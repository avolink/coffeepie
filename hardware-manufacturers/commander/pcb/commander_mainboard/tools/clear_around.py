"""clear_around.py SRC DST --keep REGEX [--cl 0.15] [--hole 0.2]   (KiCad's Python)

Takes out, in ONE pass, every track and via of the other nets that touches or comes too near copper of the kept nets
(same layer for tracks; a via counts on every layer): nearer than the clearance --cl between copper, or --hole between
a hole and copper, or 0.25 mm hole to hole.  Meant for copper that was laid over an existing board (the memory bus
brought in from the cpu_ram board): what is in its way goes, the router lays it again.

Why one pass and not DRC / remove rounds: a fragment left touching the kept copper has no pad of its own any more and
KiCad's net propagation then gives it the kept net - the short becomes invisible.
"""
import collections
import math
import os
import re
import shutil
import sys

import pcbnew
from pcbnew import ToMM


def seg_seg(a, b, c, d):
    """distance between the segments ab and cd (points as (x, y) in mm)"""
    def pt_seg(p, s, e):
        vx, vy = e[0] - s[0], e[1] - s[1]
        l2 = vx * vx + vy * vy
        if l2 == 0:
            return math.hypot(p[0] - s[0], p[1] - s[1])
        t = max(0.0, min(1.0, ((p[0] - s[0]) * vx + (p[1] - s[1]) * vy) / l2))
        return math.hypot(p[0] - (s[0] + t * vx), p[1] - (s[1] + t * vy))

    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if (ccw(a, c, d) > 0) != (ccw(b, c, d) > 0) and (ccw(a, b, c) > 0) != (ccw(a, b, d) > 0):
        return 0.0
    return min(pt_seg(a, c, d), pt_seg(b, c, d), pt_seg(c, a, b), pt_seg(d, a, b))


def main():
    src, dst = sys.argv[1:3]
    opt = sys.argv[3:]
    keep = re.compile(opt[opt.index("--keep") + 1])
    cl = float(opt[opt.index("--cl") + 1]) if "--cl" in opt else 0.15
    hcl = float(opt[opt.index("--hole") + 1]) if "--hole" in opt else 0.2
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    C = 1.0                                         # bucket size, mm
    ksegs = collections.defaultdict(list)           # (layer, i, j) -> [(a, b, halfwidth)]
    kvias = collections.defaultdict(list)           # (i, j) -> [(x, y, r, rh)]
    box = [1e9, 1e9, -1e9, -1e9]

    def grow(x, y):
        box[0], box[1], box[2], box[3] = min(box[0], x), min(box[1], y), max(box[2], x), max(box[3], y)
    others = []
    for t in b.GetTracks():
        k = bool(keep.fullmatch(t.GetNetname()))
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
            r, rh = ToMM(t.GetWidth(pcbnew.F_Cu)) / 2, ToMM(t.GetDrillValue()) / 2
            if k:
                kvias[(int(x // C), int(y // C))].append((x, y, r, rh))
                grow(x, y)
            else:
                others.append(("via", t, x, y, r, rh))
        else:
            a = (ToMM(t.GetStart().x), ToMM(t.GetStart().y))
            e = (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
            hw = ToMM(t.GetWidth()) / 2
            if k:
                l = int(t.GetLayer())
                for i in range(int(min(a[0], e[0]) // C), int(max(a[0], e[0]) // C) + 1):
                    for j in range(int(min(a[1], e[1]) // C), int(max(a[1], e[1]) // C) + 1):
                        ksegs[(l, i, j)].append((a, e, hw))
                grow(*a)
                grow(*e)
            else:
                others.append(("seg", t, a, e, hw, int(t.GetLayer())))
    layers = sorted({k_[0] for k_ in ksegs})
    doomed = []
    for o in others:
        if o[0] == "via":
            _, t, x, y, r, rh = o
            if x < box[0] - 1 or x > box[2] + 1 or y < box[1] - 1 or y > box[3] + 1:
                continue
            hit = False
            i0, j0 = int(x // C), int(y // C)
            for i in (i0 - 1, i0, i0 + 1):
                for j in (j0 - 1, j0, j0 + 1):
                    for (vx, vy, vr, vrh) in kvias.get((i, j), ()):
                        d = math.hypot(vx - x, vy - y)
                        if d < r + vr + cl or d < rh + vrh + 0.25:
                            hit = True
                    if hit:
                        break
                    for l in layers:
                        for (a, e, hw) in ksegs.get((l, i, j), ()):
                            d = seg_seg((x, y), (x, y), a, e)
                            if d < r + hw + cl or d < rh + hw + hcl:
                                hit = True
                                break
                        if hit:
                            break
                if hit:
                    break
            if hit:
                doomed.append(t)
        else:
            _, t, a, e, hw, l = o
            if max(a[0], e[0]) < box[0] - 1 or min(a[0], e[0]) > box[2] + 1 or max(a[1], e[1]) < box[1] - 1 or min(a[1], e[1]) > box[3] + 1:
                continue
            hit = False
            for i in range(int((min(a[0], e[0]) - 0.6) // C), int((max(a[0], e[0]) + 0.6) // C) + 1):
                for j in range(int((min(a[1], e[1]) - 0.6) // C), int((max(a[1], e[1]) + 0.6) // C) + 1):
                    for (s2, e2, hw2) in ksegs.get((l, i, j), ()):
                        if seg_seg(a, e, s2, e2) < hw + hw2 + cl:
                            hit = True
                            break
                    if hit:
                        break
                    for (vx, vy, vr, vrh) in kvias.get((i, j), ()):
                        d = seg_seg((vx, vy), (vx, vy), a, e)
                        if d < vr + hw + cl or d < vrh + hw + hcl:
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                doomed.append(t)
    names = sorted({t.GetNetname() for t in doomed})
    n = len(doomed)
    for t in doomed:
        b.Remove(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("clear_around: %d tracks / vias of %d nets taken out -> %s" % (n, len(names), dst))
    print("  nets:", " ".join(names))


main()
