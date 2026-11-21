"""via_swap.py SRC DST NET --del x,y [--del x,y ...] --add x,y,dia,drill [...]   (KiCad's Python)

Takes out the vias of NET standing at the --del points (within 0.05 mm) and sets new ones at the --add points;
tracks / vias of OTHER nets nearer than 0.15 mm to a new via go (one pass, whole items; the router lays them again).
Used for the Ethernet PHY's thermal vias: two of the three 0.6 mm ones stood between the transformers' secondary
pads and the common-mode chokes on the bottom face, where the MDI links have to pass."""
import math
import os
import shutil
import sys
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I


def main():
    src, dst, net = sys.argv[1:4]
    a = sys.argv[4:]
    dels = [tuple(float(v) for v in a[i + 1].split(",")) for i in range(len(a)) if a[i] == "--del"]
    adds = [tuple(float(v) for v in a[i + 1].split(",")) for i in range(len(a)) if a[i] == "--add"]
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    nc = b.FindNet(net)
    doomed, notes = [], []
    for t in b.GetTracks():
        n = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y, r = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
            if n == net and any(math.hypot(x - dx, y - dy) < 0.05 for (dx, dy) in dels):
                doomed.append(t)
                notes.append("%s via (%.2f, %.2f) out" % (n, x, y))
            elif n != net and any(math.hypot(x - ax, y - ay) < r + d / 2 + 0.15 for (ax, ay, d, _h) in adds):
                doomed.append(t)
                notes.append("%s via (%.2f, %.2f) in the way" % (n, x, y))
        elif n != net:
            ax0, ay0, bx0, by0 = ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
            hw = ToMM(t.GetWidth()) / 2
            for (ax, ay, d, _h) in adds:
                vx, vy = bx0 - ax0, by0 - ay0
                l2 = vx * vx + vy * vy
                k = max(0.0, min(1.0, ((ax - ax0) * vx + (ay - ay0) * vy) / l2)) if l2 else 0.0
                if math.hypot(ax - ax0 - k * vx, ay - ay0 - k * vy) < hw + d / 2 + 0.15:
                    doomed.append(t)
                    notes.append("%s track on %s in the way" % (n, b.GetLayerName(t.GetLayer())))
                    break
    for (ax, ay, d, h) in adds:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(VECTOR2I(FromMM(ax), FromMM(ay)))
        v.SetWidth(pcbnew.F_Cu, FromMM(d))
        v.SetDrill(FromMM(h))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nc)
        b.Add(v)
        notes.append("%s via (%.2f, %.2f) %.2f / %.2f in" % (net, ax, ay, d, h))
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
    for s in notes:
        print("  ", s)
    print("written", dst)


main()
