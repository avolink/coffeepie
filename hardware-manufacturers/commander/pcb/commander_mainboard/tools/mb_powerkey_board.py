"""mb_powerkey_board.py (KiCad's Python; the mainboard) --stage edit|route|promote

The 2026-11-19 power-key change on the mainboard, which is a master file with hand work on it (it is not rebuilt):
  edit     SW3 (the tact switch) taken out with the PMIC_PWRON copper that only went to it; J22 (2-pin JST-SH, the
           cable from the keyboard's power key) and ED13 (its ESD diode) placed on the top face at the right-hand
           edge beside J20; F1's value from the netlist (750 mA)                -> build/mb_pk_edit.kicad_pcb
  route    PMIC_PWRON joined again with the mainboard's router in a window round J22 and the PMIC; each ground pad of
           the new parts gets a short stub and a via to the ground planes      -> build/mb_pk_routed.kicad_pcb
  promote  the old board kept as build/mb_before_powerkey.kicad_pcb, the routed one put in its place
"""
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew                                   # noqa: E402
from pcbnew import FromMM, ToMM, VECTOR2I       # noqa: E402

import cpmodel                                  # noqa: E402

ROOT, PRJ = cpmodel.ROOT, cpmodel.PRJ
FINAL = os.path.join(ROOT, PRJ + ".kicad_pcb")
BUILD = os.path.join(ROOT, "build")
EDIT = os.path.join(BUILD, "mb_pk_edit.kicad_pcb")
ROUTED = os.path.join(BUILD, "mb_pk_routed.kicad_pcb")
BACKUP = os.path.join(BUILD, "mb_before_powerkey.kicad_pcb")
NET = "PMIC_PWRON"
CL = 0.2
VIA_D, VIA_DRILL, STUB_W = 0.45, 0.25, 0.2


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def xy(v):
    return ToMM(v.x), ToMM(v.y)


def with_project(path):
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(ROOT, PRJ + ext)
        if os.path.exists(src):
            shutil.copyfile(src, path[:-len(".kicad_pcb")] + ext)


def court(fp):
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    c = fp.GetCourtyard(layer)
    bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
    return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())


def dseg(px, py, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    u = 0.0 if L == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / L))
    return math.hypot(px - a[0] - u * dx, py - a[1] - u * dy)


def rect_seg(r, a, b):
    best = 1e9
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
    for k in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
        best = min(best, math.hypot(max(r[0] - x, 0, x - r[2]), max(r[1] - y, 0, y - r[3])))
    return best


class Copper:
    """Copper of the board as simple shapes: ('s', layer, a, b, half width) segments, ('c', None, centre, radius) for
    vias and holes (every layer), ('r', layer or None, box) for pads; each with its net."""

    def __init__(self, board):
        self.items = []
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                self.items.append((t.GetNetname(), "c", None, xy(t.GetPosition()), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
            else:
                self.items.append((t.GetNetname(), "s", t.GetLayer(), (xy(t.GetStart()), xy(t.GetEnd())), ToMM(t.GetWidth()) / 2))
        for f in board.GetFootprints():
            for p in f.Pads():
                self.add_pad(p)
        self.zones = []
        for z in board.Zones():
            if z.GetIsRuleArea():
                continue
            for l in z.GetLayerSet().Seq():
                self.zones.append((z.GetNetname(), l, z.GetFilledPolysList(l)))

    def add_pad(self, p):
        bb = p.GetBoundingBox()
        r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        lay = None if p.HasHole() else (pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu)
        self.items.append((p.GetNetname(), "r", lay, r, 0.0))

    def rect_ok(self, r, layer, net):
        """A box of copper on `layer` (None = every layer) keeps CL from all copper of other nets."""
        for n, kind, l, g, w in self.items:
            if net and n == net:
                continue
            if layer is not None and l is not None and l != layer:
                continue
            if kind == "c":
                (cx, cy) = g
                if math.hypot(max(r[0] - cx, 0, cx - r[2]), max(r[1] - cy, 0, cy - r[3])) - w < CL:
                    return False
            elif kind == "s":
                a, b = g
                if min(a[0], b[0]) - 2 > r[2] or max(a[0], b[0]) + 2 < r[0] or min(a[1], b[1]) - 2 > r[3] or max(a[1], b[1]) + 2 < r[1]:
                    continue
                if rect_seg(r, a, b) - w < CL:
                    return False
            else:
                q = g
                if not (r[2] + CL <= q[0] or q[2] + CL <= r[0] or r[3] + CL <= q[1] or q[3] + CL <= r[1]):
                    return False
        return True

    def in_zone(self, x, y, layer, net):
        """Does a filled zone of another net cover (x, y) on `layer` (None = any layer)?"""
        v = P(x, y)
        for n, l, fill in self.zones:
            if n == net or (layer is not None and l != layer):
                continue
            if fill.Contains(v, -1, FromMM(CL + 0.3)):
                return True
        return False


def pose(fp, x, y, rot, bottom=False):
    if bottom != fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))


def fits(fp, cop, ps, boxes, edge_x=None, side="right"):
    c = court(fp)
    if any(not (c[2] <= b[0] or b[2] <= c[0] or c[3] <= b[1] or b[3] <= c[1]) for b in boxes):
        return False
    for i in range(6):
        for j in range(6):
            x, y = c[0] + (c[2] - c[0]) * i / 5, c[1] + (c[3] - c[1]) * j / 5
            if edge_x is not None and (x > edge_x - 0.6 if side == "right" else x < edge_x + 0.6):
                continue                        # (the connector's mouth stands on the edge)
            if not ps.Contains(P(x, y)):
                return False
    face = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
    for p in fp.Pads():
        if not p.IsOnLayer(face) and not p.HasHole():
            continue
        bb = p.GetBoundingBox()
        r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
        if not cop.rect_ok(r, None if p.HasHole() else face, p.GetNetname()):
            return False
        cx, cy = xy(p.GetPosition())
        if cop.in_zone(cx, cy, face, p.GetNetname()):
            return False
    return True


def new_fp(board, d, nets, ref):
    import gen_pcb as GP
    from gen_schematic import uid
    c = d.comps[ref]
    fp = GP.load_fp(c.fp)
    fp.SetReference(c.ref)
    fp.SetValue(c.value)
    fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
    fp.SetSheetname("/" + c.sheet + "/")
    fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
    for pin, net in c.pins.items():
        for padname in cpmodel.pads_for(c, pin):
            for p in fp.Pads():
                if p.GetNumber() == padname and net:
                    p.SetNet(nets[net])
    board.Add(fp)
    return fp


def trim_dead(board, net, skip):
    """The copper of `net` that would lead nowhere once footprint `skip` is gone: track ends that touch no pad, via or
    other track of the net, vias with one track or none and no pad; over and over until nothing more goes."""
    pads = [p for f in board.GetFootprints() if f.GetReference() != skip for p in f.Pads() if p.GetNetname() == net]
    # (worked out on plain copies first, then removed in one go: KiCad's Python objects do not like a board that
    #  changes under them)
    allt = [t for t in board.GetTracks() if t.GetNetname() == net]
    T = [(t, t.GetLayer(), xy(t.GetStart()), xy(t.GetEnd()), ToMM(t.GetWidth()) / 2) for t in allt if t.GetClass() != "PCB_VIA"]
    V = [(v, xy(v.GetPosition()), ToMM(v.GetWidth(pcbnew.F_Cu)) / 2) for v in allt if v.GetClass() == "PCB_VIA"]
    dead = []

    def on_pad(e, layer):
        return any((layer is None or p.IsOnLayer(layer)) and p.HitTest(P(*e), FromMM(0.01)) for p in pads)

    def touches(tt, e):
        return dseg(e[0], e[1], tt[2], tt[3]) <= 0.005     # (a joint: on the other track's centre line)
    while True:
        kill = []
        for tt in T:
            for e in (tt[2], tt[3]):
                if on_pad(e, tt[1]):
                    continue
                if any(math.hypot(c[0] - e[0], c[1] - e[1]) <= rad for _, c, rad in V):
                    continue
                if any(o[0] is not tt[0] and o[1] == tt[1] and touches(o, e) for o in T):
                    continue
                kill.append(tt[0])
                break
        for v, c, rad in V:
            n = sum(1 for tt in T if touches(tt, c))
            if n <= 1 and not on_pad(c, None):
                kill.append(v)
        if not kill:
            break
        ks = {id(k) for k in kill}
        T = [tt for tt in T if id(tt[0]) not in ks]
        V = [vv for vv in V if id(vv[0]) not in ks]
        dead += kill
    return dead


def stage_strip():
    """(a process of its own: KiCad's Python side of a board does not survive removals)"""
    d = cpmodel.load()
    os.makedirs(BUILD, exist_ok=True)
    shutil.copyfile(FINAL, EDIT)
    with_project(EDIT)
    board = pcbnew.LoadBoard(EDIT)
    f1 = board.FindFootprintByReference("F1")
    print("  F1: %s -> %s" % (f1.GetValue(), d.comps["F1"].value))
    f1.SetValue(d.comps["F1"].value)
    ref = "SW3"
    if board.FindFootprintByReference(ref) is not None:
        kill = trim_dead(board, NET, skip=ref)
        # and the ground stubs from its two ground pads (they end at a via to the ground planes, which stays)
        gpads = [p for p in board.FindFootprintByReference(ref).Pads() if p.GetNetname() == "GND"]
        other = [p for f in board.GetFootprints() if f.GetReference() != ref for p in f.Pads() if p.GetNetname() == "GND"]
        gt = [(t, xy(t.GetStart()), xy(t.GetEnd())) for t in board.GetTracks() if t.GetNetname() == "GND" and t.GetClass() != "PCB_VIA" and ToMM(t.GetLength()) < 2.0]
        gv = [xy(t.GetPosition()) for t in board.GetTracks() if t.GetNetname() == "GND" and t.GetClass() == "PCB_VIA"]
        ng = 0
        gone = set()
        loose = []                              # points where a removed stub ended
        for t, a_, b_ in gt:
            if any(p.HitTest(P(*e), 0) for p in gpads for e in (a_, b_)):
                gone.add(id(t))
                kill.append(t)
                ng += 1
                loose += [a_, b_]
        while True:                             # follow each stub on while its end touches nothing else
            more = False
            for t, a_, b_ in gt:
                if id(t) in gone:
                    continue
                for e, far in ((a_, b_), (b_, a_)):
                    if not any(math.hypot(e[0] - l[0], e[1] - l[1]) < 0.005 for l in loose):
                        continue
                    if any(math.hypot(e[0] - v[0], e[1] - v[1]) < 0.005 for v in gv) or any(p.HitTest(P(*e), 0) for p in other):
                        continue
                    if any(id(o) not in gone and o is not t and any(math.hypot(e[0] - q[0], e[1] - q[1]) < 0.005 for q in (oa, ob)) for o, oa, ob in gt):
                        continue
                    gone.add(id(t))
                    kill.append(t)
                    ng += 1
                    loose.append(far)
                    more = True
                    break
            if not more:
                break
        print("  %d ground stub(s) of SW3 taken out" % ng)
        for t in kill:
            board.Remove(t)
        board.Remove(board.FindFootprintByReference(ref))
        print("  SW3 taken out; %d pieces of %s copper that only led to it taken out" % (len(kill), NET))
    pcbnew.SaveBoard(EDIT, board, True)


def stage_edit():
    import subprocess
    d = cpmodel.load()
    if d.errors:
        raise SystemExit("\n".join(d.errors))
    rc = subprocess.run([sys.executable, os.path.abspath(__file__), "--stage", "strip"]).returncode
    if rc:
        raise SystemExit("strip failed")
    board = pcbnew.LoadBoard(EDIT)
    nets = {}
    for name in sorted(d.nets()):
        ni = board.FindNet(name)
        if ni is None:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
        nets[name] = ni
    rep = []
    rep.append("%s pads left: %s" % (NET, ", ".join("%s.%s" % (f.GetReference(), p.GetNumber()) for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == NET)))
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    edge_of = {"right": ToMM(board.GetBoardEdgesBoundingBox().GetRight()), "left": ToMM(board.GetBoardEdgesBoundingBox().GetLeft())}
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    cop = Copper(board)
    boxes_of = {b: [court(f) for f in board.GetFootprints() if f.IsFlipped() == b] for b in (False, True)}
    j20 = board.FindFootprintByReference("J20")
    jb = court(j20)
    j22 = new_fp(board, d, nets, "J22")
    ed13 = new_fp(board, d, nets, "ED13")
    # Where it goes (2026-11-19): beside J20 on the right-hand edge was the wish, but that edge is full on both faces
    # from J2 to J21 (J2, J20, H2, SW1 / SW2, J21 on top, their parts below).  So: the right-hand edge if it ever has
    # room, else the left-hand edge on the top face (where SW3 was), else the left-hand edge below; nearest to J20 first.
    ok = False
    jc = (jb[1] + jb[3]) / 2
    ys = sorted([jc + 0.25 * k for k in range(-400, 101)], key=lambda v: abs(v - jc))
    for side, bottom in (("right", False), ("right", True), ("left", False), ("left", True)):
        boxes = boxes_of[bottom]
        edge_x = edge_of[side]
        for yy, rot in ((y_, r_) for y_ in ys for r_ in (0, 90, 180, 270)):
            pose(j22, 55.0, yy, rot, bottom)
            pads = [xy(p.GetPosition()) for p in j22.Pads() if p.GetNumber() in ("1", "2")]
            c = court(j22)
            if (sum(p[0] for p in pads) / 2 < (c[0] + c[2]) / 2) != (side == "right"):
                continue                        # the mouth faces the edge: the pins are on the far side of the body
            j22.SetPosition(VECTOR2I(j22.GetPosition().x + FromMM((edge_x - c[2]) if side == "right" else (edge_x - c[0])), j22.GetPosition().y))
            if fits(j22, cop, ps, boxes, edge_x, side):
                ok = True
                break
        if ok:
            break
    if not ok:
        raise SystemExit("no room for J22 on either side edge")
    boxes.append(court(j22))
    for p in j22.Pads():
        cop.add_pad(p)
    rep.append("J22 at (%.2f, %.2f) turned %.0f, %s face, mouth on the %s-hand edge" % (*xy(j22.GetPosition()), j22.GetOrientationDegrees(), "bottom" if bottom else "top", side))
    p1 = xy(next(p for p in j22.Pads() if p.GetNumber() == "1").GetPosition())
    ok = False
    for rr in [0.25 * k for k in range(4, 60)]:
        n = max(8, int(2 * math.pi * rr / 0.25))
        for k in range(n):
            a = 2 * math.pi * k / n
            for rot in (0, 90, 180, 270):
                pose(ed13, round((p1[0] + rr * math.cos(a)) / 0.05) * 0.05, round((p1[1] + rr * math.sin(a)) / 0.05) * 0.05, rot, bottom)
                if fits(ed13, cop, ps, boxes):
                    ok = True
                    break
            if ok:
                break
        if ok:
            break
    if not ok:
        raise SystemExit("no room for ED13")
    rep.append("ED13 at (%.2f, %.2f), same face" % xy(ed13.GetPosition()))
    pcbnew.SaveBoard(EDIT, board, True)
    with_project(EDIT)
    print("\n".join("  " + s for s in rep))
    print("  -> " + EDIT)


def gnd_vias(board):
    """A 0.2 mm stub and a via from each ground pad of J22 / ED13 that has no copper yet, where it clears everything."""
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    cop = Copper(board)
    gnd = board.FindNet("GND")
    out = []
    for ref in ("J22", "ED13"):
        fp = board.FindFootprintByReference(ref)
        for p in fp.Pads():
            if p.GetNetname() != "GND":
                continue
            cx, cy = xy(p.GetPosition())
            face = pcbnew.B_Cu if fp.IsFlipped() else pcbnew.F_Cu
            done = None
            for rr in (0.7, 0.85, 1.0, 1.2, 1.4, 1.7, 2.0, 2.4, 2.8, 3.2):
                for k in range(32):
                    a = 2 * math.pi * k / 32
                    vx, vy = round((cx + rr * math.cos(a)) / 0.025) * 0.025, round((cy + rr * math.sin(a)) / 0.025) * 0.025
                    rv = VIA_D / 2
                    if not cop.rect_ok((vx - rv, vy - rv, vx + rv, vy + rv), None, "GND"):
                        continue
                    if cop.in_zone(vx, vy, face, "GND"):
                        continue                # (the inner planes of other nets clear round a via by themselves)
                    hw = STUB_W / 2             # the stub, walked in small boxes from the pad to the via
                    if not all(cop.rect_ok((cx + (vx - cx) * s / 10 - hw, cy + (vy - cy) * s / 10 - hw,
                                            cx + (vx - cx) * s / 10 + hw, cy + (vy - cy) * s / 10 + hw), face, "GND") for s in range(11)):
                        continue
                    done = (vx, vy)
                    break
                if done:
                    break
            if not done:
                out.append("%s.%s: no room for a ground via" % (ref, p.GetNumber()))
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(p.GetPosition())
            t.SetEnd(P(*done))
            t.SetWidth(FromMM(STUB_W))
            t.SetLayer(face)
            t.SetNet(gnd)
            board.Add(t)
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(P(*done))
            v.SetWidth(FromMM(VIA_D))
            v.SetDrill(FromMM(VIA_DRILL))
            v.SetNet(gnd)
            board.Add(v)
            cop.items.append(("GND", "c", None, done, VIA_D / 2))
            out.append("%s.%s: ground via at (%.2f, %.2f)" % (ref, p.GetNumber(), *done))
    return out


def stage_route():
    shutil.copyfile(EDIT, ROUTED)
    with_project(ROUTED)
    os.environ["CP_PCB"] = ROUTED
    import route as R
    from gen_pcb import OX, OY
    board = pcbnew.LoadBoard(ROUTED)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    o = ps.Outline(0)
    outline = [(ToMM(o.CPoint(i).x) - OX, ToMM(o.CPoint(i).y) - OY) for i in range(o.PointCount())]
    R.outline_pts = lambda: outline
    pads = [p for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == NET]
    xs = [ToMM(p.GetPosition().x) for p in pads]
    ys = [ToMM(p.GetPosition().y) for p in pads]
    bb = board.GetBoardEdgesBoundingBox()
    box = (ToMM(bb.GetLeft()) - 0.5, min(ys) - 8.0, ToMM(bb.GetRight()) + 0.5, max(ys) + 8.0)
    r = R.Router(board)
    reg = R.Region("pk", box[0] - OX, box[1] - OY, box[2] - OX, box[3] - OY)
    r.regs = [reg]
    r.build()
    r.items, r.failed = [], []
    code = {v: k for k, v in r.name_of.items()}[NET]
    _, bad = r.route_net(reg, code)
    r.flush(r.items)
    print("  %s routed in the window x %.1f..%.1f y %.1f..%.1f: %d pieces, %s" % (
        NET, box[0], box[2], box[1], box[3], len(r.items), "still open: %s" % bad if bad else "joined"), flush=True)
    for s in gnd_vias(board):
        print("  " + s)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(ROUTED, board, True)
    with_project(ROUTED)
    print("  -> " + ROUTED)


def stage_promote():
    if not os.path.exists(BACKUP):
        shutil.copyfile(FINAL, BACKUP)
    shutil.copyfile(ROUTED, FINAL)
    print("  %s kept as %s; the routed board is now the master" % (os.path.basename(FINAL), BACKUP))


if __name__ == "__main__":
    {"strip": stage_strip, "edit": stage_edit, "route": stage_route, "promote": stage_promote}[sys.argv[sys.argv.index("--stage") + 1]]()
