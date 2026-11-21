#!/usr/bin/env python
"""hub_extend.py SRC DST DX   (KiCad's Python; DX < 0: the card end moves left, the board gets |DX| longer)

Lengthens the ROUTED hub board at its card end without touching the routing: the M.2 card-edge footprint J90 (fingers
and tongue outline) moves by DX, and every finger gets a straight track from its new place back over the place it
had - the copper that was the finger stays as a track of the finger's width, so everything that joined the old finger
still joins the net, and nothing else moves.  (tools/hub_shift.py, used for the first 4 mm, stretches the fingers'
own stubs; after the router's work the fingers are joined in too many ways for that.)

  - fingers: one track per finger and face, 0.35 mm over the old finger, 0.35 mm (ground / 5 V) or 0.20 mm (signals)
    over the new stretch;
  - outline: the body's left edge (the two short steps beside the tongue) moves by DX, top / bottom edges follow;
  - zones: the planes' left edge (just left of the old tongue tip) moves by DX, so they cover the new stretch.

Why: in the chassis the mainboard stands 4.98 mm further left of the hub than the two boards' common coordinates
assumed (the hub's nine bays have to stay on the Framework cards); with 5 mm more tongue the card sits in J41 to its
full depth.  The hub's page coordinates are now 5 mm off the mainboard's at the socket."""
import os
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

WIDE = ("GND", "VCC5V_BUS")


def main():
    src, dst, dx = sys.argv[1], sys.argv[2], float(sys.argv[3])
    b = pcbnew.LoadBoard(src)
    pro = os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read() if os.path.exists(pro) else None
    j90 = b.FindFootprintByReference("J90")
    x_face = ToMM(j90.GetPosition().x)
    fingers = []                                # (net code, layer, y, old left, old right, old centre x, width across)
    for p in j90.Pads():
        if not p.GetNetCode():
            continue
        bb = p.GetBoundingBox()
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(lay):
                fingers.append((p.GetNetCode(), p.GetNetname(), lay, ToMM(p.GetPosition().y), ToMM(bb.GetLeft()), ToMM(bb.GetRight()),
                                ToMM(p.GetPosition().x), ToMM(bb.GetBottom() - bb.GetTop())))
    zone_x = min(ToMM(z.Outline().BBox().GetLeft()) for z in b.Zones() if not z.GetIsRuleArea())
    j90.SetPosition(VECTOR2I(FromMM(x_face + dx), j90.GetPosition().y))

    def track(net, lay, x0, x1, y, w):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(VECTOR2I(FromMM(x0), FromMM(y)))
        t.SetEnd(VECTOR2I(FromMM(x1), FromMM(y)))
        t.SetWidth(FromMM(w))
        t.SetLayer(lay)
        t.SetNetCode(net)
        b.Add(t)
    n = 0
    for (net, name, lay, y, left, right, cx, across) in fingers:
        w = min(across, 0.35)
        # over the old finger: the same copper, as a track (round ends kept inside the old pad)
        track(net, lay, left + w / 2, right - w / 2, y, w)
        # the new stretch: from the finger's new centre to the old finger
        track(net, lay, cx + dx, left + w / 2, y, w if name in WIDE else 0.20)
        n += 1
    print("J90 at x %.3f (was %.3f); %d fingers carried over by %.2f mm" % (x_face + dx, x_face, n, -dx))
    nx = FromMM(x_face + dx)
    k = 0
    for d in b.GetDrawings():
        if d.GetLayer() != pcbnew.Edge_Cuts or d.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        for pt, set_ in ((d.GetStart(), d.SetStart), (d.GetEnd(), d.SetEnd)):
            if abs(ToMM(pt.x) - x_face) < 0.005:
                set_(VECTOR2I(nx, int(pt.y)))
                k += 1
    print("outline: %d points of the body's left edge to x %.3f" % (k, x_face + dx))
    for z in b.Zones():
        o = z.Outline()
        m = 0
        for i in range(o.OutlineCount()):
            ch = o.Outline(i)
            for q in range(ch.PointCount()):
                pt = ch.CPoint(q)
                if abs(ToMM(pt.x) - zone_x) < 0.005:
                    ch.SetPoint(q, VECTOR2I(FromMM(zone_x + dx), int(pt.y)))
                    m += 1
        if m:
            z.UnFill()
            print("zone %s on %s: left edge to x %.2f" % (z.GetNetname(), b.GetLayerName(z.GetFirstLayer()), zone_x + dx))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    stem = os.path.splitext(dst)[0]
    if pro_text is not None:
        open(stem + ".kicad_pro", "w", encoding="utf-8", newline="").write(pro_text)
    dru = os.path.splitext(src)[0] + ".kicad_dru"
    if os.path.exists(dru) and os.path.abspath(dru) != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(dru, stem + ".kicad_dru")
    e = b.GetBoardEdgesBoundingBox()
    print("outline x %.2f .. %.2f; wrote %s" % (ToMM(e.GetLeft()), ToMM(e.GetRight()), dst))


if __name__ == "__main__":
    main()
