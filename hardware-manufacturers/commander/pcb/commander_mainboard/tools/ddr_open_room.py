"""ddr_open_room.py SRC DST [inner|inner+b] - experiment (input for tools/route_ddr_groups.py via CP_DDR_SRC): the memory field with room opened.  Removes, inside the field, the top-face parts
and every top-face / In2 / In3 track of nets other than the memory's, and the other nets' vias that are not in a
ball of U1 / U10.  The memory field = both packages (design mm).  Nothing of this is meant for the real board as such:
it measures what routing the bus would need."""
import sys
import pcbnew
from pcbnew import ToMM

OX, OY = 40.0, 70.0
FIELD = (6.0, 69.5, 23.0, 90.0)
src, dst = sys.argv[1], sys.argv[2]
INNER_ONLY = len(sys.argv) > 3 and sys.argv[3] in ("inner", "inner+b")      # open only In2 / In3, leave the top face as it is
CLEAR_B = len(sys.argv) > 3 and sys.argv[3] == "inner+b"       # and the other nets' B.Cu tracks between the balls (stubs kept)
b = pcbnew.LoadBoard(src)


def inside(p):
    x, y = ToMM(p.x) - OX, ToMM(p.y) - OY
    return FIELD[0] <= x <= FIELD[2] and FIELD[1] <= y <= FIELD[3]


ball = set()
for ref in ("U1", "U10"):
    for p in b.FindFootprintByReference(ref).Pads():
        ball.add((p.GetPosition().x, p.GetPosition().y))
kill_fp = [] if INNER_ONLY else [f for f in b.GetFootprints() if not f.IsFlipped() and any(inside(p.GetPosition()) for p in f.Pads())]
kill = []
balls = {}
for ref in ("U1", "U10"):
    for p in b.FindFootprintByReference(ref).Pads():
        balls[(p.GetPosition().x, p.GetPosition().y)] = p.GetNetname()
STUB = pcbnew.FromMM(0.7)
displaced = set()
for t in b.GetTracks():
    if t.GetNetname().startswith("LPDDR4_"):
        continue
    if t.GetClass() == "PCB_VIA":
        if not INNER_ONLY and inside(t.GetPosition()) and (t.GetPosition().x, t.GetPosition().y) not in ball:
            kill.append(t)
    elif t.GetLayer() in ((pcbnew.In2_Cu, pcbnew.In3_Cu) if INNER_ONLY else (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu)) and (inside(t.GetStart()) or inside(t.GetEnd())):
        kill.append(t)
    elif CLEAR_B and t.GetLayer() == pcbnew.B_Cu and (inside(t.GetStart()) or inside(t.GetEnd())):
        ends = [(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)]
        if t.GetLength() <= STUB and any(e in balls for e in ends):
            continue                                # a ball's own dog-bone to its via
        kill.append(t)
        displaced.add(t.GetNetname())
if CLEAR_B:
    print("other nets whose B.Cu copper under the chips is taken out (to be re-routed round the field): %d" % len(displaced))
    print("  " + " ".join(sorted(displaced)))
print("removing %d top-face parts, %d tracks / vias of other nets in the memory field" % (len(kill_fp), len(kill)))
for it in kill + kill_fp:
    b.Remove(it)
pcbnew.SaveBoard(dst, b)
