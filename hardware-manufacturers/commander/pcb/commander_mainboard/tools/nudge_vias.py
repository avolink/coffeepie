"""nudge_vias.py SRC DST DRC.json [--box x0,y0,x1,y1] [--max-cut 0] [--max-nudge 0.2] [--protect REGEX] [--refs REGEX]
                 [--only REF.PAD,...] [--skip REF.PAD,...] [--force REF.PAD,...] [--cut-gnd] [--allow-cut REGEX] [--dry] [--report FILE]

force_vias.py sets a via in the centre of an open supply / ground pad and gives up when anything fixed is in the way.
Most of the pads it gives up on are balls with a two-pad passive on the other face whose pad lies a few hundredths of
a millimetre too near the hole.  This tool does the same job with two more degrees of freedom:

  - the via may sit anywhere in the pad where it still lands on it (a ball: up to 0.05 mm off centre; a passive's
    pad: anywhere the via's land stays on the pad);
  - a two-pad passive of another net that is in the way is nudged (at most --max-nudge, in 0.025 mm steps, shortest
    first) to where both its pads clear the new via and everything else on their face, and still cover the ends of
    the tracks and the vias that join them today.  Nothing else is ever moved.

Tracks of other nets over the spot are cut only with --max-cut N (nets per via; never a net of --protect, never
ground / 5 V / Ethernet unless --cut-gnd for ground): the router then lays those links again.
--force: these pads get a via although no plane of their net lies under them (a signal ball that needs a way down).
--dry: report only (what would be done, and for every pad left out everything that stands in its way at its centre).

One pass; moves, then removals last (KiCad's Python objects do not survive a Remove())."""
import json
import math
import os
import re
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

VD, VH = 0.25, 0.15          # the via
CL = 0.10                    # copper clearance kept to other nets (the classes here ask 0.09 / 0.10)
CL5 = 0.15                   # ... to the 5 V and Ethernet classes
HOLE = 0.196                 # hole wall to other copper (the board's rule is 0.195)
H2H = 0.25                   # hole to hole
STEP = 0.025
SW = 0.09                    # width of a stub that keeps a nudged pad on its track end
BIG = re.compile(r"VCC_SYS|VOUT_5V.*|VBUS_.*|VCC5V.*|SVC_VBUS|POE_.*|MDI.*|PHY_MDI.*|TR._48V|BS")


def seg_pt(ax, ay, bx, by, px, py):
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    k = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2)) if l2 else 0.0
    return math.hypot(px - ax - k * vx, py - ay - k * vy)


def rect_pt(r, px, py):
    return math.hypot(max(r[0] - px, 0.0, px - r[2]), max(r[1] - py, 0.0, py - r[3]))


def rect_rect(a, b):
    return math.hypot(max(a[0] - b[2], 0.0, b[0] - a[2]), max(a[1] - b[3], 0.0, b[1] - a[3]))


def seg_rect(ax, ay, bx, by, r):
    """Distance between a segment and a rectangle (0 when they meet)."""
    t0, t1 = 0.0, 1.0
    dx, dy = bx - ax, by - ay
    hit = True
    for p, q in ((-dx, ax - r[0]), (dx, r[2] - ax), (-dy, ay - r[1]), (dy, r[3] - ay)):
        if p == 0:
            if q < 0:
                hit = False
                break
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    hit = False
                    break
                t0 = max(t0, t)
            else:
                if t < t0:
                    hit = False
                    break
                t1 = min(t1, t)
    if hit:
        return 0.0
    return min(rect_pt(r, ax, ay), rect_pt(r, bx, by),
               *[seg_pt(ax, ay, bx, by, cx, cy) for cx in (r[0], r[2]) for cy in (r[1], r[3])])


def cl_of(a, b):
    return CL5 if BIG.fullmatch(a or "") or BIG.fullmatch(b or "") else CL


def shift(r, dx, dy):
    return (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)


def inside(r, x, y, m=0.005):
    return r[0] + m <= x <= r[2] - m and r[1] + m <= y <= r[3] - m


def main():
    src, dst, drc = sys.argv[1:4]
    opt = sys.argv[4:]

    def arg(name, default=None):
        return opt[opt.index(name) + 1] if name in opt else default

    box = [float(v) for v in arg("--box").split(",")] if "--box" in opt else None
    max_cut = int(arg("--max-cut", 0))
    max_nudge = float(arg("--max-nudge", 0.2))
    protect = re.compile(arg("--protect")) if "--protect" in opt else None
    refs = re.compile(arg("--refs", r"U1|U10|U20|U9|[CRL]\d+|FB\d+"))
    only = set(arg("--only").split(",")) if "--only" in opt else None
    skip = set(arg("--skip").split(",")) if "--skip" in opt else set()
    force = set(arg("--force").split(",")) if "--force" in opt else set()      # these get a via without a plane under them
    cut_gnd = "--cut-gnd" in opt
    allow_big = re.compile(arg("--allow-cut")) if "--allow-cut" in opt else None      # 5 V / Ethernet nets that may be cut all the same
    dry = "--dry" in opt
    passive = re.compile(r"[CRL]\d+|FB\d+")
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    j = json.load(open(drc, encoding="utf-8"))
    inner = [l for l in b.GetEnabledLayers().CuStack() if l not in (pcbnew.F_Cu, pcbnew.B_Cu)]
    zones = {}
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetNetname():
            zones.setdefault(z.GetNetname(), []).append(z)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    pads = []            # dicts; "rect" changes when a passive is nudged
    by_ref = {}
    for ref, f in fps.items():
        numbered = [p for p in f.Pads() if p.GetNumber()]
        nudgeable = bool(passive.fullmatch(ref)) and len(numbered) == 2 and not any(p.HasHole() for p in numbered)
        for p in f.Pads():
            if not (p.GetNumber() or p.HasHole()):
                continue                            # paste apertures: no copper
            bb = p.GetBoundingBox()
            cu = list(p.GetLayerSet().CuStack())
            d = {"net": p.GetNetname(), "rect": (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())),
                 "hole": p.HasHole(), "hr": ToMM(p.GetDrillSize().x) / 2 if p.HasHole() else 0.0,
                 "cx": ToMM(p.GetPosition().x), "cy": ToMM(p.GetPosition().y), "ref": ref, "num": p.GetNumber(),
                 "side": "T" if p.HasHole() else ("F" if pcbnew.F_Cu in cu else "B"), "nudge": nudgeable}
            pads.append(d)
            by_ref.setdefault(ref, []).append(d)
    vias, segs = [], []  # vias: [net, x, y, r, hole r]; segs: (obj, net, ax, ay, bx, by, hw, layer name)
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t.GetNetname(), ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2,
                         ToMM(t.GetDrillValue()) / 2))
        else:
            segs.append((t, t.GetNetname(), ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y),
                         ToMM(t.GetWidth()) / 2, b.GetLayerName(t.GetLayer())))
    cand = {}
    for u in j["unconnected_items"]:
        for it in u["items"]:
            m = re.match(r"Pad (\S+) \[([^\]]*)\] of (\S+)", it["description"])
            if not m or not refs.fullmatch(m.group(3)):
                continue
            x, y = it["pos"]["x"], it["pos"]["y"]
            if box and not (box[0] <= x <= box[2] and box[1] <= y <= box[3]):
                continue
            if only is not None and "%s.%s" % (m.group(3), m.group(1)) not in only:
                continue
            if "%s.%s" % (m.group(3), m.group(1)) in skip:
                continue
            cand[(m.group(3), m.group(1))] = m.group(2)
    for fp_pad in force:
        ref, num = fp_pad.split(".")
        cand[(ref, num)] = [q for q in by_ref[ref] if q["num"] == num][0]["net"]
    new = []             # (net, x, y)
    moved = {}           # ref -> [dx, dy]
    doomed, log, skipped = [], [], []
    stubs_all = []
    need_hole = VH / 2 + HOLE

    def near(lst, x, y, r, key):
        return [o for o in lst if abs(key(o)[0] - x) < r and abs(key(o)[1] - y) < r]

    nudge_why = {}

    def nudge(ref, lpads, lsegs, lvias, extra):
        """Shortest shift of passive `ref` that is legal with the vias in `extra` + `new`; None if there is none."""
        own = by_ref[ref]
        hold = []        # per pad: points its new place must still cover
        for q in own:
            lay = "F.Cu" if q["side"] == "F" else "B.Cu"
            pts = []
            for s in lsegs:
                if s[1] == q["net"] and s[7] == lay:
                    for (px, py) in ((s[2], s[3]), (s[4], s[5])):
                        if inside(q["rect"], px, py, 0.0):
                            pts.append((px, py))
            for v in lvias:
                if v[0] == q["net"] and inside(q["rect"], v[1], v[2], 0.0):
                    pts.append((v[1], v[2]))
            hold.append(pts)
        n = int(round(max_nudge / STEP))
        steps = sorted(((i * STEP, k * STEP) for i in range(-n, n + 1) for k in range(-n, n + 1)
                        if (i or k) and math.hypot(i, k) * STEP <= max_nudge + 1e-9), key=lambda s: (math.hypot(*s), s))
        def foreign(q, r, what):
            lay = "F.Cu" if q["side"] == "F" else "B.Cu"
            for (vn, vx, vy) in list(new) + list(extra):
                if vn != q["net"] and rect_pt(r, vx, vy) < max(VD / 2 + cl_of(vn, q["net"]), need_hole):
                    return "%s still too near the new via of %s" % (what, vn)
            for v in lvias:
                if v[0] != q["net"] and rect_pt(r, v[1], v[2]) < max(v[3] + cl_of(v[0], q["net"]), v[4] + HOLE):
                    return "%s too near the via of %s at (%.3f, %.3f)" % (what, v[0], v[1], v[2])
            for o in lpads:
                if o["ref"] == ref or o["net"] == q["net"]:
                    continue
                if o["hole"] and rect_pt(r, o["cx"], o["cy"]) < o["hr"] + HOLE:
                    return "%s too near the hole of %s.%s" % (what, o["ref"], o["num"])
                if o["side"] in ("T", q["side"]) and rect_rect(r, o["rect"]) < cl_of(o["net"], q["net"]):
                    return "%s too near pad %s.%s (%s)" % (what, o["ref"], o["num"], o["net"])
            for s_ in lsegs:
                if s_[1] != q["net"] and s_[7] == lay and seg_rect(s_[2], s_[3], s_[4], s_[5], r) < s_[6] + cl_of(s_[1], q["net"]):
                    return "%s too near a track of %s on %s" % (what, s_[1], lay)
            return None

        def bad(q, r, pts, stubs):
            lay = "F.Cu" if q["side"] == "F" else "B.Cu"
            why = foreign(q, r, "pad %s" % q["num"])
            if why:
                return why
            for (px, py) in pts:
                if inside(r, px, py):
                    continue
                # the pad leaves this track end / via behind: a short stub joins them again
                tx, ty = min(max(px, r[0] + 0.05), r[2] - 0.05), min(max(py, r[1] + 0.05), r[3] - 0.05)
                for k in range(6):
                    sx, sy = px + (tx - px) * k / 5.0, py + (ty - py) * k / 5.0
                    why = foreign(q, (sx - SW / 2, sy - SW / 2, sx + SW / 2, sy + SW / 2), "the stub to pad %s" % q["num"])
                    if why:
                        return why
                stubs.append((q["net"], lay, px, py, tx, ty))
            return None

        whys = {}
        for (dx, dy) in steps:
            why, stubs = None, []
            for q, pts in zip(own, hold):
                why = bad(q, shift(q["rect"], dx, dy), pts, stubs)
                if why:
                    break
            if os.environ.get("NV_DEBUG") == ref and math.hypot(dx, dy) <= 0.13:
                print("    ", ref, "%+.3f %+.3f" % (dx, dy), why, [(q["num"], [round(v, 3) for v in q["rect"]], pts) for q, pts in zip(own, hold)] if (dx, dy) == steps[0] else "")
            if why is None:
                return ((dx, dy), stubs)
            whys[why] = whys.get(why, 0) + 1
        nudge_why[ref] = "; ".join("%s (%d)" % (k, v) for k, v in sorted(whys.items(), key=lambda kv: -kv[1])[:4])
        return None

    def look(net, x, y, me, lpads, lsegs, lvias):
        """What stands in the way of a via of `net` at (x, y): (fixed reasons, passives to nudge, tracks to cut)."""
        fixed, nud, cut = [], [], []
        for o in lpads:
            if (o["ref"], o["num"]) == me:
                continue
            if o["hole"] and math.hypot(o["cx"] - x, o["cy"] - y) < VH / 2 + o["hr"] + H2H:
                fixed.append("hole of %s.%s" % (o["ref"], o["num"]))
                continue
            if o["net"] == net:
                continue
            if rect_pt(o["rect"], x, y) < max(VD / 2 + cl_of(o["net"], net), need_hole):
                if o["nudge"]:
                    if o["ref"] not in nud:
                        nud.append(o["ref"])
                else:
                    fixed.append("pad %s.%s (%s)" % (o["ref"], o["num"], o["net"] or "no net"))
        for (vn, vx, vy) in new:
            d = math.hypot(vx - x, vy - y)
            if d < VH + H2H or (vn != net and d < VD + CL):
                fixed.append("a new via of %s" % vn)
        for v in lvias:
            d = math.hypot(v[1] - x, v[2] - y)
            if d < VH / 2 + v[4] + H2H or (v[0] != net and d < VD / 2 + v[3] + cl_of(v[0], net)):
                fixed.append("via of %s" % v[0])
        for s in lsegs:
            if s[1] == net:
                continue
            if seg_pt(s[2], s[3], s[4], s[5], x, y) < s[6] + max(VD / 2 + cl_of(s[1], net), need_hole):
                if s[0] is None or (protect is not None and protect.fullmatch(s[1])) or (BIG.fullmatch(s[1]) and not (allow_big and allow_big.fullmatch(s[1]))) or (s[1] == "GND" and not cut_gnd):
                    fixed.append("track of %s on %s" % (s[1], s[7]))
                else:
                    cut.append(s)
        return sorted(set(fixed)), nud, cut

    for (ref, num), net in sorted(cand.items()):
        me = [q for q in by_ref[ref] if q["num"] == num][0]
        cx, cy = me["cx"], me["cy"]
        if any(vn == net and inside(me["rect"], vx, vy, -0.05) for (vn, vx, vy, _r, _h) in vias) or \
                any(vn == net and inside(me["rect"], vx, vy, -0.05) for (vn, vx, vy) in new):
            skipped.append("%s.%s %s: has a via already" % (ref, num, net))
            continue
        lpads = near(pads, cx, cy, 2.0, lambda o: (o["cx"], o["cy"]))
        lvias = near(vias, cx, cy, 2.0, lambda v: (v[1], v[2]))
        lsegs = [s for s in segs if not (max(s[2], s[4]) < cx - 2 or min(s[2], s[4]) > cx + 2 or max(s[3], s[5]) < cy - 2 or min(s[3], s[5]) > cy + 2)]
        r = me["rect"]
        if me["nudge"] and not ("--on-ball" in opt and "%s.%s" % (ref, num) in force):   # (--on-ball: a forced pad stands over its ball, stay on it)
            mx, my = max(0.0, (r[2] - r[0]) / 2 - VD / 2 + 0.05), max(0.0, (r[3] - r[1]) / 2 - VD / 2 + 0.05)
        else:
            mx = my = 0.05
        sites = sorted(((i * STEP, k * STEP) for i in range(-8, 9) for k in range(-8, 9)
                        if abs(i * STEP) <= mx + 1e-9 and abs(k * STEP) <= my + 1e-9), key=lambda s: (math.hypot(*s), s))
        best, centre_why = None, None
        for (ox, oy) in sites:
            x, y = round(cx + ox, 4), round(cy + oy, 4)
            at = VECTOR2I(FromMM(x), FromMM(y))
            plane = sorted({b.GetLayerName(l) for z in zones.get(net, []) for l in z.GetLayerSet().Seq()
                            if l in inner and z.HitTestFilledArea(l, at, FromMM(0.02))})
            if not plane and "%s.%s" % (ref, num) not in force:
                if (ox, oy) == (0.0, 0.0):
                    centre_why = "no plane of its own under it"
                continue
            fixed, nud, cut = look(net, x, y, (ref, num), lpads, lsegs, lvias)
            cut_nets = sorted({s[1] for s in cut})
            if (ox, oy) == (0.0, 0.0):
                centre_why = "; ".join(fixed + ["nudge " + n for n in nud] + ["cut %s on %s" % (n, ",".join(sorted({s[7] for s in cut if s[1] == n}))) for n in cut_nets]) or "free"
            if fixed or len(cut_nets) > max_cut:
                continue
            plan, good, undo = [], True, []
            for n in nud:
                got = nudge(n, lpads, lsegs, lvias, [(net, x, y)])
                if got is None:
                    good = False
                    break
                sh, st = got
                plan.append((n, sh, st))
                for q in by_ref[n]:                 # tentatively moved, so the next passive sees it there
                    undo.append((q, q["rect"], q["cx"], q["cy"]))
                    q["rect"] = shift(q["rect"], *sh)
                    q["cx"] += sh[0]
                    q["cy"] += sh[1]
            for (q, r0, x0, y0) in undo:
                q["rect"], q["cx"], q["cy"] = r0, x0, y0
            if not good:
                if (ox, oy) == (0.0, 0.0):
                    centre_why += " - no legal place for %s: %s" % (n, nudge_why.get(n, ""))
                continue
            score = (len(cut_nets), sum(math.hypot(*sh) for (_n, sh, _st) in plan), math.hypot(ox, oy))
            if best is None or score < best[0]:
                best = (score, x, y, plan, cut, plane)
            if score[0] == 0 and score[1] == 0:
                break
        if best is None:
            skipped.append("%s.%s %s: %s" % (ref, num, net, centre_why))
            continue
        (_s, x, y, plan, cut, plane) = best
        new.append((net, x, y))
        for (n, sh, st) in plan:
            for q in by_ref[n]:
                q["rect"] = shift(q["rect"], *sh)
                q["cx"] += sh[0]
                q["cy"] += sh[1]
            for (sn, lay, ax, ay, bx, by) in st:
                stubs_all.append((sn, lay, ax, ay, bx, by))
                segs.append((None, sn, ax, ay, bx, by, SW / 2, lay))
            m = moved.setdefault(n, [0.0, 0.0])
            m[0] += sh[0]
            m[1] += sh[1]
        for s in cut:
            if s[0] not in [d_[0] for d_ in doomed]:
                doomed.append(s)
        cut_ids = {id(s[0]) for s in cut}
        segs[:] = [s for s in segs if id(s[0]) not in cut_ids]
        log.append("%s.%s %s (%.3f, %.3f)%s -> %s%s%s" % (
            ref, num, net, x, y, "" if (x, y) == (round(cx, 4), round(cy, 4)) else " off centre", ",".join(plane),
            "; nudged: " + ", ".join("%s %+.3f %+.3f%s" % (n, sh[0], sh[1], " +%d stub" % len(st) if st else "") for (n, sh, st) in plan) if plan else "",
            "; cut: " + ", ".join(sorted({"%s on %s" % (s[1], s[7]) for s in cut})) if cut else ""))
    cut_nets = sorted({s[1] for s in doomed})
    print("nudge_vias%s: %d vias set in pads, %d passives nudged, %d track segments of %d nets cut -> %s" % (
        " (dry run)" if dry else "", len(new), len(moved), len(doomed), len(cut_nets), dst))
    for s in log:
        print("  +", s)
    for s in skipped:
        print("  -", s)
    print("  cut nets:", " ".join(cut_nets))
    if "--report" in opt:
        json.dump({"vias": log, "skipped": skipped, "cut_nets": cut_nets, "moved": {k: [round(v[0], 4), round(v[1], 4)] for k, v in moved.items()}},
                  open(arg("--report"), "w", encoding="utf-8"), indent=1)
    if dry:
        return
    for (net, x, y) in new:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        v.SetWidth(pcbnew.F_Cu, FromMM(VD))
        v.SetDrill(FromMM(VH))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(b.FindNet(net))
        b.Add(v)
    for (sn, lay, ax, ay, bx, by) in stubs_all:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(VECTOR2I(FromMM(ax), FromMM(ay)))
        t.SetEnd(VECTOR2I(FromMM(bx), FromMM(by)))
        t.SetWidth(FromMM(SW))
        t.SetLayer(b.GetLayerID(lay))
        t.SetNet(b.FindNet(sn))
        b.Add(t)
    for ref, (dx, dy) in moved.items():
        f = fps[ref]
        pos = f.GetPosition()
        f.SetPosition(VECTOR2I(pos.x + FromMM(dx), pos.y + FromMM(dy)))
    for s in doomed:
        b.Remove(s[0])
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")


main()
