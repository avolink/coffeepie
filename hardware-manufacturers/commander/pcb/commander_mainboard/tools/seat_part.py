"""seat_part.py SRC DST REF[@x,y] [REF ...] [--radius MM] [--avoid REGEX]   (KiCad's Python)

Sets a part down again at the nearest free spot of its own face (searching from where it is, or from x,y): its
courtyard clear of every other courtyard (through-hole parts count on both faces) and of the board edge, its pads
clear of every via and of the tracks on its face whose net matches --avoid (default: every net but the pad's own).
The part's old copper is left behind as stubs for the prune."""
import math
import os
import re
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I


def main():
    src, dst = sys.argv[1:3]
    args = sys.argv[3:]
    radius = float(args[args.index("--radius") + 1]) if "--radius" in args else 25.0
    avoid = re.compile(args[args.index("--avoid") + 1]) if "--avoid" in args else None
    refs = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--radius", "--avoid"))]
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    CL, CLV = FromMM(0.1), FromMM(0.17)
    vias, segs = [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t.GetPosition().x, t.GetPosition().y, t.GetWidth(pcbnew.F_Cu) // 2, t.GetNetname()))
        elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu) and (avoid is None or avoid.fullmatch(t.GetNetname())):
            segs.append((t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth() // 2, t.GetNetname()))
    bb = b.GetBoardEdgesBoundingBox()

    def court(f):
        c = f.GetCourtyard(f.GetLayer())
        return c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    courts = {f.GetReference(): (f.GetLayer(), court(f), any(p.HasHole() for p in f.Pads())) for f in b.GetFootprints()}
    near = {}

    def seg_hit(seg, bx, grow):
        l, x0, y0, x1, y1, hw, n = seg
        g = grow + hw
        left, top, right, bottom = bx.GetLeft() - g, bx.GetTop() - g, bx.GetRight() + g, bx.GetBottom() + g
        if max(x0, x1) < left or min(x0, x1) > right or max(y0, y1) < top or min(y0, y1) > bottom:
            return False
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / FromMM(0.05)))
        for k in range(steps + 1):
            x, y = x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps
            if left <= x <= right and top <= y <= bottom:
                return True
        return False

    def free(f):
        cb = court(f)
        m = FromMM(0.4)
        if cb.GetLeft() < bb.GetLeft() + m or cb.GetRight() > bb.GetRight() - m or cb.GetTop() < bb.GetTop() + m or cb.GetBottom() > bb.GetBottom() - m:
            return False
        for r, (lay, ob, th) in courts.items():
            if r == f.GetReference() or (lay != f.GetLayer() and not th):
                continue
            if cb.GetLeft() < ob.GetRight() and ob.GetLeft() < cb.GetRight() and cb.GetTop() < ob.GetBottom() and ob.GetTop() < cb.GetBottom():
                return False
        for p in f.Pads():
            if not p.GetNumber():
                continue
            n = p.GetNetname()
            bx = p.GetBoundingBox()
            for (x, y, r, vn) in near["vias"]:
                if vn != n and bx.GetLeft() - r - CLV <= x <= bx.GetRight() + r + CLV and bx.GetTop() - r - CLV <= y <= bx.GetBottom() + r + CLV:
                    return False
            for seg in near["segs"]:
                if seg[6] != n and p.IsOnLayer(seg[0]) and seg_hit(seg, bx, CL):
                    return False
        return True
    for spec in refs:
        ref, _, at = spec.partition("@")
        f = b.FindFootprintByReference(ref)
        o = f.GetPosition()
        if at:
            o = VECTOR2I(FromMM(float(at.split(",")[0])), FromMM(float(at.split(",")[1])))
        rot0 = f.GetOrientationDegrees()
        R = FromMM(radius + 4)
        near["vias"] = [v for v in vias if abs(v[0] - o.x) < R and abs(v[1] - o.y) < R]
        near["segs"] = [g for g in segs if min(abs(g[1] - o.x), abs(g[3] - o.x)) < R and min(abs(g[2] - o.y), abs(g[4] - o.y)) < R]
        best = None
        old = f.GetPosition()
        for ring in range(0, int(radius / 0.2) + 1):
            r = ring * 0.2
            n = max(1, int(2 * math.pi * r / 0.2))
            for k in range(n):
                ang = 2 * math.pi * k / n
                x, y = o.x + FromMM(r * math.cos(ang)), o.y + FromMM(r * math.sin(ang))
                for rot in (rot0, rot0 + 90):
                    f.SetPosition(VECTOR2I(int(x), int(y)))
                    f.SetOrientationDegrees(rot)
                    if free(f):
                        best = (x, y, rot)
                        break
                if best:
                    break
            if best:
                break
        if best:
            courts[ref] = (f.GetLayer(), court(f), any(p.HasHole() for p in f.Pads()))
            print("%s: (%.2f, %.2f) -> (%.2f, %.2f) rot %g" % (ref, ToMM(old.x), ToMM(old.y), ToMM(best[0]), ToMM(best[1]), best[2]))
        else:
            f.SetPosition(old)
            f.SetOrientationDegrees(rot0)
            print("%s: no free spot within %.0f mm" % (ref, radius))
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
