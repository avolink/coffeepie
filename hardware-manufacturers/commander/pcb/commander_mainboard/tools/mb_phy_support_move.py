"""mb_phy_support_move.py SRC DST - mainboard: the Ethernet PHY's strap resistors and three small capacitors leave the
strip north of the PHY (U2).

That strip (top face, y 67.6 .. 70.2) lies over the line side of the four transformers on the bottom face: no via of
a secondary-side net may stand there (2 mm isolation on every layer a via touches), and on the top face it is only
2.6 mm deep between the RJ45's pins and the PHY.  Seventeen two-pad parts stood in it with their ground chained from
pad to pad on the top face - a single-layer puzzle that never closed (the PHY's nets were the bulk of the open links
in the head).  The straps are DC configuration resistors and the capacitors are the extra ones of rails that have
their main decoupling south of the PHY, so they go to the free bottom face south of the PHY (y 76.7 / 78.0), where
vias are allowed and the ground plane is one layer away.  The strip is left to the PHY's top-row pins.

The ground tracks of the top face inside the strip (the old chain) are taken out.  Tracks of the moved parts stay
behind as stubs: route the window anew afterwards (soft), then prune.  seat_part.py REF@x,y afterwards settles each
part on the nearest spot that is really free.
"""
import os
import shutil
import sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

PLACE = [   # ref, x, y (seed), pad that looks north
    ("R97", 57.0, 76.7, "2"), ("R98", 58.2, 76.7, "1"),      # RXD0 strap pair
    ("R99", 59.4, 76.7, "2"), ("R100", 60.6, 76.7, "1"),     # RXD1
    ("R102", 61.8, 76.7, "2"), ("R103", 63.0, 76.7, "1"),    # RXD2
    ("R87", 64.4, 76.7, "1"), ("R90", 65.8, 76.7, "1"),      # RXD3, RXCLK
    ("C106", 67.0, 76.7, "1"),
    ("R76", 59.4, 78.0, "2"), ("R77", 60.6, 78.0, "1"),      # LED0
    ("R78", 61.8, 78.0, "2"), ("R88", 63.2, 78.0, "1"),      # LED2, INTB
    ("R74", 64.6, 78.0, "1"), ("R72", 66.0, 78.0, "1"),      # MAC clock
    ("C113", 67.4, 78.0, "1"), ("C107", 68.6, 78.0, "1"),
]
STRIP = (52.5, 66.9, 70.2, 70.35)       # the old ground chain on the top face


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    pro_path = os.path.splitext(src)[0] + ".kicad_pro"
    pro = open(pro_path, encoding="utf-8").read() if os.path.exists(pro_path) else None
    for ref, x, y, pad in PLACE:
        f = b.FindFootprintByReference(ref)
        if f.GetLayer() != pcbnew.B_Cu:
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        best = None
        for rot in (0, 90, 180, 270):
            f.SetOrientationDegrees(rot)
            p = [q for q in f.Pads() if q.GetNumber() == pad][0].GetPosition()
            score = -(ToMM(p.y) - y)
            if best is None or score > best[0]:
                best = (score, rot)
        f.SetOrientationDegrees(best[1])
        print("%-5s B (%.2f, %.2f) rot %3d  %s" % (ref, x, y, best[1], "  ".join(
            "%s=%s" % (q.GetNumber(), q.GetNetname()) for q in f.Pads() if q.GetNumber())))
    doomed = []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T or t.GetNetname() != "GND" or t.GetLayer() != pcbnew.F_Cu:
            continue
        mx, my = ToMM(t.GetStart().x + t.GetEnd().x) / 2, ToMM(t.GetStart().y + t.GetEnd().y) / 2
        if STRIP[0] <= mx <= STRIP[2] and STRIP[1] <= my <= STRIP[3]:
            doomed.append(t)
    n = len(doomed)
    for t in doomed:
        b.Remove(t)
    print(n, "ground tracks of the old chain taken out")
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("written", dst)


main()
