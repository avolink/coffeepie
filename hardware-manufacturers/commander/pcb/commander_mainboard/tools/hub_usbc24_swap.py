#!/usr/bin/env python
"""hub_usbc24_swap.py SRC DST - the hub's four 24-pin bay receptacles J31..J34: JAE DX07S024WJ1R350 -> HOAUC
HYCW275-USBC24-050B (LCSC C42400261, 2026-11-15).

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/hub_usbc24_swap.py commander_hub.kicad_pcb build/hub_usbc.kicad_pcb

Both are right-angle receptacles at the board's rear edge.  The mating face stays where the JAE's was (its body front,
0.25 mm past the board edge) and the centre line stays; the new part is turned 180 deg so that its body runs into the
board.  Its two pad rows are 6.6 / 7.8 mm behind the face (the JAE had one row 1.2 mm behind it, at the edge).
Every pad keeps its net (same A1..B12 / SH numbering).  Removed: the connector's own tracks and vias round the bay
(they are re-routed afterwards), and any other copper that the new pads, shell slots or holes would touch.  Parts
whose courtyard now overlaps the new one are reported, not moved.
"""
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

REFS = ("J31", "J32", "J33", "J34")
LIB = "commander"
NAME = "USB_C_Receptacle_HOAUC_HYCW275-USBC24-050B"
KEEP_NETS = ("GND",)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    libdir = sys.argv[3] if len(sys.argv) > 3 else None
    b = pcbnew.LoadBoard(src)
    if libdir is None:
        import os
        libdir = os.path.join(os.path.dirname(os.path.abspath(src)), "lib", "commander.pretty")
    plans = []
    for ref in REFS:
        old = b.FindFootprintByReference(ref)
        if old.GetFPIDAsString().endswith(NAME):
            print(ref, "already swapped")
            continue
        cx, cy = ToMM(old.GetPosition().x), ToMM(old.GetPosition().y)
        front = cy - 3.5                          # the JAE body's front edge (rot 0: towards -y)
        nets = {p.GetNumber(): p.GetNetname() for p in old.Pads() if p.GetNumber()}
        netobj = {p.GetNumber(): p.GetNet() for p in old.Pads() if p.GetNumber()}
        plans.append((ref, old, cx, front, nets, netobj))

    # ---- new footprints first (nothing is removed before everything is read) ----
    new_fps = []
    for ref, old, cx, front, nets, netobj in plans:
        new = pcbnew.FootprintLoad(libdir, NAME)
        new.SetReference(ref)
        new.SetValue(old.GetValue())
        new.SetFPID(pcbnew.LIB_ID(LIB, NAME))
        b.Add(new)
        new.SetPosition(VECTOR2I(FromMM(cx), FromMM(front)))
        new.SetOrientationDegrees(180)
        new.SetPath(old.GetPath())
        for p in new.Pads():
            if p.GetNumber() in netobj:
                p.SetNet(netobj[p.GetNumber()])
        new_fps.append((ref, new, cx, front, set(nets.values()) - set(KEEP_NETS)))

    # ---- copper to remove ----
    kill = []
    for t in b.GetTracks():
        n = t.GetNetname()
        x0, y0 = ToMM(t.GetStart().x), ToMM(t.GetStart().y)
        x1, y1 = ToMM(t.GetEnd().x), ToMM(t.GetEnd().y)
        for ref, new, cx, front, own in new_fps:
            near = lambda x, y: abs(x - cx) <= 7.5 and front - 0.5 <= y <= front + 11.0
            if n in own and (near(x0, y0) or near(x1, y1)):
                kill.append(t)
                break
            # other copper under the new pads / slots / holes (a plain distance test: pad's larger half-size + the
            # track's half-width + 0.2 mm; SMD pads only meet top-face copper, holes meet every layer)
            hit = False
            is_via = t.GetClass() == "PCB_VIA"
            hw = (ToMM(t.GetWidth(pcbnew.F_Cu)) if is_via else ToMM(t.GetWidth())) / 2
            for p in new.Pads():
                if p.GetNetname() == n and n:
                    continue
                drilled = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
                if not drilled and not t.IsOnLayer(pcbnew.F_Cu):
                    continue
                px, py = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
                r = max(ToMM(p.GetSize().x), ToMM(p.GetSize().y)) / 2 + hw + 0.2
                if is_via:
                    d = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
                else:
                    dx, dy = x1 - x0, y1 - y0
                    L2 = dx * dx + dy * dy
                    u = 0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
                    d = ((px - x0 - u * dx) ** 2 + (py - y0 - u * dy) ** 2) ** 0.5
                if d < r:
                    hit = True
                    break
            if hit:
                kill.append(t)
                break
    seen = set()
    kill = [t for t in kill if not (t.m_Uuid.AsString() in seen or seen.add(t.m_Uuid.AsString()))]

    # ---- overlaps with other parts ----
    overl = []
    for ref, new, cx, front, own in new_fps:
        c = new.GetCourtyard(pcbnew.F_CrtYd)
        for f in b.GetFootprints():
            if f.GetReference() in REFS or f.IsFlipped():
                continue
            cf = f.GetCourtyard(pcbnew.F_CrtYd)
            if cf.OutlineCount() and c.Collide(cf):
                overl.append("%s/%s" % (ref, f.GetReference()))
    olds = [old for ref, old, cx, front, nets, netobj in plans]
    for t in kill:
        b.Remove(t)
    for o in olds:
        b.Remove(o)
    pcbnew.SaveBoard(dst, b)
    print("swapped %d receptacles; removed %d tracks / vias; courtyard overlaps on the top face: %s"
          % (len(plans), len(kill), " ".join(overl) or "none"))


if __name__ == "__main__":
    main()
