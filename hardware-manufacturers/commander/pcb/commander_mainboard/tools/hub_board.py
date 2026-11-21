#!/usr/bin/env python
"""hub_board.py SRC DST - cut the hub board (branch m2-hub) out of the routed mainboard SRC and write it to DST.

Run with KiCad's Python.  The hub board keeps the mainboard's coordinates (so route.py's strip region applies to it
unchanged) and its copper: every footprint of the hub design model (../commander_hub/src/netlist) with its tracks,
vias and pours inside the strip.  What changes:
  - outline: the strip from the socket's front face (board x 73.0) to its far end, plus the M.2 card tongue (J90)
    reaching 4 mm into socket J41 on the mainboard;
  - J90 (card-edge fingers) is added, its pads on the nets of tools/hub_link.py;
  - parts that overlapped the new left end are moved to the nearest free spot to the right (on the bottom face the
    first 1.4 mm are kept clear too: there the hub hangs 0.3 mm over the mainboard's tab and the socket's pads);
  - copper left of the new edge, and copper that touched a moved part, is removed for the router to redo;
  - every footprint gets the symbol path of the hub schematic, the board 0.8 mm thick (6 layers kept for now).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["CP_ROOT"] = os.path.normpath(os.path.join(HERE, "..", "..", "commander_hub"))
sys.path.insert(0, HERE)

import pcbnew                               # noqa: E402
from pcbnew import FromMM, ToMM             # noqa: E402

import cpmodel                              # noqa: E402
import hub_link                             # noqa: E402
from gen_schematic import uid               # noqa: E402

X_FACE = 73.0                     # socket front face = hub body's left edge (board mm)
Y_TOP, Y_BOT = 81.30, 103.02      # strip edges
YC = round((Y_TOP + Y_BOT) / 2, 3)
LIMIT_F, LIMIT_B = X_FACE + 0.4, X_FACE + 1.4      # left limit of courtyards on the top / bottom face
EDGE_CU = X_FACE + 0.3                              # copper to the left edge
WIN = (LIMIT_F, Y_TOP + 0.3, 90.0, Y_BOT - 0.3)     # where moved parts may go


def P(x, y):
    return pcbnew.VECTOR2I(FromMM(x), FromMM(y))


def rect_of(bb):
    return (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))


def crt(fp):
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    poly = fp.GetCourtyard(lay)
    if poly.OutlineCount():
        return rect_of(poly.BBox())
    return rect_of(fp.GetBoundingBox(False))


def overlap(a, b, m=0.0):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = cpmodel.load()
    b = pcbnew.LoadBoard(src)
    keep = set(d.comps)
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    hub_nets = set(d.nets()) | set(hub_link.PINS.values())
    for r, fp in fps.items():                      # mounting holes (not in any netlist) that sit on the strip
        if r.startswith("H") and r[1:].isdigit() and ToMM(fp.GetPosition().x) > 71.0:
            keep.add(r)
    missing = sorted(r for r in d.comps if r not in fps and r != "J90")
    print("hub parts not on the source board:", missing)

    # ---- nets ----
    def net(name):
        n = b.FindNet(name)
        if n is None:
            n = pcbnew.NETINFO_ITEM(b, name)
            b.Add(n)
        return n

    # ---- J90: the card edge ----
    lib = os.path.join(cpmodel.ROOT, "lib", "commander.pretty")
    j90 = pcbnew.FootprintLoad(lib, "M2_CardEdge_KeyM_Tongue")
    j90.SetReference("J90")
    j90.SetValue("M2_EDGE_M")
    b.Add(j90)
    j90.SetPosition(P(X_FACE, YC))
    j90.SetOrientationDegrees(-90)
    for p in j90.Pads():
        p.SetNet(net(hub_link.PINS[int(p.GetNumber())]))
    # every finger gets a straight stub on its own face, away from the mating edge, to x 72.6 (inside the part of
    # the tongue that sits in the socket's slot, where route.py's hub outline lets the router take over); power and
    # ground 0.25 mm, signals 0.15 mm (fingers are 0.5 mm apart on each face)
    stubs = set()
    for p in j90.Pads():
        n_ = hub_link.PINS[int(p.GetNumber())]
        tr = pcbnew.PCB_TRACK(b)
        tr.SetStart(p.GetPosition())
        tr.SetEnd(pcbnew.VECTOR2I(FromMM(72.6), p.GetPosition().y))
        tr.SetWidth(FromMM(0.25 if n_ in ("GND", "VCC5V_BUS", "VCC_SYS", "VCC3V3_SYS") else 0.15))
        tr.SetLayer(pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
        tr.SetNet(net(n_))
        b.Add(tr)
        stubs.add(tr.m_Uuid.AsString())
    p1 = [p for p in j90.Pads() if p.GetNumber() == "1"][0]
    print("J90 pad 1 at (%.2f, %.2f), layer %s" % (ToMM(p1.GetPosition().x), ToMM(p1.GetPosition().y), b.GetLayerName(p1.GetLayer())))
    fps["J90"] = j90
    keep.add("J90")

    # ---- symbol paths of the hub schematic, values from the model ----
    for r in keep:
        c = d.comps.get(r)
        if c is not None:
            fps[r].SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))

    # ---- parts in the way of the new left end: nearest free spot to the right ----
    others = [fp for r, fp in fps.items() if r in keep and r != "J90"]
    stuck = [fp for fp in others if crt(fp)[0] < (LIMIT_B if fp.IsFlipped() else LIMIT_F)]
    stuck.sort(key=lambda f: -ToMM(f.GetPosition().x))
    vacated = []
    def spot(fp, r0, flipped, max_move):
        """Nearest free place for courtyard r0 on one face, right of the face's limit; (dx, dy, cost) or None."""
        lim = LIMIT_B if flipped else LIMIT_F
        need = max(0.0, lim - r0[0])
        same = [crt(o) for o in others if o is not fp and o.IsFlipped() == flipped]
        cands = sorted((abs(i * 0.25) + abs(j * 0.25) * 1.3, need + i * 0.25, j * 0.25)
                       for i in range(0, 61) for j in range(-40, 41))
        for cost, dx, dy in cands:
            if abs(dx) + abs(dy) > max_move:
                continue
            n = (r0[0] + dx, r0[1] + dy, r0[2] + dx, r0[3] + dy)
            if n[0] < lim or n[2] > WIN[2] or n[1] < WIN[1] or n[3] > WIN[3]:
                continue
            if not any(overlap(n, o, 0.05) for o in same):
                return dx, dy, cost
        return None

    for fp in stuck:
        r0 = crt(fp)
        vacated.append((r0, fp.IsFlipped()))
        x0, y0 = ToMM(fp.GetPosition().x), ToMM(fp.GetPosition().y)
        s = spot(fp, r0, fp.IsFlipped(), 6.0)
        if s is None:
            # no room within 6 mm on its own face: the other face, at the same place or nearby (a part's courtyard
            # mirrors about its own centre, so the box stays the same size)
            s2 = spot(fp, r0, not fp.IsFlipped(), 8.0)
            if s2 is not None:
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
                fp.SetPosition(P(x0 + s2[0], y0 + s2[1]))
                print("moved %-6s to the %s face, by (%+.2f, %+.2f)" % (fp.GetReference(), "bottom" if fp.IsFlipped() else "top", s2[0], s2[1]))
                continue
            s = spot(fp, r0, fp.IsFlipped(), 30.0)
        if s is None:
            print("NO SPOT for", fp.GetReference(), "- left in place")
            continue
        fp.SetPosition(P(x0 + s[0], y0 + s[1]))
        print("moved %-6s %s by (%+.2f, %+.2f)" % (fp.GetReference(), "B" if fp.IsFlipped() else "F", s[0], s[1]))
    moved = [(crt(fp), fp.IsFlipped()) for fp in stuck]

    # ---- copper: left of the edge, under / around moved parts' old and new places ----
    gone = []
    for t in b.GetTracks():
        if t.m_Uuid.AsString() in stubs:
            continue
        pts = [t.GetStart(), t.GetEnd()]
        xs = [ToMM(p_.x) for p_ in pts]
        r = (min(xs), min(ToMM(p_.y) for p_ in pts), max(xs), max(ToMM(p_.y) for p_ in pts))
        if min(xs) < EDGE_CU + (0.3 if t.GetClass() == "PCB_VIA" else 0.0) or t.GetNetname() not in hub_nets:
            gone.append(t)
            continue
        if any(overlap(r, a, 0.3) for a, _ in vacated + moved):
            gone.append(t)
    print("tracks / vias removed:", len(gone))

    # ---- outline ----
    for dr in list(b.GetDrawings()):
        if dr.GetLayer() != pcbnew.Edge_Cuts:
            continue
        s, e = dr.GetStart(), dr.GetEnd()
        xs = (ToMM(s.x), ToMM(e.x))
        ys = (ToMM(s.y), ToMM(e.y))
        if min(xs) > 71.5:
            continue
        if dr.GetShape() == pcbnew.SHAPE_T_SEGMENT and max(xs) > 300 and abs(ys[0] - ys[1]) < 0.01 and \
                min(abs(ys[0] - Y_TOP), abs(ys[0] - Y_BOT)) < 0.05:
            if xs[0] < xs[1]:
                dr.SetStart(P(X_FACE, ys[0]))
            else:
                dr.SetEnd(P(X_FACE, ys[1]))
            continue
        gone.append(dr)
    for y0, y1 in ((Y_TOP, YC - 10.425), (YC + 10.425, Y_BOT)):
        seg = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(FromMM(0.05))
        seg.SetStart(P(X_FACE, y0))
        seg.SetEnd(P(X_FACE, y1))
        b.Add(seg)
    # other drawings (silkscreen notes, user layers) left of the strip go too
    for dr in list(b.GetDrawings()):
        if dr.GetLayer() != pcbnew.Edge_Cuts and ToMM(dr.GetBoundingBox().GetRight()) < 74.0:
            gone.append(dr)

    # ---- zones: drop the column's, clip the rest to the hub (tongue included) ----
    clip = pcbnew.SHAPE_POLY_SET()
    clip.NewOutline()
    for x, y in ((68.5, Y_TOP - 0.5), (366.0, Y_TOP - 0.5), (366.0, Y_BOT + 0.5), (68.5, Y_BOT + 0.5)):
        clip.Append(FromMM(x), FromMM(y))
    for z in list(b.Zones()):
        bb = rect_of(z.GetBoundingBox())
        if bb[2] < X_FACE + 0.5 or bb[3] < Y_TOP or bb[1] > Y_BOT or \
                (not z.GetIsRuleArea() and z.GetNetname() not in hub_nets):
            gone.append(z)
            continue
        o = z.Outline()
        o.BooleanIntersection(clip)
        if o.OutlineCount() == 0:
            gone.append(z)

    # ---- board ----
    ds = b.GetDesignSettings()
    ds.SetBoardThickness(FromMM(0.8))
    tb = b.GetTitleBlock()
    tb.SetTitle("Commander hub board (bays, USB hubs, microSD) - M.2 Key M card edge")
    tb.SetRevision(cpmodel.REV)

    # ---- removals last (KiCad's Python objects do not survive many removals) ----
    drop = [fp for r, fp in fps.items() if r not in keep]
    print("footprints removed:", len(drop), " kept:", len(keep))
    for it in gone:
        b.Remove(it)
    for fp in drop:
        b.Remove(fp)
    pcbnew.SaveBoard(dst, b)
    print("wrote", dst)


if __name__ == "__main__":
    main()
