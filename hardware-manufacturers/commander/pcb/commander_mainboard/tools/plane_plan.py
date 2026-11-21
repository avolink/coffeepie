"""plane_plan.py SRC DST CONFIG.json - supply planes laid out from where each rail's pads and vias are.

The board's power layers are shared by many rails.  Instead of one box per rail (with priorities deciding who gets the
overlap - most rails then get no copper at all where they need it) this works on a grid:

  1. every rail is given ONE of the power layers: the one on which its terminals mix least with the rails already there
     (or the layer named for it in "assign");
  2. on its layer each rail first gets a skeleton: its terminals (the net's vias and through-hole pads; its SMD pads as
     the places where a via will stand) joined by the shortest free paths, round the other nets' holes and terminals;
  3. the free cells are then handed to the nearest rail (all rails grow at the same speed);
  4. each rail's cells become zone outlines (one zone per connected piece), replacing that layer's old supply zones in
     the window.

KiCad's zone filler does the real clearances afterwards; the DRC is the judge.  A terminal no path was found for is
reported (the router joins it with a track).

CONFIG: {"layers": ["In3.Cu", "In4.Cu"], "window": [x0, y0, x1, y1], "grid": 0.1,
         "nets": [regex, ...],            rails to plan (full match); "min_pads": 3 (smaller ones are left to tracks)
         "skip": [regex, ...], "assign": {"VCC_DDR": "In4.Cu", ...},
         "keep_zones": [regex, ...]       zones of these nets on the power layers stay; their outline is an obstacle
         "clearance": 0.12, "term_r": 0.3, "hole_cl": 0.2, "edge": 0.35,
         "via_r": 0.26,                   a foreign via as an obstacle: this radius instead of hole + hole_cl.  Between
                                          two vias of a 0.65 mm ball field the real web is 0.65 - 2 x (0.075 + 0.195)
                                          = 0.11 mm; with 0.26 (and a 0.05 grid) the planes thread through the field
                                          as the filler will really lay them, and still stop at a 0.5 mm field
         "min_thickness": 0.1,            of the zones (0.09 keeps the 0.11 mm webs)
         "report": file}
"""
import collections
import json
import math
import os
import re
import shutil
import sys
import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

NB = ((1, 0), (-1, 0), (0, 1), (0, -1))


def main():
    src, dst, cfgp = sys.argv[1:4]
    cfg = json.load(open(cfgp, encoding="utf-8"))
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    x0, y0, x1, y1 = cfg["window"]
    G = float(cfg.get("grid", 0.1))
    W, H = int(round((x1 - x0) / G)), int(round((y1 - y0) / G))
    lay_names = cfg["layers"]
    lay_ids = [b.GetLayerID(n) for n in lay_names]
    want = [re.compile(p) for p in cfg["nets"]]
    skip = [re.compile(p) for p in cfg.get("skip", [])]
    keepz = [re.compile(p) for p in cfg.get("keep_zones", [])]
    min_pads = int(cfg.get("min_pads", 3))
    term_r = float(cfg.get("term_r", 0.3))
    hole_cl = float(cfg.get("hole_cl", 0.2))
    edge_cl = float(cfg.get("edge", 0.35))
    via_r = cfg.get("via_r")

    def cell(x, y):
        return int((x - x0) / G), int((y - y0) / G)

    def inwin(x, y):
        return x0 <= x < x1 and y0 <= y < y1

    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = x0 + (xx + 0.5) * G, y0 + (yy + 0.5) * G

    def disc(mask, x, y, r, val=True):
        i0, i1 = max(0, int((x - r - x0) / G)), min(W, int((x + r - x0) / G) + 2)
        j0, j1 = max(0, int((y - r - y0) / G)), min(H, int((y + r - y0) / G) + 2)
        if i0 >= i1 or j0 >= j1:
            return
        sub = (cx[j0:j1, i0:i1] - x) ** 2 + (cy[j0:j1, i0:i1] - y) ** 2 <= r * r
        mask[j0:j1, i0:i1][sub] = val

    # ---- the rails and their terminals
    pads = collections.defaultdict(list)        # net -> [(x, y, through)]
    for f in b.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n:
                continue
            pads[n].append((ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), p.HasHole()))
    vias = collections.defaultdict(list)        # net -> [(x, y, r_copper, r_hole)]
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias[t.GetNetname()].append((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y),
                                         ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, ToMM(t.GetDrillValue()) / 2))
    rails = []
    for n in sorted(pads):
        if n == "GND" or not any(r.fullmatch(n) for r in want) or any(r.fullmatch(n) for r in skip):
            continue
        if len([q for q in pads[n] if inwin(q[0], q[1])]) >= min_pads:
            rails.append(n)
    terms = {}
    for n in rails:
        ts = [(x, y) for (x, y, th) in pads[n] if inwin(x, y)] + [(x, y) for (x, y, _, _) in vias.get(n, []) if inwin(x, y)]
        seen, out = set(), []
        for (x, y) in ts:                       # one terminal per neighbourhood
            k = (int(x / 0.15), int(y / 0.15))
            if k not in seen:
                seen.add(k)
                out.append((x, y))
        terms[n] = out
    print(len(rails), "rails:", " ".join("%s(%d)" % (n, len(terms[n])) for n in sorted(rails, key=lambda n_: -len(terms[n_]))))

    # ---- what no plane may cover on a layer: the edge margin, fill keep-outs, kept zones, tracks of that layer
    def base_block(lid):
        blk = np.zeros((H, W), bool)
        bb = b.GetBoardEdgesBoundingBox()
        bx0, by0, bx1, by1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
        blk |= (cx < bx0 + edge_cl) | (cx > bx1 - edge_cl) | (cy < by0 + edge_cl) | (cy > by1 - edge_cl)
        for z in list(b.Zones()) + [z for f in b.GetFootprints() for z in f.Zones()]:
            if not z.IsOnLayer(lid):
                continue
            if z.GetIsRuleArea():
                if not z.GetDoNotAllowZoneFills():
                    continue
            elif not any(r.fullmatch(z.GetNetname()) for r in keepz):
                continue
            poly = z.Outline()
            zb = poly.BBox()
            i0, j0 = cell(ToMM(zb.GetLeft()) - 0.3, ToMM(zb.GetTop()) - 0.3)
            i1, j1 = cell(ToMM(zb.GetRight()) + 0.3, ToMM(zb.GetBottom()) + 0.3)
            i0, j0, i1, j1 = max(0, i0), max(0, j0), min(W, i1 + 1), min(H, j1 + 1)
            for j in range(j0, j1):
                for i in range(i0, i1):
                    if poly.Collide(VECTOR2I(FromMM(float(cx[j, i])), FromMM(float(cy[j, i]))), FromMM(0.25)):
                        blk[j, i] = True
        for t in b.GetTracks():
            if t.Type() == pcbnew.PCB_VIA_T or t.GetLayer() != lid:
                continue
            ax, ay, ex, ey = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
            if max(ax, ex) < x0 or min(ax, ex) > x1 or max(ay, ey) < y0 or min(ay, ey) > y1:
                continue
            r = ToMM(t.GetWidth()) / 2 + 0.15
            n = max(1, int(math.hypot(ex - ax, ey - ay) / (G / 2)))
            for k in range(n + 1):
                disc(blk, ax + (ex - ax) * k / n, ay + (ey - ay) * k / n, r)
        return blk

    # every hole with its clearance (a plane of another net cannot be there); per rail its own holes, to take out again
    all_holes = np.zeros((H, W), bool)
    own_holes = {n: np.zeros((H, W), bool) for n in rails}
    for n, vs in vias.items():
        for (x, y, rc, rh) in vs:
            if x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1:
                r = float(via_r) if via_r else max(rh + hole_cl, rc + 0.1) + G * 0.3
                disc(all_holes, x, y, r)
                if n in own_holes:
                    disc(own_holes[n], x, y, r)
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.HasHole():
                x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
                if x0 - 3 <= x <= x1 + 3 and y0 - 3 <= y <= y1 + 3:
                    r = max(ToMM(p.GetSize().x), ToMM(p.GetSize().y)) / 2 + hole_cl
                    disc(all_holes, x, y, r)
                    if p.GetNetname() in own_holes:
                        disc(own_holes[p.GetNetname()], x, y, r)

    # ---- 1: a layer for every rail
    def hull_box(n):
        xs = [t[0] for t in terms[n]]
        ys = [t[1] for t in terms[n]]
        return min(xs), min(ys), max(xs), max(ys)

    def mix(a, c):
        """how many terminals of a lie in c's box and the other way round"""
        ax0, ay0, ax1, ay1 = hull_box(a)
        cx0, cy0, cx1, cy1 = hull_box(c)
        return sum(1 for (x, y) in terms[a] if cx0 <= x <= cx1 and cy0 <= y <= cy1) + \
            sum(1 for (x, y) in terms[c] if ax0 <= x <= ax1 and ay0 <= y <= ay1)

    assign = {n: l for n, l in (cfg.get("assign") or {}).items() if n in rails}
    on = {n_: [] for n_ in lay_names}
    for n in rails:
        if n in assign:
            on[assign[n]].append(n)
    for n in sorted(rails, key=lambda n_: -len(terms[n_])):
        if n in assign:
            continue
        cost = {ln: sum(mix(n, o) for o in on[ln]) for ln in lay_names}
        ln = min(lay_names, key=lambda l_: (cost[l_], len(on[l_])))
        assign[n] = ln
        on[ln].append(n)
    for ln in lay_names:
        print(ln + ":", " ".join(on[ln]))

    # ---- 2 + 3 per layer
    report = {"layers": {}, "unreached": {}, "assign": assign}
    new_zones = []
    for ln, lid in zip(lay_names, lay_ids):
        nets = sorted(on[ln], key=lambda n_: -len(terms[n_]))
        if not nets:
            continue
        base = base_block(lid)
        owner = np.full((H, W), -1, np.int32)
        reserve = np.full((H, W), -1, np.int32)          # every terminal's own disc: nobody runs over a foreign terminal
        for k, n in enumerate(nets):
            for (x, y) in terms[n]:
                m = np.zeros((H, W), bool)
                disc(m, x, y, term_r)
                reserve[m & (reserve == -1)] = k
        for k, n in enumerate(nets):
            blocked = base | (all_holes & ~own_holes[n]) | ((reserve != -1) & (reserve != k)) | ((owner != -1) & (owner != k))
            tcells = []
            for (x, y) in terms[n]:
                i, j = cell(x, y)
                if 0 <= i < W and 0 <= j < H:
                    tcells.append((i, j))
            if not tcells:
                continue
            tree = np.zeros((H, W), bool)
            left = set(range(len(tcells)))
            mxc = sum(t[0] for t in tcells) / len(tcells)
            myc = sum(t[1] for t in tcells) / len(tcells)
            s = min(left, key=lambda q: (tcells[q][0] - mxc) ** 2 + (tcells[q][1] - myc) ** 2)
            left.discard(s)
            tree[tcells[s][1], tcells[s][0]] = True
            tset = {}
            for q in range(len(tcells)):
                tset.setdefault(tcells[q], []).append(q)
            for q in tset[tcells[s]]:
                left.discard(q)
            unreached = []
            while left:
                dist = np.full((H, W), -1, np.int32)     # one wave from the whole tree to the nearest loose terminal
                front = collections.deque()
                js, is_ = np.nonzero(tree)
                for j, i in zip(js.tolist(), is_.tolist()):
                    dist[j, i] = 0
                    front.append((i, j))
                hit = None
                while front:
                    i, j = front.popleft()
                    if (i, j) in tset and any(q in left for q in tset[(i, j)]):
                        hit = (i, j)
                        break
                    d = dist[j, i] + 1
                    for di, dj in NB:
                        a, c = i + di, j + dj
                        if 0 <= a < W and 0 <= c < H and dist[c, a] < 0:
                            if blocked[c, a] and (a, c) not in tset:
                                continue
                            dist[c, a] = d
                            front.append((a, c))
                if hit is None:
                    unreached = sorted(left)
                    break
                for q in tset[hit]:
                    left.discard(q)
                i, j = hit
                while dist[j, i] > 0:
                    tree[j, i] = True
                    for di, dj in NB:
                        a, c = i + di, j + dj
                        if 0 <= a < W and 0 <= c < H and dist[c, a] == dist[j, i] - 1:
                            i, j = a, c
                            break
                tree[j, i] = True
            fat = tree.copy()                            # the skeleton one cell fatter
            fat[1:, :] |= tree[:-1, :]
            fat[:-1, :] |= tree[1:, :]
            fat[:, 1:] |= tree[:, :-1]
            fat[:, :-1] |= tree[:, 1:]
            fat &= ~blocked
            owner[(fat | tree) & (owner == -1)] = k
            owner[(reserve == k) & (owner == -1) & ~base] = k
            if unreached:
                report["unreached"].setdefault(n, []).extend(
                    ["%.2f,%.2f" % (x0 + (tcells[q][0] + 0.5) * G, y0 + (tcells[q][1] + 0.5) * G) for q in unreached])
        # 3: growth - every rail takes the free cells next to it, all at the same speed
        free = ~base & (owner == -1)
        for _ in range(W + H):
            grew = False
            for di, dj in NB:
                sh = np.full((H, W), -1, np.int32)
                if di == 1:
                    sh[:, 1:] = owner[:, :-1]
                elif di == -1:
                    sh[:, :-1] = owner[:, 1:]
                elif dj == 1:
                    sh[1:, :] = owner[:-1, :]
                else:
                    sh[:-1, :] = owner[1:, :]
                take = free & (sh != -1)
                if take.any():
                    owner[take] = sh[take]
                    free &= ~take
                    grew = True
            if not grew:
                break
        report["layers"][ln] = {n: round(float((owner == k).sum()) * G * G, 1) for k, n in enumerate(nets)}
        print(ln, "mm2:", " ".join("%s:%.0f" % (n, report["layers"][ln][n]) for n in nets))
        # 4: outlines
        for k, n in enumerate(nets):
            m = owner == k
            if not m.any():
                continue
            ps = pcbnew.SHAPE_POLY_SET()
            for j in range(H):
                row = m[j]
                if not row.any():
                    continue
                d = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
                starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
                for s_, e_ in zip(starts.tolist(), ends.tolist()):
                    ps.NewOutline()
                    ya, yb = y0 + j * G - 0.002, y0 + (j + 1) * G + 0.002
                    xa, xb = x0 + s_ * G - 0.002, x0 + e_ * G + 0.002
                    for (px, py) in ((xa, ya), (xb, ya), (xb, yb), (xa, yb)):
                        ps.Append(FromMM(px), FromMM(py))
            ps.Simplify()
            ps.Fracture()
            new_zones.append((n, lid, ps))
    # ---- replace the old supply zones of the planned layers inside the window
    # (KiCad's Python objects do not survive a Remove(): the old zones are picked first, taken out last)
    old = []
    for z in list(b.Zones()):
        if z.GetIsRuleArea() or z.GetNetname() == "GND" or any(r.fullmatch(z.GetNetname()) for r in keepz):
            continue
        if not any(z.IsOnLayer(l) for l in lay_ids):
            continue
        zb = z.GetBoundingBox()
        if inwin((ToMM(zb.GetLeft()) + ToMM(zb.GetRight())) / 2, (ToMM(zb.GetTop()) + ToMM(zb.GetBottom())) / 2):
            old.append(z)
    gone = len(old)
    made = 0
    for n, lid, ps in new_zones:
        net = b.FindNet(n)
        for oi in range(ps.OutlineCount()):
            o = ps.Outline(oi)
            if o.Area() < FromMM(0.3) * FromMM(0.3):
                continue
            z = pcbnew.ZONE(b)
            z.SetLayer(lid)
            z.SetNet(net)
            z.SetZoneName("%s plane %s" % (n, b.GetLayerName(lid)))
            z.AddPolygon(o)
            z.SetLocalClearance(FromMM(float(cfg.get("clearance", 0.12))))
            z.SetMinThickness(FromMM(float(cfg.get("min_thickness", 0.1))))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            z.SetAssignedPriority(1)
            b.Add(z)
            made += 1
    for z in old:
        b.Remove(z)
    print(gone, "old zones taken out,", made, "zones made")
    if report["unreached"]:
        print("no path on the plane for:", "; ".join("%s %d" % (n, len(v)) for n, v in report["unreached"].items()))
    if cfg.get("report"):
        json.dump(report, open(cfg["report"], "w", encoding="utf-8"), indent=1)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("written", dst)


main()
