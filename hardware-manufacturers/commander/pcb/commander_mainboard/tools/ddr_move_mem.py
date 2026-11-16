#!/usr/bin/env python
"""ddr_move_mem.py SRC DST DX DY ROT - experiment: the memory U10 moved by (DX, DY) mm and turned by ROT degrees.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/ddr_move_mem.py build/ddr6_src.kicad_pcb build/mem_x.kicad_pcb -2.5 3 0

For measuring only (input for tools/route_ddr_groups.py through CP_DDR_SRC, as ddr_open_room.py is): the memory's own
vias (the ones in its balls) move and turn with it; in the memory's new place every other net's via and B.Cu track
is removed, and every bottom-face part whose courtyard overlaps the memory's is taken off the board.  So the result
says what the memory bus could reach in that place, not what the rest of the board would need to make room for it.
"""
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

OX, OY = 40.0, 70.0


def main():
    src, dst, dx, dy, rot = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    b = pcbnew.LoadBoard(src)
    bottom_refs = [f.GetReference() for f in b.GetFootprints() if f.IsFlipped() and f.GetReference() != "U10"]
    u = b.FindFootprintByReference("U10")
    balls = {(p.GetPosition().x, p.GetPosition().y) for p in u.Pads()}
    own = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and (t.GetPosition().x, t.GetPosition().y) in balls]
    c0 = u.GetPosition()
    off = VECTOR2I(FromMM(dx), FromMM(dy))
    ang = pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T)
    for item in [u] + own:
        if rot:
            item.Rotate(c0, ang)
        item.Move(off)
    ownset = {v.m_Uuid.AsString() for v in own}
    crt = u.GetCourtyard(pcbnew.B_CrtYd)
    box = crt.BBox()
    box.Inflate(FromMM(0.2))
    gone_fp = []                                # (decided before anything is removed: pcbnew's wrappers go astray after)
    for ref in bottom_refs:
        c = b.FindFootprintByReference(ref).GetCourtyard(pcbnew.B_CrtYd)
        if c.OutlineCount() and c.Collide(crt):
            gone_fp.append(ref)
    gone_objs = [b.FindFootprintByReference(ref) for ref in gone_fp]
    where = "(%.2f, %.2f) rot %.0f" % (ToMM(u.GetPosition().x) - OX, ToMM(u.GetPosition().y) - OY, u.GetOrientationDegrees())
    gone_v = gone_t = 0
    for t in list(b.GetTracks()):
        if t.m_Uuid.AsString() in ownset or t.GetNetname().startswith("LPDDR4_"):
            continue
        if t.GetClass() == "PCB_VIA":
            if box.Contains(t.GetPosition()):
                b.Remove(t)
                gone_v += 1
        elif t.GetLayer() == pcbnew.B_Cu and (box.Contains(t.GetStart()) or box.Contains(t.GetEnd())):
            b.Remove(t)
            gone_t += 1
    for f in gone_objs:
        b.Remove(f)
    pcbnew.SaveBoard(dst, b)
    print("U10 now at %s; %d of its vias moved with it; removed %d vias, %d B.Cu tracks, parts %s"
          % (where, len(own), gone_v, gone_t, " ".join(gone_fp) or "-"))


if __name__ == "__main__":
    main()
