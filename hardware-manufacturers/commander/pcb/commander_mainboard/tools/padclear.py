"""padclear.py SRC DST REF [REF ...] [--cl 0.15]   (KiCad's Python)

After a part was moved: takes out the tracks (on the pad's layers) and vias of OTHER nets that touch its pads or come
nearer than --cl, so that no old copper shorts to the new position.  One pass, whole items only (no fragments are
left touching the pads - see clear_around.py for why).  The router lays the removed links again."""
import math
import os
import shutil
import sys
import pcbnew
from pcbnew import ToMM


def seg_rect(ax, ay, bx, by, r):
    """distance from the segment a-b to the rectangle r = (x0, y0, x1, y1) (0 if it touches)"""
    n = max(1, int(math.hypot(bx - ax, by - ay) / 0.02))
    best = 1e9
    for k in range(n + 1):
        x, y = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
        dx = max(r[0] - x, 0.0, x - r[2])
        dy = max(r[1] - y, 0.0, y - r[3])
        best = min(best, math.hypot(dx, dy))
        if best == 0.0:
            break
    return best


def main():
    src, dst = sys.argv[1:3]
    args = sys.argv[3:]
    cl = float(args[args.index("--cl") + 1]) if "--cl" in args else 0.15
    refs = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--cl")]
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    pads = []
    for ref in refs:
        f = b.FindFootprintByReference(ref)
        for p in f.Pads():
            if not p.GetNumber():
                continue
            bb = p.GetBoundingBox()
            pads.append((ref, p.GetNumber(), p.GetNetname(), [l for l in p.GetLayerSet().CuStack()],
                         (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))))
    doomed, why = [], []
    for t in b.GetTracks():
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y, r = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
            for (ref, num, pn, layers, rect) in pads:
                if pn != n and seg_rect(x, y, x, y, rect) < r + cl:
                    doomed.append(t)
                    why.append("%s via (%.2f, %.2f) at %s.%s" % (n, x, y, ref, num))
                    break
        else:
            ax, ay, bx, by = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
            hw = ToMM(t.GetWidth()) / 2
            lay = t.GetLayer()
            for (ref, num, pn, layers, rect) in pads:
                if pn == n or lay not in layers:
                    continue
                if max(ax, bx) < rect[0] - 1 or min(ax, bx) > rect[2] + 1 or max(ay, by) < rect[1] - 1 or min(ay, by) > rect[3] + 1:
                    continue
                if seg_rect(ax, ay, bx, by, rect) < hw + cl:
                    doomed.append(t)
                    why.append("%s track at %s.%s" % (n, ref, num))
                    break
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
    print("padclear: %d tracks / vias taken out -> %s" % (n, dst))
    for w in sorted(set(why)):
        print("  ", w)


main()
