"""hub_support_move.py SRC DST - hub board: the USB5744's support parts go where they belong.

They came over from the strip in a grid on the bottom face under the microSD slot, 25-35 mm from the hub controller
U40 and on the far side of bay 1: twelve decoupling capacitors, the crystal's load capacitors, both regulators'
feedback dividers, the strap resistors, the upstream pair's coupling capacitors.  Every one of their nets had to cross
bay 1's break-out area (some twice), which is what kept the left end from routing - and a decoupling capacitor 30 mm
from its pin does nothing.  This puts each one next to the pin it serves (bottom face under / beside U40, beside the
crystal Y40 and the regulators U41 / U42; the two coupling capacitors on the top face at the card edge).  Tracks are
not touched: route the left end anew afterwards (it is emptied first).  The reset parts R608 / R609 / C607 stay.

Each entry: ref, x, y, face, pad, side - the pad named ends up on that side (N / S / E / W) of the part's centre.
"""
import os
import shutil
import sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

PLACE = [
    # decoupling, top row of U40 (pins 55, 49, 44, 43)
    ("C611", 73.20, 83.10, "B", "1", "N"), ("C620", 75.70, 83.10, "B", "1", "N"),
    ("C610", 77.30, 83.10, "B", "1", "N"), ("C619", 78.40, 83.10, "B", "1", "N"),
    # left column (pins 5, 12)
    ("C613", 72.60, 85.40, "B", "1", "W"), ("C614", 72.60, 88.20, "B", "1", "W"),
    # bottom row (pins 15, 16, 21, 28)
    ("C615", 72.60, 90.10, "B", "1", "N"), ("C608", 73.70, 90.10, "B", "1", "N"),
    ("C616", 75.40, 90.10, "B", "1", "N"), ("C617", 78.45, 90.10, "B", "1", "N"),
    # right column (pins 33, 31)
    ("C618", 79.85, 87.30, "B", "1", "W"), ("C609", 79.85, 88.40, "B", "1", "W"),
    # 1.2 V regulator U42's feedback divider, below it
    ("R613", 76.90, 88.60, "B", "1", "E"), ("R612", 76.90, 89.65, "B", "2", "E"),
    # straps and the (unpopulated) SMBus links, beside pins 38..41
    ("R602", 79.60, 83.00, "B", "1", "S"), ("R603", 81.70, 83.00, "B", "1", "S"),
    ("R607", 79.60, 85.20, "B", "2", "N"), ("R606", 81.70, 85.20, "B", "2", "N"),
    # 3.3 V regulator U41's feedback divider, the VBUS-detect divider, the crystal's load capacitors
    ("R610", 79.20, 92.65, "B", "2", "E"), ("R611", 79.20, 93.70, "B", "1", "E"),
    ("R605", 81.30, 92.65, "B", "1", "W"), ("R604", 81.30, 93.70, "B", "2", "W"),
    ("C605", 79.60, 94.75, "B", "1", "W"), ("C606", 81.90, 99.43, "B", "1", "E"),
    # upstream SuperSpeed TX coupling capacitors, top face, at the card edge's pads 13 / 11
    ("C603", 74.00, 98.13, "F", "2", "W"), ("C604", 74.00, 99.18, "F", "2", "W"),
]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    pro_path = os.path.splitext(src)[0] + ".kicad_pro"
    pro = open(pro_path, encoding="utf-8").read() if os.path.exists(pro_path) else None
    for ref, x, y, face, pad, side in PLACE:
        f = b.FindFootprintByReference(ref)
        want = pcbnew.F_Cu if face == "F" else pcbnew.B_Cu
        if f.GetLayer() != want:
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        f.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
        best = None
        for rot in (0, 90, 180, 270):
            f.SetOrientationDegrees(rot)
            p = [q for q in f.Pads() if q.GetNumber() == pad][0].GetPosition()
            dx, dy = ToMM(p.x) - x, ToMM(p.y) - y
            score = {"N": -dy, "S": dy, "E": dx, "W": -dx}[side]
            if best is None or score > best[0]:
                best = (score, rot)
        f.SetOrientationDegrees(best[1])
        print("%-5s %-9s %s (%.2f, %.2f) rot %3d  %s" % (ref, f.GetValue()[:9], face, x, y, best[1], "  ".join(
            "%s=%s(%.2f,%.2f)" % (q.GetNumber(), q.GetNetname(), ToMM(q.GetPosition().x), ToMM(q.GetPosition().y)) for q in f.Pads())))
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    print("written", dst)


main()
