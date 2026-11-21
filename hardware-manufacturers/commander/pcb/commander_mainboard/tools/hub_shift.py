#!/usr/bin/env python
"""hub_shift.py SRC DST DX - lengthen the hub board at its card end by moving the card edge DX along x (DX < 0: left).

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/hub_shift.py ../commander_hub/commander_hub.kicad_pcb build/x.kicad_pcb -4

Run with KiCad's Python.  Goes with tools/j41_shift.py (the mainboard's socket J41 moved by the same DX): the hub keeps
the mainboard's coordinates, so its card edge must follow the socket.  The right end stays where it is.
  - J90 (the card-edge fingers, whose footprint carries the tongue's outline) moves by DX;
  - each finger's straight stub (tools/hub_board.py) keeps its far end, where the routing joins it, and starts at the
    finger's new place: the stubs get |DX| longer, on their own face, and nothing is left open;
  - the body's left edge (the two short pieces beside the tongue) moves by DX and the top / bottom edges reach it;
  - the zones' left edge (x 68.5, just left of the tongue) moves by DX so that the planes still cover the tongue.
"""
import sys

import pcbnew
from pcbnew import FromMM, ToMM

X_FACE, Y_TOP, Y_BOT, ZONE_X = 73.0, 81.30, 103.02, 68.5


def main():
    src, dst, dx = sys.argv[1], sys.argv[2], float(sys.argv[3])
    b = pcbnew.LoadBoard(src)
    j90 = b.FindFootprintByReference("J90")
    x0 = ToMM(j90.GetPosition().x)
    if abs(x0 - X_FACE) > 0.01:
        raise SystemExit("J90 is at x %.3f, not %.3f: already moved?" % (x0, X_FACE))
    old = {}                                    # pad -> (old box, new centre)
    for p in j90.Pads():
        bb = p.GetBoundingBox()
        old[p.GetNumber() + p.GetLayerName()] = ((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()), p)
    j90.SetPosition(pcbnew.VECTOR2I(FromMM(X_FACE + dx), j90.GetPosition().y))

    # ---- stubs: the end on the old finger goes to the new finger ----
    n = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            continue
        s = (int(t.GetStart().x), int(t.GetStart().y))
        e = (int(t.GetEnd().x), int(t.GetEnd().y))
        for (l, tp, r, bt), p in old.values():
            if p.GetNetCode() != t.GetNetCode() or not p.IsOnLayer(t.GetLayer()):
                continue
            pos = p.GetPosition()
            new = pcbnew.VECTOR2I(int(pos.x), int(pos.y))
            if l <= s[0] <= r and tp <= s[1] <= bt:
                t.SetStart(new)
                n += 1
                break
            if l <= e[0] <= r and tp <= e[1] <= bt:
                t.SetEnd(new)
                n += 1
                break
    print("J90 at x %.3f; %d finger stubs lengthened by %.2f mm" % (X_FACE + dx, n, -dx))

    # ---- outline ----
    nx = FromMM(X_FACE + dx)
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts or d.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        s = (int(d.GetStart().x), int(d.GetStart().y))
        e = (int(d.GetEnd().x), int(d.GetEnd().y))
        for pt, set_ in ((s, d.SetStart), (e, d.SetEnd)):
            if abs(ToMM(pt[0]) - X_FACE) < 0.005 and Y_TOP - 0.01 <= ToMM(pt[1]) <= Y_BOT + 0.01:
                set_(pcbnew.VECTOR2I(nx, pt[1]))
    print("outline: body's left edge at x %.3f" % (X_FACE + dx))

    # ---- zones ----
    for z in b.Zones():
        o = z.Outline()
        k_ = 0
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            for k in range(ch.PointCount()):
                pt = ch.CPoint(k)
                if abs(ToMM(pt.x) - ZONE_X) < 0.005:
                    ch.SetPoint(k, pcbnew.VECTOR2I(FromMM(ZONE_X + dx), int(pt.y)))
                    k_ += 1
        if k_:
            print("zone %s on %s: left edge to x %.2f" % (z.GetNetname(), b.GetLayerName(z.GetFirstLayer()), ZONE_X + dx))
    pcbnew.SaveBoard(dst, b)
    print("wrote", dst)


if __name__ == "__main__":
    main()
