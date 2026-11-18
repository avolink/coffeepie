#!/usr/bin/env python
"""j41_shift.py SRC DST DX - move the hub socket J41 along x on the mainboard (branch m2-hub), on a copy.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/j41_shift.py commander_mainboard.kicad_pcb build/x.kicad_pcb -4

Run with KiCad's Python.  The positions are absolute: J41 goes to main_cut.py's place (front face at board x 73.0,
centre line y 92.16) plus DX, and C601 / C602 (SuperSpeed coupling, bottom face beside pins 5 / 7) with it, whatever
was done to them by hand before.  Then:
  - outline: the tab under the socket (to x 73.9) moves with it; when the moved tab no longer reaches past the
    column's edge (x 70) it goes and the column edge runs straight through (only that case is handled);
  - zones: clipped to the new outline; the planes' cut-out round the PoE primary (In1 / In4 GND hole, In3 5 V edge)
    has its right-hand edge at x 64.2 along the socket (y up to 102.65, where the transformer's primary row starts):
    that edge moves by DX too, so that the socket's pad rows keep their planes underneath;
  - copper: the J41 signal nets (and C601 / C602's) lose everything in the socket's neighbourhood on every layer;
    every other net loses its top-face copper and vias inside the socket's courtyard, its copper on every layer
    under the socket body (room for the fan-out) and round the locating posts, and bottom-face copper under
    C601 / C602.  tools/j41_fanout.py and route.py (CP_LINK=1 CP_REGIONS=link) put it back.
Nothing else on the board is touched.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew                               # noqa: E402
from pcbnew import FromMM, ToMM             # noqa: E402

X_FACE, YC, TAB_X, COL_EDGE = 73.0, 92.16, 73.9, 70.0
PLANE_EDGE, PLANE_EDGE_Y1 = 64.2, 102.65    # the cut-out's right-hand edge along the socket (board mm)


def P(x, y):
    return pcbnew.VECTOR2I(FromMM(x), FromMM(y))


def overlap(a, b, m=0.0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


def dseg(px, py, s_):
    x1, y1, x2, y2 = s_[:4]
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
    return ((px - x1 - u * dx) ** 2 + (py - y1 - u * dy) ** 2) ** 0.5


def main():
    src, dst, dx = sys.argv[1], sys.argv[2], float(sys.argv[3])
    b = pcbnew.LoadBoard(src)
    tab = TAB_X + dx
    if tab > COL_EDGE + 0.5:
        raise SystemExit("the moved tab still reaches past the column edge: rebuild it as main_cut.py does (not handled)")
    sock_box = (X_FACE - 9.1 + dx, YC - 11.35, tab, YC + 11.35)          # courtyard (+0.1), top face
    under = (X_FACE - 7.1 + dx, YC - 10.4, min(X_FACE - 3.0 + dx, COL_EDGE), YC + 10.4)   # between the rows: fan-out vias
    rip = (X_FACE - 14.5 + dx, YC - 12.7, COL_EDGE, YC + 13.4)             # J41's own signal nets, every layer

    j41 = b.FindFootprintByReference("J41")
    j41.SetPosition(P(X_FACE + dx, YC))
    caps = {}
    for r, (x, y) in (("C601", (67.6 + dx, YC + 8.25)), ("C602", (67.6 + dx, YC + 6.9))):
        fp = b.FindFootprintByReference(r)
        if not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetOrientationDegrees(0)
        fp.SetPosition(P(x, y))
        bb = fp.GetCourtyard(pcbnew.B_CrtYd).BBox()
        caps[r] = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
    print("J41 at (%.3f, %.3f); C601 / C602 at x %.2f" % (X_FACE + dx, YC, 67.6 + dx))
    power = {"GND", "VCC5V_BUS", "VCC_SYS", "VCC3V3_SYS"}
    sig = {p.GetNetname() for p in j41.Pads() if p.GetNetname() and p.GetNetname() not in power}
    for r in ("C601", "C602"):
        sig |= {p.GetNetname() for p in b.FindFootprintByReference(r).Pads() if p.GetNetname() not in power}
    posts = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), ToMM(p.GetDrillSize().x) / 2)
             for p in j41.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]

    # ---- copper: decide everything first, remove last (KiCad's wrappers break after Remove) ----
    gone, lost = [], {}
    for t in b.GetTracks():
        is_via = t.GetClass() == "PCB_VIA"
        w = ToMM(t.GetWidth(pcbnew.F_Cu)) if is_via else ToMM(t.GetWidth())
        s_ = (ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
        r = (min(s_[0], s_[2]) - w / 2, min(s_[1], s_[3]) - w / 2, max(s_[0], s_[2]) + w / 2, max(s_[1], s_[3]) + w / 2)
        n = t.GetNetname()
        why = None
        if n in sig and overlap(r, rip):
            why = "J41 net"
        elif any(dseg(px, py, s_) < pr + w / 2 + 0.35 for px, py, pr in posts):
            why = "post"
        elif (is_via or t.GetLayer() == pcbnew.F_Cu) and overlap(r, sock_box, 0.2):
            why = "socket"
        elif overlap(r, under):
            why = "under socket"
        elif (is_via or t.GetLayer() == pcbnew.B_Cu) and any(overlap(r, c, 0.25) for c in caps.values()):
            why = "C601/C602"
        if why:
            gone.append(t)
            lost.setdefault(why, {}).setdefault(n, 0)
            lost[why][n] += 1
    for why, d in lost.items():
        print("removed (%s): %s" % (why, ", ".join("%s x%d" % kv for kv in sorted(d.items()))))

    # ---- outline: the tab goes, the column edge runs straight ----
    top = bot = None
    for dr in list(b.GetDrawings()):
        if dr.GetLayer() != pcbnew.Edge_Cuts:
            continue
        s, e = dr.GetStart(), dr.GetEnd()
        xs, ys = (ToMM(s.x), ToMM(e.x)), (ToMM(s.y), ToMM(e.y))
        if not (YC - 14 < min(ys) and max(ys) < YC + 14 and max(xs) > COL_EDGE - 0.5):
            continue
        if dr.GetShape() == pcbnew.SHAPE_T_SEGMENT and all(abs(x - COL_EDGE) < 0.01 for x in xs):
            continue                            # (the column edge itself)
        gone.append(dr)
        print("outline: removed %s (%.3f, %.3f) - (%.3f, %.3f)" % (dr.GetShapeStr(), xs[0], ys[0], xs[1], ys[1]))
    for dr in b.GetDrawings():                  # the two column-edge pieces that met the tab's fillets
        if dr.GetLayer() != pcbnew.Edge_Cuts or dr.GetShape() != pcbnew.SHAPE_T_SEGMENT or dr in gone:
            continue
        s, e = dr.GetStart(), dr.GetEnd()
        if abs(ToMM(s.x) - COL_EDGE) > 0.01 or abs(ToMM(e.x) - COL_EDGE) > 0.01:
            continue
        for pt in (s, e):
            if abs(ToMM(pt.y) - (YC - 12.86)) < 0.05:
                top = pcbnew.VECTOR2I(int(pt.x), int(pt.y))
            elif abs(ToMM(pt.y) - (YC + 12.86)) < 0.05:
                bot = pcbnew.VECTOR2I(int(pt.x), int(pt.y))
    if top is None or bot is None:
        raise SystemExit("column edge ends at the tab not found")
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(FromMM(0.05))
    s.SetStart(top)
    s.SetEnd(bot)
    b.Add(s)
    print("outline: column edge x %.2f from y %.3f to %.3f" % (COL_EDGE, ToMM(top.y), ToMM(bot.y)))

    # ---- zones: clip to the column; move the cut-out's right edge along the socket ----
    clip = pcbnew.SHAPE_POLY_SET()
    clip.NewOutline()
    for x, y in ((0.0, 0.0), (COL_EDGE, 0.0), (COL_EDGE, 400.0), (0.0, 400.0)):
        clip.Append(FromMM(x), FromMM(y))
    for z in list(b.Zones()):
        if z.GetIsRuleArea() or ToMM(z.GetBoundingBox().GetRight()) < COL_EDGE + 0.1:
            pass
        else:
            z.Outline().BooleanIntersection(clip)
        if z.GetIsRuleArea() or z.GetNetname() not in ("GND", "VCC5V_BUS"):
            continue
        o = z.Outline()
        moved = 0
        chains = []
        for i in range(o.OutlineCount()):
            chains.append(o.Outline(i))
            chains += [o.Hole(i, h) for h in range(o.HoleCount(i))]
        for ch in chains:
            for k in range(ch.PointCount()):
                pt = ch.CPoint(k)
                if abs(ToMM(pt.x) - PLANE_EDGE) < 0.01 and YC - 15.0 < ToMM(pt.y) <= PLANE_EDGE_Y1 + 0.01:
                    ch.SetPoint(k, pcbnew.VECTOR2I(FromMM(PLANE_EDGE + dx), int(pt.y)))
                    moved += 1
        if moved:
            print("zone %s on %s: %d corner(s) of the cut-out edge moved to x %.2f" % (
                z.GetNetname(), b.GetLayerName(z.GetFirstLayer()), moved, PLANE_EDGE + dx))

    for it in gone:
        b.Remove(it)
    pcbnew.SaveBoard(dst, b)
    print("wrote", dst)


if __name__ == "__main__":
    main()
