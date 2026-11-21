"""kbd_powerkey_board.py (keyboard; KiCad's Python, CP_ROOT = commander_keyboard) --stage edit|route|promote

The 2026-11-19 changes on the keyboard board, which is the master file (hand-made fixes: it is not rebuilt):
  edit     T16's infra-red LED off LED_K onto row A0 (its pad 6: the stub to the LED_K via taken out, the pad re-netted);
           J201 swapped for the mid-mount USB-C (HCTL HC-TYPE-C-16P-CB1.6, bottom face) with its notch cut into the
           left edge and its old fan-out taken out; the power-key parts Q201, R207, ED201 and J202 (2-pin JST-SH beside
           J201) placed on free spots of the bottom face          -> build/kbd_pk_edit.kicad_pcb
  route    the keyboard's router (kbd_board.make_router) on what is open: a window round T16 (A0), then its usual
           window round the USB-C / chip                                       -> build/kbd_pk_routed.kicad_pcb
  promote  the old board kept as build/kbd_before_powerkey.kicad_pcb, the routed one put in its place, then the
           keyboard's ground stage (vias for ground pads the pours do not reach)
Coordinates are KiCad page mm (the keyboard's "board mm").
"""
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew                                   # noqa: E402
from pcbnew import FromMM, ToMM, VECTOR2I       # noqa: E402

import cpmodel                                  # noqa: E402
import gen_pcb as GP                            # noqa: E402

ROOT, PRJ = cpmodel.ROOT, cpmodel.PRJ
FINAL = os.path.join(ROOT, PRJ + ".kicad_pcb")
BUILD = os.path.join(ROOT, "build")
EDIT = os.path.join(BUILD, "kbd_pk_edit.kicad_pcb")
ROUTED = os.path.join(BUILD, "kbd_pk_routed.kicad_pcb")
BACKUP = os.path.join(BUILD, "kbd_before_powerkey.kicad_pcb")

EDGE_X = -0.39                  # the board's left edge at the USB-C
USB_Y = 160.0
NOTCH_HW, NOTCH_D, NOTCH_R = 4.75, 6.60, 0.5
CLEAR_BOX = (-1.0, USB_Y - 5.6, 9.0, USB_Y + 5.6)       # J201's old fan-out: its copper here is taken out
CL = 0.2                        # pad to other copper when placing (the board's 0.15 plus a little)


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))


def xy(v):
    return ToMM(v.x), ToMM(v.y)


def with_project(path):
    """Give a board copy in build/ the project's rules (.kicad_pro, .kicad_dru), so KiCad and its filler use them."""
    for ext in (".kicad_pro", ".kicad_dru"):
        src = os.path.join(ROOT, PRJ + ext)
        if os.path.exists(src):
            shutil.copyfile(src, path[:-len(".kicad_pcb")] + ext)


# ------------------------------------------------------------------------------------------------- stage edit
def j201_local_rules(fp):
    """J201's own pad settings.  The board (converted from Altium) opens the solder mask 0.1 mm round every pad; on this
    receptacle's 0.5 mm row of 0.3 mm pads that leaves no mask between them - here 0, as on the numpad / touchpad.
    Its ground pads join the pours solid: thermal spokes have no room between the row's neighbours."""
    fp.SetLocalSolderMaskMargin(0)
    fp.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)


def court(fp):
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    c = fp.GetCourtyard(layer)
    bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
    return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())


def pose(fp, x, y, rot, bottom):
    if bottom != fp.IsFlipped():
        try:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        except (AttributeError, TypeError):
            fp.Flip(fp.GetPosition(), False)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))


def seg_rect_dist(a, b, r):
    """Distance from segment a-b to rectangle r = (x0, y0, x1, y1) (sampled; fine at these sizes)."""
    best = 1e9
    n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
    for k in range(n + 1):
        x, y = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
        dx = max(r[0] - x, 0, x - r[2])
        dy = max(r[1] - y, 0, y - r[3])
        best = min(best, math.hypot(dx, dy))
    return best


class Free:
    """Is a spot free on the bottom face: courtyard inside the board, off the cut-outs and the other bottom parts,
    its pads clear of the copper on B.Cu (tracks, vias, pads of other nets, through holes)."""

    def __init__(self, board):
        self.board = board
        self.ps = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(self.ps, True)
        self.boxes = [court(f) for f in board.GetFootprints() if f.IsFlipped()]
        self.copper = []                        # (net, kind, geometry)
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                self.copper.append((t.GetNetname(), "c", xy(t.GetPosition()), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2))
            elif t.GetLayer() == pcbnew.B_Cu:
                self.copper.append((t.GetNetname(), "s", (xy(t.GetStart()), xy(t.GetEnd())), ToMM(t.GetWidth()) / 2))
        for f in board.GetFootprints():
            for p in f.Pads():
                if p.IsOnLayer(pcbnew.B_Cu) or p.HasHole():
                    bb = p.GetBoundingBox()
                    self.copper.append((p.GetNetname(), "r", (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())), 0.0))

    def inside(self, x, y):
        return self.ps.Contains(pcbnew.VECTOR2I(FromMM(x), FromMM(y)))

    def ok(self, fp, edge_ok=False):
        c = court(fp)
        if any(not (c[2] <= b[0] or b[2] <= c[0] or c[3] <= b[1] or b[3] <= c[1]) for b in self.boxes):
            return False
        x0, y0, x1, y1 = c
        m = 0.0 if edge_ok else 0.3
        nx, ny = max(2, int((x1 - x0) / 0.4) + 1), max(2, int((y1 - y0) / 0.4) + 1)
        for i in range(nx):
            for j in range(ny):
                x, y = x0 + (x1 - x0) * i / (nx - 1), y0 + (y1 - y0) * j / (ny - 1)
                if edge_ok and x < EDGE_X + 0.5:
                    continue                    # (a connector's mouth stands on the edge)
                if not self.inside(x, y):
                    return False
        for p in fp.Pads():
            if not (p.IsOnLayer(pcbnew.B_Cu) or p.HasHole()):
                continue
            bb = p.GetBoundingBox()
            r = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
            for net, kind, g, w in self.copper:
                if net and net == p.GetNetname() and net != "":
                    continue
                if kind == "c":
                    (cx, cy), rad = g, w
                    dx, dy = max(r[0] - cx, 0, cx - r[2]), max(r[1] - cy, 0, cy - r[3])
                    if math.hypot(dx, dy) - rad < CL:
                        return False
                elif kind == "s":
                    a, b = g
                    if min(a[0], b[0]) - 2 > r[2] or max(a[0], b[0]) + 2 < r[0] or min(a[1], b[1]) - 2 > r[3] or max(a[1], b[1]) + 2 < r[1]:
                        continue
                    if seg_rect_dist(a, b, r) - w < CL:
                        return False
                else:
                    q = g
                    if not (r[2] + CL <= q[0] or q[2] + CL <= r[0] or r[3] + CL <= q[1] or q[3] + CL <= r[1]):
                        return False
        return True

    def take(self, fp):
        self.boxes.append(court(fp))
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            self.copper.append((p.GetNetname(), "r", (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())), 0.0))


def spiral_place(fp, free, tx, ty, rots=(0, 90, 180, 270), rmax=12.0, step=0.25):
    for rr in [0.0] + [step * k for k in range(1, int(rmax / step) + 1)]:
        n = max(1, int(2 * math.pi * rr / step))
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = round((tx + rr * math.cos(a)) / 0.05) * 0.05, round((ty + rr * math.sin(a)) / 0.05) * 0.05
            for rot in rots:
                pose(fp, x, y, rot, True)
                if free.ok(fp):
                    free.take(fp)
                    return True
    return False


def new_fp(board, d, nets, ref):
    c = d.comps[ref]
    fp = GP.load_fp(c.fp)
    fp.SetReference(c.ref)
    fp.SetValue(c.value)
    from gen_schematic import uid
    fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
    fp.SetSheetname("/" + c.sheet + "/")
    fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
    if c.desc and hasattr(fp, "SetLibDescription"):
        fp.SetLibDescription(c.desc)
    for pin, net in c.pins.items():
        for padname in cpmodel.pads_for(c, pin):
            for p in fp.Pads():
                if p.GetNumber() == padname and net:
                    p.SetNet(nets[net])
    if getattr(c, "dnp", False) or c.value.upper() == "DNP":
        fp.SetDNP(True)
    board.Add(fp)
    return fp


def stage_edit():
    d = cpmodel.load()
    if d.errors:
        raise SystemExit("\n".join(d.errors))
    os.makedirs(BUILD, exist_ok=True)
    shutil.copyfile(FINAL, EDIT)
    with_project(EDIT)
    board = pcbnew.LoadBoard(EDIT)
    nets = {}
    for name in sorted(d.nets()):
        ni = board.FindNet(name)
        if ni is None:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
        nets[name] = ni
    rep = []

    # ---- 0. every pad of the parts already on the board onto its net from the netlist (here: U201 pin 24 -> PWRKEY_DRV) ----
    for f in board.GetFootprints():
        c = d.comps.get(f.GetReference())
        if c is None or f.GetReference() in ("J201", "T16"):
            continue                            # (J201 is swapped below, T16 has its own step)
        for pin, net in c.pins.items():
            for pn in cpmodel.pads_for(c, pin):
                for p in f.Pads():
                    if p.GetNumber() == pn and net and p.GetNetname() != net:
                        rep.append("%s.%s: %r -> %s" % (f.GetReference(), pn, p.GetNetname(), net))
                        p.SetNet(nets[net])
        if c.value != f.GetValue():
            rep.append("%s value: %s -> %s" % (f.GetReference(), f.GetValue(), c.value))
            f.SetValue(c.value)

    # ---- 1. T16: its LED off LED_K, onto A0 ----
    t16 = board.FindFootprintByReference("T16")
    p6 = next(p for p in t16.Pads() if p.GetNumber() == "6")
    c6 = xy(p6.GetPosition())
    kill = []
    for t in board.GetTracks():
        if t.GetNetname() == "LED_K" and t.GetClass() != "PCB_VIA":
            ends = [xy(t.GetStart()), xy(t.GetEnd())]
            if any(math.hypot(e[0] - c6[0], e[1] - c6[1]) < 0.05 for e in ends) and ToMM(t.GetLength()) < 2.0:
                kill.append(t)
    p6.SetNet(nets["A0"])
    rep.append("T16 pad 6: %d LED_K stub piece(s) taken out, pad now on A0" % len(kill))

    # ---- 2. J201: the mid-mount USB-C, its notch, its old fan-out out ----
    old = board.FindFootprintByReference("J201")
    jnets = {p.GetNetname() for p in old.Pads() if p.GetNetname()}
    x0, y0, x1, y1 = CLEAR_BOX
    for t in board.GetTracks():
        if t.GetNetname() not in jnets:
            continue
        pts = [xy(t.GetPosition())] if t.GetClass() == "PCB_VIA" else [xy(t.GetStart()), xy(t.GetEnd())]
        if any(x0 <= px <= x1 and y0 <= py <= y1 for px, py in pts):
            kill.append(t)
    rep.append("J201's old fan-out: %d tracks / vias taken out" % (len(kill) - len(rep) + 0))
    path, sheet, sfile = old.GetPath(), old.GetSheetname(), old.GetSheetfile()
    jfp = new_fp(board, d, nets, "J201")
    j201_local_rules(jfp)
    jfp.SetPath(path)
    jfp.SetSheetname(sheet)
    jfp.SetSheetfile(sfile)
    best = None
    for rot in (0, 90, 180, 270):               # the turn that puts its pads inside the board, 7.35 mm in from the edge
        pose(jfp, EDGE_X, USB_Y, rot, True)
        pts = [xy(p.GetPosition()) for p in jfp.Pads() if p.GetNumber() not in ("SH", "")]
        cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        err = abs(cx - (EDGE_X + 7.35)) + abs(cy - USB_Y)
        if best is None or err < best[0]:
            best = (err, rot)
    pose(jfp, EDGE_X, USB_Y, best[1], True)
    rep.append("J201: HCTL mid-mount, bottom face, origin on the edge (%.2f, %.2f), turned %d (pad row %.2f mm off)" % (EDGE_X, USB_Y, best[1], best[0]))
    # Its D+ / D- pads alternate along the row (B6 A7 A6 B7): one of them has to change layers right at the pad.  A6 (D+)
    # gets a stub straight in from the edge and a 0.5 / 0.3 via just past the pad row (0.5 mm pitch: the via clears the
    # stubs of A7 and B7 on either side by 0.175 mm); D- then leaves on the bottom face, D+ crosses over on the top.
    a6 = next(p for p in jfp.Pads() if p.GetNumber() == "A6")
    ax_, ay_ = xy(a6.GetPosition())
    vx_ = ax_ + 1.14
    st = pcbnew.PCB_TRACK(board)
    st.SetStart(a6.GetPosition())
    st.SetEnd(P(vx_, ay_))
    st.SetWidth(FromMM(0.15))
    st.SetLayer(pcbnew.B_Cu)
    st.SetNet(nets["USB_CON_DP"])
    board.Add(st)
    vv = pcbnew.PCB_VIA(board)
    vv.SetPosition(P(vx_, ay_))
    vv.SetWidth(FromMM(0.50))
    vv.SetDrill(FromMM(0.30))
    vv.SetNet(nets["USB_CON_DP"])
    board.Add(vv)
    rep.append("J201.A6 (D+): stub and 0.5 / 0.3 via at (%.2f, %.2f), its crossing to the top face" % (vx_, ay_))
    # the notch in Edge.Cuts: the straight left edge is split round it
    edge = None
    for dr in board.GetDrawings():
        if dr.GetLayer() == pcbnew.Edge_Cuts and dr.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            (ax, ay), (bx, by) = xy(dr.GetStart()), xy(dr.GetEnd())
            if abs(ax - EDGE_X) < 0.01 and abs(bx - EDGE_X) < 0.01 and min(ay, by) < USB_Y - NOTCH_HW and max(ay, by) > USB_Y + NOTCH_HW:
                edge = dr
    if edge is None:
        raise SystemExit("the left edge segment at the USB-C was not found")
    (ax, ay), (bx, by) = xy(edge.GetStart()), xy(edge.GetEnd())
    lo, hi = min(ay, by), max(ay, by)
    w = edge.GetWidth()

    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(w)
        board.Add(s)

    def arc3(a, m, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(*a), P(*m), P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(w)
        board.Add(s)
    e, a0, a1, dd, rr = EDGE_X, USB_Y - NOTCH_HW, USB_Y + NOTCH_HW, NOTCH_D, NOTCH_R
    k = 1 - math.sqrt(0.5)
    seg((e, lo), (e, a0))
    seg((e, a0), (e + dd - rr, a0))
    arc3((e + dd - rr, a0), (e + dd - rr * k, a0 + rr * k), (e + dd, a0 + rr))
    seg((e + dd, a0 + rr), (e + dd, a1 - rr))
    arc3((e + dd, a1 - rr), (e + dd - rr * k, a1 - rr * k), (e + dd - rr, a1))
    seg((e + dd - rr, a1), (e, a1))
    seg((e, a1), (e, hi))
    board.Remove(edge)
    rep.append("notch %.2f x %.2f mm, R%.1f, cut into the left edge at y %.2f..%.2f" % (2 * NOTCH_HW, NOTCH_D, NOTCH_R, a0, a1))

    # ---- 3. the power-key parts on free spots of the bottom face ----
    for t in kill:
        board.Remove(t)
    board.Remove(old)
    free = Free(board)
    free.take(jfp)
    u201 = board.FindFootprintByReference("U201")
    pin24 = xy(next(p for p in u201.Pads() if p.GetNumber() == "24").GetPosition())
    ucx, ucy = xy(u201.GetPosition())
    out = (pin24[0] - ucx, pin24[1] - ucy)
    n_ = math.hypot(*out) or 1.0
    q201 = new_fp(board, d, nets, "Q201")
    r207 = new_fp(board, d, nets, "R207")
    j202 = new_fp(board, d, nets, "J202")
    ed201 = new_fp(board, d, nets, "ED201")
    placed = []
    if spiral_place(q201, free, pin24[0] + out[0] / n_ * 3.0, pin24[1] + out[1] / n_ * 3.0):
        placed.append("Q201 at (%.2f, %.2f)" % xy(q201.GetPosition()))
    if spiral_place(r207, free, *xy(q201.GetPosition())):
        placed.append("R207 at (%.2f, %.2f)" % xy(r207.GetPosition()))
    # J202: mouth on the left edge, beside J201 (above it first, then below)
    ok = False
    for yy in [USB_Y - 9.5 - 0.5 * k for k in range(0, 40)] + [USB_Y + 9.0 + 0.5 * k for k in range(0, 8)]:
        for rot in (0, 90, 180, 270):
            pose(j202, 20.0, yy, rot, True)
            pads = [xy(p.GetPosition()) for p in j202.Pads() if p.GetNumber() in ("1", "2")]
            px = sum(p[0] for p in pads) / len(pads)
            c = court(j202)
            if px < (c[0] + c[2]) / 2:
                continue                        # the mouth (away from the pads) has to face the edge, on the left
            j202.SetPosition(VECTOR2I(j202.GetPosition().x + FromMM(EDGE_X - c[0]), j202.GetPosition().y))
            if free.ok(j202, edge_ok=True):
                free.take(j202)
                ok = True
                break
        if ok:
            break
    if ok:
        placed.append("J202 at (%.2f, %.2f)" % xy(j202.GetPosition()))
    p1 = xy(next(p for p in j202.Pads() if p.GetNumber() == "1").GetPosition())
    if spiral_place(ed201, free, p1[0] + 3.0, p1[1]):
        placed.append("ED201 at (%.2f, %.2f)" % xy(ed201.GetPosition()))
    rep.append("placed on the bottom face: " + ", ".join(placed))
    if len(placed) < 4:
        rep.append("NOT all placed!")
    pcbnew.SaveBoard(EDIT, board, True)
    with_project(EDIT)
    print("\n".join("  " + s for s in rep))
    print("  -> " + EDIT)


# ------------------------------------------------------------------------------------------------ stage route
def stage_route():
    import kbd_board as K
    with_project(EDIT)
    shutil.copyfile(EDIT, ROUTED)
    with_project(ROUTED)
    usb = ("USB_CON_DP", "USB_CON_DM", "KB_CC1", "KB_CC2", "VBUS_USB")
    route_passes([("round T16 (A0)", (276.0, 36.0, 298.0, 50.0), None, 1),
                  # the USB-C's own fan-out first, in a small window: its D+ / D- pads alternate (B6 A7 A6 B7); A6
                  # has its crossing via from the edit stage
                  ("USB-C fan-out", (-1.5, 150.0, 20.0, 170.0), usb, 1),
                  ("the rest", K.ROUTE_BOX, None, 1)])


def stage_fixfp():
    """j201_local_rules() on the routed board (for a board routed before they were in the edit stage)."""
    board = pcbnew.LoadBoard(ROUTED)
    j201_local_rules(board.FindFootprintByReference("J201"))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(ROUTED, board, True)
    with_project(ROUTED)
    print("  J201: mask margin 0, ground pads solid -> " + ROUTED)


def stage_route_more():
    """Whatever the route stage left open, once more on the routed board with 8 times the search budget: the power-key
    line from Q201 (by the microcontroller) to J202 (by the USB-C) is 135 mm long, past every column of the matrix."""
    import kbd_board as K
    route_passes([("the rest, longer searches", K.ROUTE_BOX, None, 8)])


def route_passes(passes):
    import random
    import kbd_board as K
    log = []
    for title, box, only, mult in passes:
        board = pcbnew.LoadBoard(ROUTED)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        board.BuildConnectivity()
        K.ROUTE_BOX = box
        r, reg, code = K.make_router(board)
        import route as R
        if not hasattr(R, "_search0"):
            R._search0 = R.search
        R.search = (lambda *a, max_exp=1500000, _m=mult, **k: R._search0(*a, max_exp=max_exp * _m, **k)) if mult > 1 else R._search0
        code = {v: k for k, v in r.name_of.items()}
        for n in ("USB_CON_DP", "USB_CON_DM"):
            r.rc_of[code[n]] = R.RCS["FAN"]     # (0.5 / 0.3 vias: they fit between the 0.5 mm pad rows)
        nets = K.split_nets(r, reg)
        if only:
            nets = [n for n in nets if r.name_of[n] in only]
        names = [r.name_of[n] for n in nets]
        best = None
        rnd = random.Random(3)
        import copy
        snap_D = {k: D.copy() for k, D in reg.D.items()}
        snap = (reg.novia.copy(), list(reg.uf), {n: dict(v) for n, v in reg.tree.items()}, {n: dict(v) for n, v in reg.exact.items()})
        order = list(nets)
        for attempt in range(int(os.environ.get("CP_ORDERS", "8"))):
            if attempt:
                for k, D in reg.D.items():
                    D[...] = snap_D[k]
                reg.novia[...] = snap[0]
                reg.uf[:] = snap[1]
                reg.tree.clear(); reg.tree.update({n: dict(v) for n, v in snap[2].items()})
                reg.exact.clear(); reg.exact.update({n: dict(v) for n, v in snap[3].items()})
                r.items[:] = []
                rnd.shuffle(order)
            left = []
            for n in order:
                _, bad = r.route_net(reg, n)
                if bad:
                    left.append("%s (%s)" % (r.name_of[n], "; ".join(bad)))
            if best is None or len(left) < len(best[0]):
                best = (left, list(r.items))
            if not left:
                break
        r.items[:] = best[1]
        r.flush(r.items)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(ROUTED, board, True)
        with_project(ROUTED)
        log.append("%s: %d nets open before (%s), still open: %s" % (title, len(names), " ".join(names) or "-", " ".join(best[0]) or "-"))
        print("  " + log[-1], flush=True)
        del board
    print("  -> " + ROUTED)


# ---------------------------------------------------------------------------------------------- stage promote
def stage_promote():
    if not os.path.exists(BACKUP):
        shutil.copyfile(FINAL, BACKUP)
    shutil.copyfile(ROUTED, FINAL)
    print("  %s kept as %s; the routed board is now the master" % (os.path.basename(FINAL), BACKUP), flush=True)
    rc = subprocess.run([sys.executable, os.path.join(HERE, "kbd_board.py"), "--stage", "ground"]).returncode
    if rc:
        raise SystemExit("ground stage failed")


def main():
    stage = sys.argv[sys.argv.index("--stage") + 1]
    {"edit": stage_edit, "route": stage_route, "route_more": stage_route_more, "fixfp": stage_fixfp, "promote": stage_promote}[stage]()


if __name__ == "__main__":
    main()
