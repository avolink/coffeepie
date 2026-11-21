#!/usr/bin/env python
"""hub_midmount_swap.py SRC DST - the hub's nine bay receptacles J31..J39 -> Amphenol 12402072E512A, sink (mid) mount
in a notch of the board's rear edge (2026-11-16).

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/hub_midmount_swap.py commander_hub.kicad_pcb build/hub_sink.kicad_pcb

Why: the hub board moves up about 2 mm (M.2 socket J41 on the mainboard becomes the H4.2 LOTES APCI0107, card 2.4 mm
above the mainboard instead of 0.3) to sit in the chassis' slot; a sink-mount receptacle (centre 0.10 mm under the
board's top face instead of 1.63 mm above it) keeps the bays on the expansion cards' plug axis.
The mating face stays where the old receptacles' was (0.255 mm past the rear edge, board y 81.045), so the cards mate as
before; the new footprint's origin is its mouth and its body runs into the board (rot 0).  Every pad keeps its net by
name (A1..B12 / SH); on the five USB 2.0 bays the SuperSpeed pads stay unconnected.  The rear edge gets a 9.42 mm notch
under each receptacle (to 7.60 mm behind the mouth, R0.5 reliefs at the inner corners, as the footprint's User.1).
Removed: the old footprints, the bay's own tracks / vias round it, and any copper that the new pads, slots or holes
or the notch would touch.  Parts whose courtyard now overlaps the new one or the notch are reported, not moved.
"""
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

REFS = ["J%d" % i for i in range(31, 40)]
LIB = "commander"
NAME = "USB_C_Receptacle_Amphenol_12402072E512A"
KEEP_NETS = ("GND",)
EDGE_Y = 81.30                 # the board's rear edge
MOUTH_Y = 81.045               # the receptacles' mating face (as before)
NOTCH_HW, NOTCH_END, RELIEF = 4.71, 7.60, 0.5


def seg(b, a, c):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(FromMM(a[0]), FromMM(a[1])))
    s.SetEnd(VECTOR2I(FromMM(c[0]), FromMM(c[1])))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(FromMM(0.1))
    b.Add(s)


def arc(b, a, m, c):
    s = pcbnew.PCB_SHAPE(b)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(VECTOR2I(FromMM(a[0]), FromMM(a[1])), VECTOR2I(FromMM(m[0]), FromMM(m[1])), VECTOR2I(FromMM(c[0]), FromMM(c[1])))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(FromMM(0.1))
    b.Add(s)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    import os
    libdir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(src)), "lib", "commander.pretty")
    b = pcbnew.LoadBoard(src)
    plans = []
    for ref in REFS:
        old = b.FindFootprintByReference(ref)
        if old.GetFPIDAsString().endswith(NAME):
            print(ref, "already swapped")
            continue
        cx = ToMM(old.GetPosition().x)
        netobj = {p.GetNumber(): p.GetNet() for p in old.Pads() if p.GetNumber()}
        nets = {p.GetNumber(): p.GetNetname() for p in old.Pads() if p.GetNumber()}
        plans.append((ref, old, cx, nets, netobj))

    new_fps = []
    for ref, old, cx, nets, netobj in plans:
        new = pcbnew.FootprintLoad(libdir, NAME)
        new.SetReference(ref)
        new.SetValue("USBC24_SINK")
        new.SetFPID(pcbnew.LIB_ID(LIB, NAME))
        b.Add(new)
        new.SetPosition(VECTOR2I(FromMM(cx), FromMM(MOUTH_Y)))
        new.SetOrientationDegrees(0)
        new.SetPath(old.GetPath())
        for p in new.Pads():
            if p.GetNumber() in netobj:
                p.SetNet(netobj[p.GetNumber()])
        new_fps.append((ref, new, cx, set(nets.values()) - set(KEEP_NETS)))

    # ---- the rear edge: the one long segment at y 81.30 is replaced by pieces with a notch under every bay ----
    rear = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_SEGMENT
            and abs(ToMM(d.GetStart().y) - EDGE_Y) < 1e-3 and abs(ToMM(d.GetEnd().y) - EDGE_Y) < 1e-3]
    if len(rear) != 1:
        raise SystemExit("rear edge segment not found (%d candidates); notches not cut" % len(rear))
    r = rear[0]
    xa, xb = sorted((ToMM(r.GetStart().x), ToMM(r.GetEnd().x)))
    b.Remove(r)
    x = xa
    ye = MOUTH_Y + NOTCH_END
    for ref, new, cx, own in sorted(new_fps, key=lambda t: t[2]):
        l, rr = cx - NOTCH_HW, cx + NOTCH_HW
        seg(b, (x, EDGE_Y), (l, EDGE_Y))
        seg(b, (l, EDGE_Y), (l, ye - 2 * RELIEF))
        arc(b, (l, ye - 2 * RELIEF), (l - RELIEF, ye - RELIEF), (l, ye))
        seg(b, (l, ye), (rr, ye))
        arc(b, (rr, ye), (rr + RELIEF, ye - RELIEF), (rr, ye - 2 * RELIEF))
        seg(b, (rr, ye - 2 * RELIEF), (rr, EDGE_Y))
        x = rr
    seg(b, (x, EDGE_Y), (xb, EDGE_Y))

    # ---- copper to remove: the bay's own copper round it, anything on the new pads / holes, anything in a notch ----
    def in_notch(px, py, cx, m):
        return abs(px - cx) <= NOTCH_HW + RELIEF + m and EDGE_Y - m <= py <= ye + m

    kill = []
    for t in b.GetTracks():
        n = t.GetNetname()
        x0, y0 = ToMM(t.GetStart().x), ToMM(t.GetStart().y)
        x1, y1 = ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        is_via = t.GetClass() == "PCB_VIA"
        hw = (ToMM(t.GetWidth(pcbnew.F_Cu)) if is_via else ToMM(t.GetWidth())) / 2
        for ref, new, cx, own in new_fps:
            near = lambda xx, yy: abs(xx - cx) <= 7.5 and MOUTH_Y - 0.5 <= yy <= MOUTH_Y + 11.5   # noqa: E731
            if n in own and (near(x0, y0) or near(x1, y1)):
                kill.append(t)
                break
            pts = [(x0 + (x1 - x0) * k / 20.0, y0 + (y1 - y0) * k / 20.0) for k in range(21)]
            if any(in_notch(px, py, cx, hw + 0.3) for px, py in pts):
                kill.append(t)
                break
            hit = False
            for p in new.Pads():
                if p.GetNetname() == n and n:
                    continue
                drilled = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                if not drilled and not t.IsOnLayer(pcbnew.F_Cu):
                    continue
                px, py = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
                rad = max(ToMM(p.GetSize().x), ToMM(p.GetSize().y)) / 2 + hw + 0.2
                if is_via:
                    d = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
                else:
                    dx, dy = x1 - x0, y1 - y0
                    L2 = dx * dx + dy * dy
                    u = 0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
                    d = ((px - x0 - u * dx) ** 2 + (py - y0 - u * dy) ** 2) ** 0.5
                if d < rad:
                    hit = True
                    break
            if hit:
                kill.append(t)
                break
    seen = set()
    kill = [t for t in kill if not (t.m_Uuid.AsString() in seen or seen.add(t.m_Uuid.AsString()))]

    # ---- parts in the way (courtyard against the new courtyard, either face, or a pad inside a notch) ----
    overl = []
    for ref, new, cx, own in new_fps:
        c = new.GetCourtyard(pcbnew.F_CrtYd)
        for f in b.GetFootprints():
            if f.GetReference() in REFS:
                continue
            cf = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
            if (not f.IsFlipped()) and cf.OutlineCount() and c.Collide(cf):
                overl.append("%s/%s" % (ref, f.GetReference()))
            elif any(in_notch(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), cx, 0.3) for p in f.Pads()):
                overl.append("%s/%s(in notch)" % (ref, f.GetReference()))
    olds = [old for ref, old, cx, nets, netobj in plans]
    for t in kill:
        b.Remove(t)
    for o in olds:
        b.Remove(o)
    pcbnew.SaveBoard(dst, b)
    print("swapped %d receptacles, %d notches cut; removed %d tracks / vias; parts in the way: %s"
          % (len(plans), len(new_fps), len(kill), " ".join(sorted(set(overl))) or "none"))


if __name__ == "__main__":
    main()
