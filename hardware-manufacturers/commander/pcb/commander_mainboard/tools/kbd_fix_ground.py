"""kbd_fix_ground.py (keyboard, run with KiCad's Python, CP_ROOT = commander_keyboard) IN OUT REF.PAD RIP,RIP,...  - join a ground pad that sits on a fenced-in pour island to the main ground.

The router's tracks of the RIP nets are taken out, the pad is joined (track and vias) to the nearest pad, via or pour
of the main ground, then the RIP nets are routed again in several orders; the first that leaves nothing open wins."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.environ["CP_ROOT"], "..", "commander_mainboard", "tools"))
import numpy as np
import pcbnew
from pcbnew import ToMM

src, dst, refpad, rip = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
ref, num = refpad.split(".")
import kbd_board as K
import route as R

b = pcbnew.LoadBoard(src)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.BuildConnectivity()
conn0 = b.GetConnectivity()
groups0, seen0 = [], set()
for it in [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() == "GND"] +           [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]:
    u = it.m_Uuid.AsString()
    if u in seen0:
        continue
    ids = {x.m_Uuid.AsString() for x in conn0.GetConnectedItems(it, 0)} | {u}
    seen0 |= ids
    groups0.append(ids)
MAIN0 = max(groups0, key=len)                   # the main ground as it is BEFORE anything is taken out
kill = [t for t in K.movable_tracks(b) if t.GetNetname() in rip]
print("taking out %d pieces of %s" % (len(kill), " ".join(rip)), flush=True)
for t in kill:
    b.Remove(t)
tmp = dst + ".tmp.kicad_pcb"
pcbnew.SaveBoard(tmp, b, True)

from gen_pcb import OX, OY
board = pcbnew.LoadBoard(tmp)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.BuildConnectivity()
conn = board.GetConnectivity()
# the main ground: the largest group of ground pads / vias that KiCad sees connected
groups, seen = [], set()
for it in [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == "GND"] + \
          [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]:
    u = it.m_Uuid.AsString()
    if u in seen:
        continue
    items = list(conn.GetConnectedItems(it, 0)) + [it]
    ids = {x.m_Uuid.AsString() for x in items}
    seen |= ids
    groups.append((ids, items))
main_ids, main_items = max(groups, key=lambda g: len(g[0]))
main_ids = main_ids & MAIN0                     # (without the island, which the refill may have merged in)
main_items = [it for it in main_items if it.m_Uuid.AsString() in main_ids]
r, reg, code = K.make_router(board)
r.items, r.failed = [], []
G = R.G
gnd = code["GND"]
pd = next(q for q in reg.pads[gnd] if q["ref"] == ref and q["num"] == num)
if pd["pad"].m_Uuid.AsString() in main_ids:
    sys.exit("%s is on the main ground already" % refpad)
goal_cells = [c for q in reg.pads[gnd] if q["pad"].m_Uuid.AsString() in main_ids for c in q["cells"]]
for it in main_items:
    if it.GetClass() == "PCB_VIA":
        i, j = int(round((ToMM(it.GetPosition().x) - OX - reg.x0) / G)), int(round((ToMM(it.GetPosition().y) - OY - reg.y0) / G))
        goal_cells += [(0, i, j), (2, i, j)]
rc = R.RCS["Default"]
i0, j0, W, H, ok, vok = r.window(reg, gnd, rc, (pd["cx"] - 8, pd["cy"] - 8, pd["cx"] + 8, pd["cy"] + 8), 0)
goal = np.zeros((3, H, W), bool)
for c in goal_cells:
    if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
        goal[c[0], c[2] - j0, c[1] - i0] = True
goal &= ok
starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in pd["cells"] if ok[c[0], c[2] - j0, c[1] - i0]]
gl, gy, gx = np.nonzero(goal)
res, _ = R.search([ok[l].tobytes() for l in range(3)], vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts,
                  (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max())), max_exp=3000000, penb=r.pen)
if not res:
    sys.exit("FAILED: no way from %s to the main ground even with %s taken out" % (refpad, " ".join(rip)))
cells = r.commit(reg, gnd, rc, res, W, H, i0, j0)
r.stub(reg, gnd, rc, cells[0], pd)
print("%s joined to the main ground: %d cells" % (refpad, len(cells)), flush=True)

snap_D = {k: D.copy() for k, D in reg.D.items()}
snap = (reg.novia.copy(), list(reg.uf), {n: dict(v) for n, v in reg.tree.items()}, {n: dict(v) for n, v in reg.exact.items()}, len(r.items))
rnd = random.Random(3)
nets = [code[n] for n in rip]
best = None
for attempt in range(int(os.environ.get("CP_ORDERS", "12"))):
    if attempt:
        for k, D in reg.D.items():
            D[...] = snap_D[k]
        reg.novia[...] = snap[0]
        reg.uf[:] = snap[1]
        reg.tree.clear(); reg.tree.update({n: dict(v) for n, v in snap[2].items()})
        reg.exact.clear(); reg.exact.update({n: dict(v) for n, v in snap[3].items()})
        del r.items[snap[4]:]
        rnd.shuffle(nets)
    left = []
    for n in nets + [n_ for n_ in K.split_nets(r, reg) if n_ not in nets]:
        _, bad = r.route_net(reg, n)
        if bad:
            left.append(r.name_of[n])
    print("order %d: still open %s" % (attempt + 1, " ".join(left) or "-"), flush=True)
    if best is None or len(left) < len(best[0]):
        best = (left, list(r.items))
    if not left:
        break
r.items[:] = best[1]
r.flush(r.items)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(dst, board, True)
os.remove(tmp)
print("written %s, still open: %s" % (dst, " ".join(best[0]) or "-"))
