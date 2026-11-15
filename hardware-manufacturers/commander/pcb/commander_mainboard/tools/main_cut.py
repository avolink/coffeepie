#!/usr/bin/env python
"""main_cut.py SRC DST - the mainboard without its bay strip (branch m2-hub), from the routed board SRC.

Run with KiCad's Python.  Everything else on the board stays as it is (hand placement, routing, pours).  Changes:
  - the strip's parts (they are on the hub board now, tools/hub_board.py) and its copper go;
  - outline: the column plus a small tab (to board x 73.9) under socket J41, the strip is gone;
  - J41, the M.2 Key M socket for the hub board, on the top face at the column's right edge: its back row (the
    signals) starts at board x 64.28, right where the low-voltage corridor starts (the PoE primary zone ends at 62.3);
  - the two parts that bridge the isolation barrier inside the socket's place (optocoupler U31, Y capacitor C518)
    move down the barrier, still bridging it; their tracks go for the router to redo;
  - C601 / C602 (SuperSpeed coupling, now on this board) go on the bottom face beside the socket's pins 5 / 7;
  - copper on the top face inside the socket's courtyard goes (the router reconnects to the socket).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pcbnew                               # noqa: E402
from pcbnew import FromMM, ToMM             # noqa: E402

import cpmodel                              # noqa: E402
import hub_link                             # noqa: E402
from gen_schematic import uid               # noqa: E402

X_FACE = 73.0
YC = 92.16
TAB_X = 73.9
SOCKET_BOX = (63.9, YC - 11.35, TAB_X, YC + 11.35)     # courtyard (+0.1) of J41 on the top face
UNDER_SOCKET = (65.9, YC - 10.4, 70.0, YC + 10.4)      # between its two pad rows, left of the posts: fan-out vias


def P(x, y):
    return pcbnew.VECTOR2I(FromMM(x), FromMM(y))


def rect_of(bb):
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def crt(fp):
    poly = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    return rect_of(poly.BBox()) if poly.OutlineCount() else rect_of(fp.GetBoundingBox(False))


def overlap(a, b, m=0.0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


def seg(b, a, c):
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(FromMM(0.05))
    s.SetStart(P(*a))
    s.SetEnd(P(*c))
    b.Add(s)


def arc(b, a, m, c):
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_ARC)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(FromMM(0.05))
    s.SetArcGeometry(P(*a), P(*m), P(*c))
    b.Add(s)
    return s


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = cpmodel.load()
    nets_main = set(d.nets())
    b = pcbnew.LoadBoard(src)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    drop = [fp for r, fp in fps.items()
            if r not in d.comps and (ToMM(fp.GetPosition().x) > 70.5 or r[:1] in "JUCRLDYQ" and r[1:].isdigit())]
    print("footprints to remove:", len(drop), " (model parts missing on the board: %s)"
          % sorted(r for r in d.comps if r not in fps and r != "J41"))

    def net(name):
        n = b.FindNet(name)
        if n is None:
            n = pcbnew.NETINFO_ITEM(b, name)
            b.Add(n)
        return n

    # ---- J41 ----
    j41 = pcbnew.FootprintLoad(os.path.join(cpmodel.ROOT, "lib", "commander.pretty"), "M2_Socket_KeyM_LOTES_APCI0146")
    j41.SetReference("J41")
    j41.SetValue("M2_SOCKET_M")
    b.Add(j41)
    j41.SetPosition(P(X_FACE, YC))
    j41.SetOrientationDegrees(90)
    for p in j41.Pads():
        if p.GetNumber() == "MP":
            p.SetNet(net("GND"))
        elif p.GetNumber():
            p.SetNet(net(hub_link.PINS[int(p.GetNumber())]))
    p1 = [p for p in j41.Pads() if p.GetNumber() == "1"][0]
    print("J41 pad 1 at (%.2f, %.2f)" % (ToMM(p1.GetPosition().x), ToMM(p1.GetPosition().y)))
    c = d.comps["J41"]
    j41.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
    for r in ("C601", "C602"):
        c = d.comps[r]
        fps[r].SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
    # every other part keeps its path; the parts of the old usb2_hub sheet that stayed (keyboard port) move sheet
    for r in ("J20", "U51", "R706", "R707", "F1", "C713"):
        c = d.comps[r]
        fps[r].SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))

    # ---- parts in the socket's place; C601 / C602 beside its pins 5 / 7 ----
    keep_fps = [fp for r, fp in fps.items() if fp not in drop]
    vacated = []

    def free(fp, r, extra=()):
        others = [crt(o) for o in keep_fps if o is not fp and o.IsFlipped() == fp.IsFlipped()] + list(extra)
        return not any(overlap(r, o, 0.1) for o in others)

    socket = rect_of(j41.GetCourtyard(pcbnew.F_CrtYd).BBox())
    # Barrier parts, placed by hand (board mm, pad-pair centres): both keep their orientation and still straddle the
    # barrier.  U31 (primary pins 3 / 4 on the left) goes below the clamp diode D42, where the primary zone ends
    # (its primary pads reach 0.7 mm past the zone's lower edge; route.py's CP_LINK areas cover them).  C518
    # (pad 1 POE_RTN, pad 2 GND) goes into the bump of the primary area beside the transformer's primary pins.
    # (D42, the clamp diode above U31's new place, goes up 0.35 mm to make room)
    for r, (cx, cy) in (("D42", (59.40, 108.70)), ("U31", (63.10, 111.80)), ("C518", (65.095, 106.30))):
        fp = fps[r]
        vacated.append(crt(fp))
        pads = list(fp.Pads())
        ox = sum(ToMM(p.GetPosition().x) for p in pads) / len(pads)
        oy = sum(ToMM(p.GetPosition().y) for p in pads) / len(pads)
        pos = fp.GetPosition()
        fp.SetPosition(P(ToMM(pos.x) + cx - ox, ToMM(pos.y) + cy - oy))
        n = crt(fp)
        hit = [o.GetReference() for o in keep_fps if o is not fp and o.IsFlipped() == fp.IsFlipped() and overlap(n, crt(o), 0.0)]
        print("moved %s to (%.2f, %.2f)%s" % (r, cx, cy, "  - courtyard overlaps %s" % hit if hit else ""))
    # C518's ground pad: a short track to the right and a via there, 2 mm clear of the transformer's primary pads
    # on the bottom face (the planes In1 / In4 reach this point: their cut-out ends at x 65.9 in this band)
    gpad = [p for p in fps["C518"].Pads() if p.GetNetname() == "GND"][0]
    gx, gy = ToMM(gpad.GetPosition().x), ToMM(gpad.GetPosition().y)
    segs = []                                   # (x1, y1, x2, y2, half width) of every track, and vias as points
    for t in b.GetTracks():
        if t.GetNetname() == "GND":
            continue
        w = ToMM(t.GetWidth(pcbnew.F_Cu)) if t.GetClass() == "PCB_VIA" else ToMM(t.GetWidth())
        segs.append((ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), w / 2))
    pri = [rect_of(p.GetBoundingBox()) for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname().startswith("POE_")]

    def dseg(px, py, s_):
        x1, y1, x2, y2, _ = s_
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
        return ((px - x1 - u * dx) ** 2 + (py - y1 - u * dy) ** 2) ** 0.5

    def rgap(px, py, r_):
        return (max(r_[0] - px, px - r_[2], 0) ** 2 + max(r_[1] - py, py - r_[3], 0) ** 2) ** 0.5

    best = None
    for i in range(0, 31):
        for j in range(-25, 26):
            vx, vy = 66.8 + i * 0.1, gy + j * 0.1
            if vx > 69.3:
                continue
            if any(dseg(vx, vy, s_) < 0.3 + s_[4] + 0.2 for s_ in segs):
                continue
            if any(rgap(vx, vy, r_) < 0.3 + 2.1 for r_ in pri):
                continue
            cost = abs(vx - gx) + abs(vy - gy)
            if best is None or cost < best[0]:
                best = (cost, vx, vy)
    if best is None:
        raise SystemExit("no place for C518's ground via")
    vx, vy = best[1], best[2]
    print("C518 ground via at (%.2f, %.2f)" % (vx, vy))
    tr = pcbnew.PCB_TRACK(b)
    tr.SetStart(P(gx, gy))
    tr.SetEnd(P(vx, vy))
    tr.SetWidth(FromMM(0.4))
    tr.SetLayer(pcbnew.F_Cu)
    tr.SetNet(net("GND"))
    b.Add(tr)
    via = pcbnew.PCB_VIA(b)
    via.SetPosition(P(vx, vy))
    via.SetWidth(FromMM(0.6))
    via.SetDrill(FromMM(0.3))
    via.SetNet(net("GND"))
    b.Add(via)
    new_items = {tr.m_Uuid.AsString(), via.m_Uuid.AsString()}
    for r, (x, y) in (("C601", (67.6, YC + 8.25)), ("C602", (67.6, YC + 6.9))):
        fp = fps[r]
        vacated.append(crt(fp))
        if not fp.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetOrientationDegrees(0)
        fp.SetPosition(P(x, y))
        print("%s on the bottom face at (%.2f, %.2f)" % (r, x, y))

    # ---- copper ----
    gone = []
    moved_now = [crt(fps[r]) for r in ("U31", "C518", "D42", "C601", "C602")]
    # low-voltage copper that the moved barrier parts' primary pads came close to (2 mm rule + margin)
    pri_pads = [rect_of(p.GetBoundingBox()) for r in ("U31", "C518", "D42") for p in fps[r].Pads()
                if p.GetNetname().startswith("POE_")]
    # J41's two locating posts are unplated holes through every layer: nothing may pass them
    posts = [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), ToMM(p.GetDrillSize().x) / 2)
             for p in j41.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in new_items:
            continue
        w = ToMM(t.GetWidth(pcbnew.F_Cu)) if t.GetClass() == "PCB_VIA" else ToMM(t.GetWidth())
        s_ = (ToMM(t.GetStart().x), ToMM(t.GetStart().y), ToMM(t.GetEnd().x), ToMM(t.GetEnd().y), w / 2)
        if any(dseg(px, py, s_) < pr + w / 2 + 0.35 for px, py, pr in posts):
            gone.append(t)
            continue
        pts = [t.GetStart(), t.GetEnd()]
        xs = [ToMM(p_.x) for p_ in pts]
        ys = [ToMM(p_.y) for p_ in pts]
        r = (min(xs), min(ys), max(xs), max(ys))
        is_via = t.GetClass() == "PCB_VIA"
        if max(xs) > 70.0 or t.GetNetname() not in nets_main:
            gone.append(t)
        elif (is_via or t.GetLayer() == pcbnew.F_Cu) and overlap(r, SOCKET_BOX, 0.2):
            gone.append(t)
        elif overlap(r, UNDER_SOCKET, 0.0):
            gone.append(t)                       # every layer under the socket body: room for the signal fan-out
        elif any(overlap(r, v, 0.3) for v in vacated):
            gone.append(t)
        elif not t.GetNetname().startswith("POE_") and t.GetNetname() != "GND" and any(overlap(r, v, 2.4) for v in pri_pads):
            gone.append(t)
        elif (is_via or t.GetLayer() == pcbnew.F_Cu) and any(overlap(r, v, 0.25) for v in moved_now[:3]):
            gone.append(t)                       # top-face copper (and vias) under the new places of U31 / C518 / D42
        elif any(overlap(r, v, 0.25) for v in moved_now[3:]) and (is_via or t.GetLayer() == pcbnew.B_Cu):
            gone.append(t)                       # bottom-face copper (and vias) under C601 / C602
    print("tracks / vias removed:", len(gone))

    # ---- outline: column + tab ----
    for dr in list(b.GetDrawings()):
        if dr.GetLayer() != pcbnew.Edge_Cuts:
            if ToMM(dr.GetBoundingBox().GetLeft()) > 74.0:
                gone.append(dr)
            continue
        s, e = dr.GetStart(), dr.GetEnd()
        xs, ys = (ToMM(s.x), ToMM(e.x)), (ToMM(s.y), ToMM(e.y))
        if max(xs) > 70.5:                       # strip edges and the two inner corners (the column edge is x = 70)
            gone.append(dr)
            continue
        if dr.GetShape() == pcbnew.SHAPE_T_SEGMENT and abs(xs[0] - 70.0) < 0.01 and abs(xs[1] - 70.0) < 0.01:
            # move only the end at the strip, by an exact 1 mm (the far end stays bit-identical: it meets an arc)
            # (GetStart / GetEnd hand back live references: copy the numbers before setting anything)
            for get, set_ in ((dr.GetStart, dr.SetStart), (dr.GetEnd, dr.SetEnd)):
                px, py = int(get().x), int(get().y)
                if abs(ToMM(py) - 80.3) < 0.05:            # column edge above the strip: stop 1 mm earlier
                    top_pt = pcbnew.VECTOR2I(px, py - FromMM(1.0))
                    set_(pcbnew.VECTOR2I(px, py - FromMM(1.0)))
                elif abs(ToMM(py) - 104.02) < 0.05:        # column edge below the strip: start 1 mm later
                    bot_pt = pcbnew.VECTOR2I(px, py + FromMM(1.0))
                    set_(pcbnew.VECTOR2I(px, py + FromMM(1.0)))
    # the tab: every piece starts exactly where the previous one ended (arcs are built first, and the straight
    # pieces take the arcs' own end points, so no nanometre gaps are left for KiCad to call an invalid outline)
    k = 0.70711
    x0, y0 = ToMM(top_pt.x), ToMM(top_pt.y)
    yb = ToMM(bot_pt.y)
    a1 = arc(b, (x0, y0), (x0 + 1.0 - k, y0 + k), (x0 + 1.0, y0 + 1.0))
    a2 = arc(b, (TAB_X - 0.5, y0 + 1.0), (TAB_X - 0.5 + 0.5 * k, y0 + 1.5 - 0.5 * k), (TAB_X, y0 + 1.5))
    a3 = arc(b, (TAB_X, yb - 1.5), (TAB_X - 0.5 + 0.5 * k, yb - 1.5 + 0.5 * k), (TAB_X - 0.5, yb - 1.0))
    a4 = arc(b, (x0 + 1.0, yb - 1.0), (x0 + 1.0 - k, yb - k), (x0, yb))
    # (never call SetStart / SetEnd on an arc afterwards: KiCad rebuilds it; top_pt / bot_pt are whole nanometres,
    #  so P(ToMM(..)) gives back exactly the same points for the arcs' free ends)
    #  KiCad also stores arcs counter-clockwise, swapping start and end, so the straight pieces are built from the same
    #  millimetre values as the arcs' ends, not from GetStart / GetEnd)
    seg(b, (x0 + 1.0, y0 + 1.0), (TAB_X - 0.5, y0 + 1.0))
    seg(b, (TAB_X, y0 + 1.5), (TAB_X, yb - 1.5))
    seg(b, (TAB_X - 0.5, yb - 1.0), (x0 + 1.0, yb - 1.0))
    del a1, a2, a3, a4

    # ---- zones: clip to the column and tab ----
    clip = pcbnew.SHAPE_POLY_SET()
    clip.NewOutline()
    # (chamfered at the tab's two inner corners, where the 1 mm fillets of the outline are)
    for x, y in ((30.0, 30.0), (70.0, 30.0), (70.0, 79.0), (71.3, 80.3), (TAB_X, 80.3), (TAB_X, 104.02),
                 (71.3, 104.02), (70.0, 105.32), (70.0, 200.0), (30.0, 200.0)):
        clip.Append(FromMM(x), FromMM(y))
    for z in list(b.Zones()):
        if not z.GetIsRuleArea() and z.GetNetname() not in nets_main:
            gone.append(z)
            continue
        if ToMM(z.GetBoundingBox().GetLeft()) > 72.0:
            gone.append(z)
            continue
        z.Outline().BooleanIntersection(clip)
        if z.Outline().OutlineCount() == 0:
            gone.append(z)

    for it in gone:
        b.Remove(it)
    for fp in drop:
        b.Remove(fp)
    pcbnew.SaveBoard(dst, b)
    print("removed %d footprints, wrote %s" % (len(drop), dst))


if __name__ == "__main__":
    main()
