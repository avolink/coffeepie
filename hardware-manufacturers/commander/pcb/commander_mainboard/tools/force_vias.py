"""force_vias.py SRC DST DRC.json [--box x0,y0,x1,y1] [--free-only] [--max-cut 2] [--refs REGEX] [--pads FILE] [--report FILE]   (KiCad's Python)

A supply or ground pad that is still open although its own net's plane lies right under it only lacks a via.  This
sets that via in the pad (0.25 / 0.15 mm, filled and capped like the other vias in pads of this board) for every
such end of the open links listed in a KiCad DRC report (kicad-cli pcb drc --format json):

  - the pad belongs to a BGA or to a two-pad passive (--refs, default U1|U10|U20|[CRL]\\d+|FB\\d+);
  - its net has a filled zone at the pad's centre on an inner layer;
  - no pad, via or hole of another net is in the via's way on any layer (the opposite face included): such a site is
    skipped - nothing fixed is ever touched;
  - tracks of other nets (at most --max-cut nets per via) that pass over the spot on some layer are taken out (whole
    segments) unless --free-only:
    the router then lays just those links again round the new via (pf_route keeps the rest of the net's copper).
    Why not leave it all to the router's repair step: that one routes the net in the way anew from its pads, which
    fails where a bus is dense, although a 0.3 mm step aside is all that is needed.

One pass; removals last (KiCad's Python objects do not survive a Remove())."""
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


def seg_pt(ax, ay, bx, by, px, py):
    vx, vy = bx - ax, by - ay
    l2 = vx * vx + vy * vy
    k = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2)) if l2 else 0.0
    return math.hypot(px - ax - k * vx, py - ay - k * vy)


def rect_pt(r, px, py):
    return math.hypot(max(r[0] - px, 0.0, px - r[2]), max(r[1] - py, 0.0, py - r[3]))


def main():
    src, dst, drc = sys.argv[1:4]
    opt = sys.argv[4:]
    box = [float(v) for v in opt[opt.index("--box") + 1].split(",")] if "--box" in opt else None
    free_only = "--free-only" in opt
    max_cut = int(opt[opt.index("--max-cut") + 1]) if "--max-cut" in opt else 2
    refs = re.compile(opt[opt.index("--refs") + 1] if "--refs" in opt else r"U1|U10|U20|[CRL]\d+|FB\d+")
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    j = json.load(open(drc, encoding="utf-8"))
    big = re.compile(r"VCC_SYS|VOUT_5V.*|VBUS_.*|VCC5V.*|SVC_VBUS|POE_.*|MDI.*|PHY_MDI.*|TR._48V|BS")
    inner = [l for l in b.GetEnabledLayers().CuStack() if l not in (pcbnew.F_Cu, pcbnew.B_Cu)]
    zones = {}
    for z in b.Zones():
        if not z.GetIsRuleArea() and z.GetNetname():
            zones.setdefault(z.GetNetname(), []).append(z)
    pads = []            # (net, rect, layers set or None for through, ref, num, has hole, hole r, cx, cy)
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            pads.append((p.GetNetname(), (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())),
                         p.HasHole(), f.GetReference(), p.GetNumber(), ToMM(p.GetDrillSize().x) / 2 if p.HasHole() else 0.0,
                         ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), bool(p.GetNumber())))
    vias, segs = [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t, t.GetNetname(), ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2,
                         ToMM(t.GetDrillValue()) / 2))
        else:
            segs.append((t, t.GetNetname(), ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y),
                         ToMM(t.GetWidth()) / 2, b.GetLayerName(t.GetLayer())))
    # the candidate pads: the ends of the open links
    cand = {}
    for u in j["unconnected_items"]:
        for it in u["items"]:
            m = re.match(r"Pad (\S+) \[([^\]]*)\] of (\S+)", it["description"])
            if not m or not refs.fullmatch(m.group(3)):
                continue
            x, y = it["pos"]["x"], it["pos"]["y"]
            if box and not (box[0] <= x <= box[2] and box[1] <= y <= box[3]):
                continue
            cand[(m.group(3), m.group(1))] = m.group(2)
    # --pads FILE: a JSON list (or {"pads": [...]}) of [ref, pad]: these get a via whether a DRC link ends on them or
    # not, and without a plane under them (a capacitor set over its ball: the via joins the two)
    forced = set()
    if "--pads" in opt:
        pl = json.load(open(opt[opt.index("--pads") + 1], encoding="utf-8"))
        for ref, num in (pl["pads"] if isinstance(pl, dict) else pl):
            f = b.FindFootprintByReference(ref)
            q = [q for q in f.Pads() if q.GetNumber() == num][0]
            cand[(ref, num)] = q.GetNetname()
            forced.add((ref, num))
    new, doomed, log, skipped = [], [], [], []
    for (ref, num), net in sorted(cand.items()):
        f = b.FindFootprintByReference(ref)
        p = [q for q in f.Pads() if q.GetNumber() == num][0]
        x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
        at = VECTOR2I(FromMM(x), FromMM(y))
        plane = [b.GetLayerName(l) for z in zones.get(net, []) for l in z.GetLayerSet().Seq()
                 if l in inner and z.HitTestFilledArea(l, at, FromMM(0.02))]
        if not plane and (ref, num) not in forced:
            skipped.append("%s.%s %s: no plane of its own under it" % (ref, num, net))
            continue
        if any(vn == net and math.hypot(vx - x, vy - y) < 0.2 for (_t, vn, vx, vy, _r, _h) in vias) or \
                any(nn == net and math.hypot(nx - x, ny - y) < 0.2 for (_n, nn, nx, ny) in new):
            skipped.append("%s.%s %s: has a via already" % (ref, num, net))
            continue
        why = None
        for (pn, rect, hole, pref, pnum, hr, pcx, pcy, numbered) in pads:
            if pn == net and (pref, pnum) != (ref, num) and not hole:
                continue
            if (pref, pnum) == (ref, num) or not (numbered or hole):
                continue                        # (unnumbered pads are paste apertures: no copper)
            d = rect_pt(rect, x, y)
            lim = VD / 2 + (CL5 if big.fullmatch(pn or "") or big.fullmatch(net) else CL)
            if pn != net and d < max(lim, VH / 2 + HOLE):
                why = "pad %s.%s (%s) in the way" % (pref, pnum, pn or "no net")
                break
            if hole and math.hypot(pcx - x, pcy - y) < VH / 2 + hr + H2H:
                why = "hole of %s.%s too near" % (pref, pnum)
                break
        if why is None:
            for (_n, nn, nx, ny) in new:
                d = math.hypot(nx - x, ny - y)
                if d < VH + H2H or (nn != net and d < VD + CL):
                    why = "another new via too near"
                    break
        if why is None:
            for (t, vn, vx, vy, vr, vh) in vias:
                d = math.hypot(vx - x, vy - y)
                if d < VH / 2 + vh + H2H or (vn != net and d < VD / 2 + vr + (CL5 if big.fullmatch(vn) else CL)):
                    why = "via of %s too near" % vn
                    break
        if why:
            skipped.append("%s.%s %s: %s" % (ref, num, net, why))
            continue
        hit = []
        for s in segs:
            (t, sn, ax, ay, bx, by, hw, ln) = s
            if sn == net:
                continue
            if max(ax, bx) < x - 1 or min(ax, bx) > x + 1 or max(ay, by) < y - 1 or min(ay, by) > y + 1:
                continue
            d = seg_pt(ax, ay, bx, by, x, y)
            if d < hw + max(VD / 2 + (CL5 if big.fullmatch(sn) else CL), VH / 2 + HOLE):
                hit.append(s)
        if hit and free_only:
            skipped.append("%s.%s %s: tracks of %s pass over it" % (ref, num, net, ", ".join(sorted({h[1] for h in hit}))))
            continue
        if len({h[1] for h in hit}) > max_cut:
            skipped.append("%s.%s %s: %d nets pass over it (%s)" % (ref, num, net, len({h[1] for h in hit}), ", ".join(sorted({h[1] for h in hit}))))
            continue
        if any(h[1] == "GND" or big.fullmatch(h[1]) for h in hit):
            skipped.append("%s.%s %s: ground / 5 V / Ethernet track over it" % (ref, num, net))
            continue
        new.append((net, net, x, y))
        for h in hit:
            if h[0] not in [d_[0] for d_ in doomed]:
                doomed.append(h)
        log.append("%s.%s %s (%.2f, %.2f) -> %s%s" % (ref, num, net, x, y, ",".join(sorted(set(plane))),
                                                      "; cut: " + ", ".join(sorted({"%s on %s" % (h[1], h[7]) for h in hit})) if hit else ""))
    for (net, _n, x, y) in new:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        v.SetWidth(pcbnew.F_Cu, FromMM(VD))
        v.SetDrill(FromMM(VH))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(b.FindNet(net))
        b.Add(v)
    cut_nets = sorted({h[1] for h in doomed})
    n_new, n_cut = len(new), len(doomed)
    for h in doomed:
        b.Remove(h[0])
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("force_vias: %d vias set in pads, %d track segments of %d nets cut -> %s" % (n_new, n_cut, len(cut_nets), dst))
    for s in log:
        print("  +", s)
    for s in skipped:
        print("  -", s)
    print("  cut nets:", " ".join(cut_nets))
    if "--report" in opt:
        json.dump({"vias": log, "skipped": skipped, "cut_nets": cut_nets}, open(opt[opt.index("--report") + 1], "w", encoding="utf-8"), indent=1)


main()
