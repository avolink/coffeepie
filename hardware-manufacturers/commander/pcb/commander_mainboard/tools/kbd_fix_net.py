"""kbd_fix_net.py (keyboard, run with KiCad's Python, CP_ROOT = commander_keyboard) IN OUT NET X0 X1 RIP,RIP,...  - targeted repair on the keyboard board.

The router's tracks of NET and of the RIP nets are taken out; NET is routed first, to the part of its own copper that
lies between board x X0 and X1 only; then the RIP nets are routed again, in several orders (in memory); the first
order that leaves nothing open is written to OUT."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.environ["CP_ROOT"], "..", "commander_mainboard", "tools"))
import numpy as np
import pcbnew
from pcbnew import ToMM

src, dst, name, X0, X1, rip = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), sys.argv[6].split(",")
import kbd_board as K
import route as R

# 1. take the tracks out (on a copy)
b = pcbnew.LoadBoard(src)
kill = [t for t in K.movable_tracks(b) if t.GetNetname() in rip + [name]]
print("taking out %d pieces of %s" % (len(kill), " ".join([name] + rip)), flush=True)
for t in kill:
    b.Remove(t)
tmp = dst + ".tmp.kicad_pcb"
pcbnew.SaveBoard(tmp, b, True)

# 2. route
from gen_pcb import OX, OY
board = pcbnew.LoadBoard(tmp)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.BuildConnectivity()
r, reg, code = K.make_router(board)
r.items, r.failed = [], []
G = R.G
net = code[name]


def route_first():
    """NET from its chip pin's island to its own copper with board x in [X0, X1]."""
    pads = reg.pads.get(net, [])
    pd = next(q for q in pads if q["ref"] == "U201")
    root = reg.find(pd["node"])
    own = [c for q in pads if reg.find(q["node"]) == root for c in q["cells"]] + \
          [c for c, nd in reg.tree.get(net, {}).items() if reg.find(nd) == root]
    other = [c for c, nd in reg.tree.get(net, {}).items() if reg.find(nd) != root and X0 <= reg.xy(c[1], c[2])[0] + OX <= X1]
    other += [c for q in pads if reg.find(q["node"]) != root and X0 <= q["cx"] + OX <= X1 for c in q["cells"]]
    if not other:
        print("no copper of %s between x %.1f and %.1f" % (name, X0, X1))
        return False
    xs = [reg.xy(c[1], c[2])[0] for c in own + other]
    ys = [reg.xy(c[1], c[2])[1] for c in own + other]
    rc = r.rc_of[net]
    i0, j0, W, H, ok, vok = r.window(reg, net, rc, (min(xs), min(ys), max(xs), max(ys)), 80)
    goal = np.zeros((3, H, W), bool)
    for c in other:
        if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
            goal[c[0], c[2] - j0, c[1] - i0] = True
    goal &= ok
    starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in own if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
    gl, gy, gx = np.nonzero(goal)
    res, _ = R.search([ok[l].tobytes() for l in range(3)], vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts,
                      (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max())), max_exp=3000000, penb=r.pen)
    if not res:
        return False
    cells = r.commit(reg, net, rc, res, W, H, i0, j0)
    for c in (cells[0], cells[-1]):
        n = reg.padcell.get(net, {}).get(c)
        if n is not None:
            r.stub(reg, net, rc, c, pads[n])
    print("%s routed first: %d cells" % (name, len(cells)), flush=True)
    return True


if not route_first():
    print("FAILED: %s found no way to x %.1f..%.1f" % (name, X0, X1))
    sys.exit(2)
snap_D = {k: D.copy() for k, D in reg.D.items()}
snap = (reg.novia.copy(), list(reg.uf), {n: dict(v) for n, v in reg.tree.items()}, {n: dict(v) for n, v in reg.exact.items()}, len(r.items))
rnd = random.Random(7)
nets = [code[n] for n in rip]
best = None
for attempt in range(int(os.environ.get("CP_ORDERS", "10"))):
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
