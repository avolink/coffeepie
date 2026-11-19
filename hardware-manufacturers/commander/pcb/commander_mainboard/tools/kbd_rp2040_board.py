"""kbd_rp2040_board.py (keyboard; KiCad's Python, CP_ROOT = commander_keyboard) --stage plan|edit|route|route_more|promote

2026-11-19 (user's request: QMK / VIA): the keyboard's STC8H8K64U is replaced by a Raspberry Pi RP2040 with its QSPI
flash (GD25Q16E), 12 MHz crystal and a 3.3 V LDO (ME6211).  The keyboard board is the master file (hand-made fixes;
it is not rebuilt), so this edits it in place, like kbd_powerkey_board.py:

  plan     where each matrix line (and the power-key output, the LED enable) arrives at the chip once the STC's own
           copper is gone; the RP2040's turn (USB / QSPI side towards the USB series resistors) and, keeping the
           angular order (no crossings), the GPIO each line gets.  Writes that pin table into the netlist
           (src/netlist/01_kbd_mcu.net, between the GPIO markers) and build/kbd_rp_plan.json.
  edit     the STC, its capacitors, boot button and its fan-out out; the RP2040 in its place (bottom face), four
           ground vias in its exposed pad; flash, crystal, LDO and capacitors on free spots round it; the 16 column
           pull-ups' supply track cut off the 5 V bus (it becomes their 3.3 V rail)      -> build/kbd_rp_edit.kicad_pcb
  route    the keyboard's router on everything open, first in a window round the chip  -> build/kbd_rp_routed.kicad_pcb
  promote  the old board kept as build/kbd_before_rp2040.kicad_pcb, the routed one put in its place, then the keyboard's
           ground stage (vias for ground pads the pours do not reach)
Coordinates are KiCad page mm (the keyboard's "board mm").
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew                                   # noqa: E402
from pcbnew import FromMM, ToMM, VECTOR2I       # noqa: E402

import cpmodel                                  # noqa: E402
import gen_pcb as GP                            # noqa: E402
import kbd_powerkey_board as PK                 # noqa: E402  (Free, spiral_place, pose, new_fp, court, with_project, route_passes)

ROOT, PRJ = cpmodel.ROOT, cpmodel.PRJ
FINAL = os.path.join(ROOT, PRJ + ".kicad_pcb")
BUILD = os.path.join(ROOT, "build")
EDIT = os.path.join(BUILD, "kbd_rp_edit.kicad_pcb")
ROUTED = os.path.join(BUILD, "kbd_rp_routed.kicad_pcb")
BACKUP = os.path.join(BUILD, "kbd_before_rp2040.kicad_pcb")
PLAN = os.path.join(BUILD, "kbd_rp_plan.json")
NETFILE = os.path.join(ROOT, "src", "netlist", "01_kbd_mcu.net")

# The RP2040 sits 2.2 mm east of the STC's centre (140.70, 147.40): its crystal (pins 20 / 21, the middle of the west
# side) needs room between the chip and where the column lines come in from the west (x 132.6).
CENTRE = (142.90, 147.40)
# the STC's own parts that go (U201 is replaced); R203 / R204 (the USB series resistors, 27 ohm now) are placed anew
GONE = ("U201", "C201", "C203", "C204", "C205", "C206", "R206", "SW201", "R203", "R204")
# where lines come in: no new parts in these bands (round CENTRE: dx0, dy0, dx1, dy1) - north, south, west, and the two
# east corners that A2 (to the south-east corner) and D0_RX (to the north-east corner) take round the chip
LANES = [(-6.8, -8.4, 6.8, -3.5), (-6.8, 3.5, 6.8, 8.4), (-10.6, -6.8, -3.5, 6.8),
         (3.5, 3.2, 12.5, 8.4),                 # (south-east: A2 and D0_RX come round to the south-east corner)
         (3.5, -1.9, 6.2, 3.2)]                 # (east: the USB and flash pins' way out)
# ... except the crystal's group, south of the middle of the west lane: the column lines that come in at the middle
# (D8, D9, D11) pass north of it, D6 south of it
CRYSTAL_ZONE = (-10.4, 0.6, -3.6, 5.2)
# pins with a fixed role that face where lines come in: they are counted in the GPIO plan so that no line crosses them
FIXED_OUT = {"20": "XTAL"}                     # (XIN 20 and XOUT 21 as one: the crystal's group lies in front of both)
# copper of the nets of those parts that is taken out: in these boxes (the chip with its fan-out, the parts east of it)
CLEAR = [(132.6, 139.3, 148.8, 155.5), (144.0, 138.3, 154.6, 155.5)]
# the matrix lines etc. that get a GPIO, in no particular order (the plan stage orders them round the chip)
LINES = ["A0", "A1", "A2", "A3", "A4", "A5", "MOSI", "SCK", "MISO", "SS_RXLED", "D0_RX", "D2_SDA", "D3_SCL",
         "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12", "D13", "PWRKEY_DRV"]
GPIO_PINS = {str(n): "GPIO%d" % g for n, g in zip(
    [2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 41],
    range(30))}
# the pull-ups' supply: the top-layer rail at y 169.4 reaches the 5 V bus on the bottom layer through one via at its east
# end; that riser and via go, the rail and the pull-ups' pin 1 become VCC3V3
PU_RISER_VIA = (145.05, 167.57)
PU_RAIL_Y = (169.0, 169.7)
PU_RAIL_X = (111.0, 145.3)


def xy(v):
    return ToMM(v.x), ToMM(v.y)


def in_box(p, b):
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def item_points(t):
    return [xy(t.GetPosition())] if t.GetClass() == "PCB_VIA" else [xy(t.GetStart()), xy(t.GetEnd())]


def gone_nets(board):
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    return {p.GetNetname() for r in GONE if r in fps for p in fps[r].Pads() if p.GetNetname()}


def in_clear(p):
    return any(in_box(p, b) for b in CLEAR)


def doomed_copper(board, nets):
    """Copper of `nets` in the CLEAR boxes: (kill, trim).  Vias in a box and tracks with both ends in the boxes go;
    a track with one end in a box is cut back to where it leaves the boxes: trim = [(track, end index, new point)]."""
    kill, trim = [], []
    for t in board.GetTracks():
        if t.GetNetname() not in nets:
            continue
        pts = item_points(t)
        ins = [in_clear(p) for p in pts]
        if all(ins):
            kill.append(t)
        elif any(ins):
            k = ins.index(True)
            a, b = pts[1 - k], pts[k]           # from the outside end towards the inside one
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            n = max(2, int(L / 0.05))
            last = a
            for s in range(1, n + 1):
                q = (a[0] + (b[0] - a[0]) * s / n, a[1] + (b[1] - a[1]) * s / n)
                if in_clear(q):
                    break
                last = q
            trim.append((t, k, last))
    return kill, trim


def arrivals(board, kill_ids, trim=()):
    """For each line: the point of its remaining copper (or pads of parts that stay) nearest the chip's centre."""
    cx, cy = CENTRE
    best = {}
    trimmed = {t.m_Uuid.AsString(): (k, q) for t, k, q in trim}
    for t in board.GetTracks():
        n = t.GetNetname()
        if n not in LINES or t.m_Uuid.AsString() in kill_ids:
            continue
        pts = item_points(t)
        if t.m_Uuid.AsString() in trimmed:
            k, q = trimmed[t.m_Uuid.AsString()]
            pts[k] = q
        for p in pts:
            d = math.hypot(p[0] - cx, p[1] - cy)
            if n not in best or d < best[n][0]:
                best[n] = (d, p)
    for z in board.Zones():                     # (the rows reach the chip area through zones of their own too)
        n = z.GetNetname()
        if n not in LINES:
            continue
        o = z.Outline()
        for k in range(o.OutlineCount()):
            ring = o.Outline(k)
            pts = [xy(ring.CPoint(i)) for i in range(ring.PointCount())]
            for a_, b_ in zip(pts, pts[1:] + pts[:1]):
                for s in range(11):             # (points along each edge)
                    q = (a_[0] + (b_[0] - a_[0]) * s / 10, a_[1] + (b_[1] - a_[1]) * s / 10)
                    d = math.hypot(q[0] - cx, q[1] - cy)
                    if n not in best or d < best[n][0]:
                        best[n] = (d, q)
    for f in board.GetFootprints():
        if f.GetReference() in GONE:
            continue
        for p in f.Pads():
            n = p.GetNetname()
            if n in LINES:
                q = xy(p.GetPosition())
                d = math.hypot(q[0] - cx, q[1] - cy)
                if n not in best or d < best[n][0]:
                    best[n] = (d, q)
    return best


def rp_pads(rot):
    """The RP2040's pads (number -> (x, y)) at CENTRE, bottom face, turned `rot`."""
    fp = GP.load_fp(cpmodel.PARTS["RP2040"]["fp"])
    b = pcbnew.BOARD()
    b.Add(fp)
    PK.pose(fp, CENTRE[0], CENTRE[1], rot, True)
    return {p.GetNumber(): xy(p.GetPosition()) for p in fp.Pads()}


def ang(p):
    return math.atan2(p[1] - CENTRE[1], p[0] - CENTRE[0])


def adiff(a, b):
    d = abs(a - b) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def assign(lines, gpios):
    """Order-keeping assignment round the circle: lines (name, angle) and gpios (pad, angle), both sorted by angle;
    every line gets a different GPIO, the cyclic order is kept (no two connections cross), the summed angular
    distance is the least.  Returns (cost, {line: pad})."""
    L, G = len(lines), len(gpios)
    best = None
    for s in range(L):                          # which line goes first
        ls = lines[s:] + lines[:s]
        for g0 in range(G):                     # ... onto which GPIO at the earliest
            gs = gpios[g0:] + gpios[:g0]
            INF = 1e18
            # dp[i][j]: lines[:i] placed on gs[:j]
            dp = [[INF] * (G + 1) for _ in range(L + 1)]
            ch = [[None] * (G + 1) for _ in range(L + 1)]
            for j in range(G + 1):
                dp[0][j] = 0.0
            for i in range(1, L + 1):
                for j in range(i, G + 1):
                    skip = dp[i][j - 1]
                    ln, gn = ls[i - 1][0], gs[j - 1][0]
                    fixed = (ln in FIXED_OUT.values()) or (gn in FIXED_OUT)
                    take = dp[i - 1][j - 1] + (adiff(ls[i - 1][1], gs[j - 1][1]) if not fixed
                                               else 0.0 if FIXED_OUT.get(gn) == ln else 1e3)
                    if take <= skip:
                        dp[i][j], ch[i][j] = take, "t"
                    else:
                        dp[i][j], ch[i][j] = skip, "s"
            if best is None or dp[L][G] < best[0]:
                m, i, j = {}, L, G
                while i > 0:
                    if ch[i][j] == "t":
                        m[ls[i - 1][0]] = gs[j - 1][0]
                        i -= 1
                    j -= 1
                best = (dp[L][G], m)
    return best


# --------------------------------------------------------------------------------------------------- stage plan
def stage_plan():
    board = pcbnew.LoadBoard(FINAL)
    nets = gone_nets(board)
    kill, trim = doomed_copper(board, nets)
    kill_ids = {t.m_Uuid.AsString() for t in kill}
    print("  STC copper: %d tracks / vias go, %d tracks cut back to the cleared area's border" % (len(kill), len(trim)))
    arr = arrivals(board, kill_ids, trim)
    missing = [n for n in LINES if n not in arr]
    if missing:
        raise SystemExit("no copper found for: " + " ".join(missing))
    lines = sorted(((n, ang(arr[n][1])) for n in LINES), key=lambda t: t[1])
    usb_to = [xy(p.GetPosition()) for f in board.GetFootprints() if f.GetReference() in ("R203", "R204")
              for p in f.Pads() if p.GetNetname().startswith("USB_MCU")]
    ux, uy = sum(p[0] for p in usb_to) / len(usb_to), sum(p[1] for p in usb_to) / len(usb_to)
    res = []
    for rot in (0, 90, 180, 270):
        pads = rp_pads(rot)
        gp = sorted(((n, ang(pads[n])) for n in list(GPIO_PINS) + list(FIXED_OUT)), key=lambda t: t[1])
        # (the crystal block: at the angle of the crystal's group - CRYSTAL_ZONE, board frame round CENTRE)
        zxy = (CENTRE[0] + (CRYSTAL_ZONE[0] + CRYSTAL_ZONE[2]) / 2, CENTRE[1] + (CRYSTAL_ZONE[1] + CRYSTAL_ZONE[3]) / 2)
        ls_ = sorted(lines + [(nm, ang(zxy)) for pn, nm in FIXED_OUT.items()], key=lambda t: t[1])
        cost, m = assign(ls_, gp)
        for nm in FIXED_OUT.values():
            m.pop(nm, None)
        usb = (math.hypot(pads["46"][0] - ux, pads["46"][1] - uy) + math.hypot(pads["47"][0] - ux, pads["47"][1] - uy)) / 2
        res.append((cost + usb / 3.0, rot, cost, usb, m, pads))
    res.sort(key=lambda t: t[0])
    for tot, rot, cost, usb, m, pads in res:
        print("  turn %3d: angular cost %.2f rad, USB pads %.1f mm from R203 / R204" % (rot, cost, usb))
    tot, rot, cost, usb, m, pads = res[0]
    print("  chosen: turn %d" % rot)
    for n, a in lines:
        pad = m[n]
        print("    %-10s arrives at (%.2f, %.2f) %6.1f deg -> pin %2s %-7s %6.1f deg"
              % (n, arr[n][1][0], arr[n][1][1], math.degrees(a), pad, GPIO_PINS[pad], math.degrees(ang(pads[pad]))))
    json.dump(dict(rot=rot, pins={n: m[n] for n in LINES}, gpio={n: GPIO_PINS[m[n]] for n in LINES},
                   arrivals={n: arr[n][1] for n in LINES}), open(PLAN, "w"), indent=1)
    # the pin table into the netlist, between the markers
    txt = open(NETFILE, encoding="utf-8").read()
    a, b = "# >>> GPIO table (written by tools/kbd_rp2040_board.py --stage plan) >>>", "# <<< GPIO table <<<"
    used = set(m.values())
    if cost >= 1e3:
        raise SystemExit("no plan keeps the crystal pins clear")
    body = ["P U201 " + " ".join("%s=%s" % (m[n], n) for n in sorted(LINES, key=lambda n: int(m[n])))]
    free_ = sorted((p for p in GPIO_PINS if p not in used), key=int)
    if free_:
        body.append("NC U201 " + " ".join(free_) + "    # spare GPIO: " + " ".join(GPIO_PINS[p] for p in free_))
    body.append("# GPIO of each line (QMK pin names):")
    for n in sorted(LINES, key=lambda n: int(GPIO_PINS[m[n]][4:])):
        body.append("#   %-10s GP%s" % (n, GPIO_PINS[m[n]][4:]))
    i, j = txt.index(a), txt.index(b)
    txt = txt[:i + len(a)] + "\n" + "\n".join(body) + "\n" + txt[j:]
    open(NETFILE, "w", encoding="utf-8", newline="\n").write(txt)
    print("  -> " + PLAN + " and the GPIO table in " + os.path.relpath(NETFILE, ROOT))


# --------------------------------------------------------------------------------------------------- stage edit
def fine_pitch_rules(fp):
    """The board (converted from Altium) opens the solder mask 0.1 mm round every pad: on the RP2040's 0.4 mm pitch
    that leaves no mask between its pads - 0 here (as on the USB-C)."""
    fp.SetLocalSolderMaskMargin(0)


def add_track(board, net, a, b, w, layer=pcbnew.B_Cu):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(PK.P(*a))
    t.SetEnd(PK.P(*b))
    t.SetWidth(FromMM(w))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)
    return t


def add_via(board, net, p, d=0.5, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(PK.P(*p))
    v.SetWidth(FromMM(d))
    v.SetDrill(FromMM(drill))
    v.SetNet(net)
    board.Add(v)
    return v


def outward(pad_xy, k):
    """A point k mm further out from the chip's centre than pad_xy, square to the chip's side the pad is on."""
    dx, dy = pad_xy[0] - CENTRE[0], pad_xy[1] - CENTRE[1]
    if abs(dx) > abs(dy):
        return (pad_xy[0] + math.copysign(k, dx), pad_xy[1])
    return (pad_xy[0], pad_xy[1] + math.copysign(k, dy))


def under_chip(board, nets, pxy):
    """Copper drawn under the RP2040 before anything is routed (its pins are 0.4 mm apart: lines come in on three
    sides, so the supply pins there cannot reach out).  In the chip's own frame (a east, b south, mm from CENTRE):
      - TESTEN (19): a track in to the exposed pad (ground)
      - VCC3V3 pins 10 (south), 22 (west), 33 (north), 1 and 42 (the two east corners): a 0.5 / 0.3 via each in the
        1.45 mm ring between the pads and the exposed pad, joined on the top face; the router takes the network on
      - VDD11 (core 1.1 V): pins 45 and 50 (east) joined in that ring on the bottom face, a via at pin 50, a loop on the
        top face round the south of the VCC3V3 network to a via for pin 23 (west)."""
    import numpy as np                          # noqa: F401
    c = CENTRE

    def unit(p):
        v = (p[0] - c[0], p[1] - c[1])
        k = max(abs(v[0]), abs(v[1]))
        return (round(v[0] / k), round(v[1] / k)) if abs(v[0]) > abs(v[1]) else (round(v[0] / k), round(v[1] / k))
    E = unit(pxy["49"])
    S = unit(pxy["10"])
    E = (E[0], 0) if abs(E[0]) else (0, E[1])
    S = (S[0], 0) if abs(S[0]) else (0, S[1])

    def P(a, b):
        return (c[0] + a * E[0] + b * S[0], c[1] + a * E[1] + b * S[1])

    def R(n):
        p = pxy[n]
        v = (p[0] - c[0], p[1] - c[1])
        return (v[0] * E[0] + v[1] * E[1], v[0] * S[0] + v[1] * S[1])
    v3, v11, gnd = nets["VCC3V3"], nets["VDD11"], nets["GND"]
    B, F = pcbnew.B_Cu, pcbnew.F_Cu
    # TESTEN
    a19 = R("19")
    add_track(board, gnd, pxy["19"], P(-1.4, a19[1]), 0.15, B)
    # VCC3V3: inner vias
    vias = {}
    for n, side in (("22", "W"), ("33", "N"), ("10", "S"), ("42", "N"), ("1", "S")):
        a, b = R(n)
        q = P(-2.35, b) if side == "W" else P(a, -2.35) if side == "N" else P(a, 2.35)
        add_track(board, v3, pxy[n], q, 0.15, B)
        add_via(board, v3, q)
        vias[n] = q
    y22, x33, x10 = R("22")[1], R("33")[0], R("10")[0]
    for pts in ([vias["22"], P(-1.7, y22), P(-1.7, -2.35), vias["33"], vias["42"]],
                [P(-1.7, y22), P(-1.7, 1.7), vias["10"], vias["1"]],
                [vias["33"], P(x33, -3.9)]):                  # (the way out, north, on the top face)
        for a_, b_ in zip(pts, pts[1:]):
            add_track(board, v3, a_, b_, 0.2, F)
    # VDD11
    a23, b23 = R("23")
    v23 = P(-2.35, b23 - 0.7)
    add_track(board, v11, pxy["23"], P(-2.85, b23), 0.15, B)
    add_track(board, v11, P(-2.85, b23), v23, 0.15, B)
    add_via(board, v11, v23)
    # East side: every supply pin goes INWARD (only USB 46 / 47 and the flash 51-56 leave east, in order):
    #   43, 44 (VCC3V3) to pin 42's inner via; 48, 49 (VCC3V3) to a via of their own, joined on the top face to the
    #   VCC3V3 line; 45, 50 (VDD11) to vias of their own on the VDD11 loop, which also leaves north (top face) to a via
    #   for the core supply's capacitors.  (Vias at least 0.9 mm apart: 0.4 mm of copper between them.)
    b45, b50 = R("45")[1], R("50")[1]
    for n in ("43", "44"):
        add_track(board, v3, pxy[n], P(2.9, R(n)[1]), 0.15, B)
        add_track(board, v3, P(2.9, R(n)[1]), vias["42"], 0.15, B)
    v48 = P(2.35, -0.5)
    add_track(board, v3, pxy["48"], P(2.9, R("48")[1]), 0.15, B)
    add_track(board, v3, P(2.9, R("48")[1]), v48, 0.15, B)
    add_track(board, v3, pxy["49"], P(2.9, R("49")[1]), 0.15, B)
    add_track(board, v3, P(2.9, R("49")[1]), v48, 0.15, B)
    add_via(board, v3, v48)
    for a_, b_ in zip([v48, P(1.7, -0.5), P(1.7, -2.35)], [P(1.7, -0.5), P(1.7, -2.35), vias["42"]]):
        add_track(board, v3, a_, b_, 0.2, F)
    v45, v50 = P(2.35, -1.4), P(2.35, 0.4)
    add_track(board, v11, pxy["45"], P(2.9, b45), 0.15, B)
    add_track(board, v11, P(2.9, b45), v45, 0.15, B)
    add_track(board, v11, pxy["50"], P(2.9, b50), 0.15, B)
    add_track(board, v11, P(2.9, b50), v50, 0.15, B)
    add_via(board, v11, v45)
    add_via(board, v11, v50)
    out11 = P(3.1, -4.4)
    loop = [v23, P(-3.1, b23 - 0.7), P(-3.1, 3.1), P(3.1, 3.1), P(3.1, 0.4), P(3.1, -1.4), out11]
    for a_, b_ in zip(loop, loop[1:]):
        add_track(board, v11, a_, b_, 0.2, F)
    add_track(board, v11, P(3.1, 0.4), v50, 0.2, F)
    add_track(board, v11, P(3.1, -1.4), v45, 0.2, F)
    add_via(board, v11, out11)


def stage_edit():
    d = cpmodel.load()
    if d.errors:
        raise SystemExit("\n".join(d.errors))
    plan = json.load(open(PLAN))
    os.makedirs(BUILD, exist_ok=True)
    shutil.copyfile(FINAL, EDIT)
    PK.with_project(EDIT)
    board = pcbnew.LoadBoard(EDIT)
    nets = {}
    for name in sorted(d.nets()):
        ni = board.FindNet(name)
        if ni is None:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
        nets[name] = ni
    rep = []

    # ---- 1. the STC's copper out (or cut back to the cleared area's border), its parts out ----
    gone = gone_nets(board)
    kill, trim = doomed_copper(board, gone)
    for t, k, q in trim:
        (t.SetStart if k == 0 else t.SetEnd)(PK.P(*q))
    # ---- 2. the pull-ups' rail off the 5 V bus ----
    riser = []
    for t in board.GetTracks():
        if t.GetNetname() != "VCC5":
            continue
        pts = item_points(t)
        if t.GetClass() == "PCB_VIA":
            if math.hypot(pts[0][0] - PU_RISER_VIA[0], pts[0][1] - PU_RISER_VIA[1]) < 0.05:
                riser.append(t)
        elif t.GetLayer() == pcbnew.F_Cu and all(PU_RAIL_X[0] <= p[0] <= PU_RAIL_X[1] for p in pts) \
                and all(PU_RAIL_Y[0] - 1.8 <= p[1] <= PU_RAIL_Y[1] for p in pts):
            if all(PU_RAIL_Y[0] <= p[1] <= PU_RAIL_Y[1] for p in pts) and max(p[0] for p in pts) < 144.0:
                t.SetNet(nets["VCC3V3"])        # the rail along the pull-ups
            else:
                riser.append(t)                 # its end towards the via (x 142.96 .. 145.05)
    kill += riser
    rep.append("STC copper: %d tracks / vias out, %d cut back; pull-up rail: %d riser pieces / via out, rest now VCC3V3"
               % (len(kill) - len(riser), len(trim), len(riser)))
    for t in kill:
        board.Remove(t)
    for r in GONE:
        f = board.FindFootprintByReference(r)
        if f is not None:
            board.Remove(f)

    # ---- 3. every pad of the parts that stay onto its net from the netlist, values too ----
    for f in board.GetFootprints():
        c = d.comps.get(f.GetReference())
        if c is None:
            continue
        for pin, net in c.pins.items():
            for pn in cpmodel.pads_for(c, pin):
                for p in f.Pads():
                    if p.GetNumber() == pn and net and p.GetNetname() != net:
                        rep.append("%s.%s: %r -> %s" % (f.GetReference(), pn, p.GetNetname(), net))
                        p.SetNet(nets[net])
        if c.value != f.GetValue():
            rep.append("%s value: %s -> %s" % (f.GetReference(), f.GetValue(), c.value))
            f.SetValue(c.value)

    # ---- 4. the RP2040 in the STC's place ----
    u = PK.new_fp(board, d, nets, "U201")
    PK.pose(u, CENTRE[0], CENTRE[1], plan["rot"], True)
    fine_pitch_rules(u)
    pads = {p.GetNumber(): p for p in u.Pads()}
    gnd = nets["GND"]
    for dx in (-0.8, 0.8):                      # the exposed pad is the chip's only ground: four vias to the top pour
        for dy in (-0.8, 0.8):
            add_via(board, gnd, (CENTRE[0] + dx, CENTRE[1] + dy))
    pxy = {n: xy(p.GetPosition()) for n, p in pads.items() if n}
    under_chip(board, nets, pxy)
    rep.append("U201 RP2040 at (%.2f, %.2f), bottom, turned %d; 4 ground vias in its pad, TESTEN tied to it; the core "
               "supply and the I/O supply pins facing the lanes joined under the chip (inner vias, top face)" % (CENTRE + (plan["rot"],)))

    # ---- 5. the new parts on free spots of the bottom face: the lanes where lines come in stay free ----
    free = PK.Free(board)
    free.take(u)
    cx, cy = CENTRE
    box = lambda b_: (cx + b_[0], cy + b_[1], cx + b_[2], cy + b_[3])      # noqa: E731
    west, cz = LANES[2], CRYSTAL_ZONE
    free.boxes += [box(b_) for b_ in LANES[:2] + LANES[3:]]
    free.boxes += [box((west[0], west[1], west[2], cz[1])), box((west[0], cz[3], west[2], west[3]))]

    def put(ref, target, rmax=16.0):
        fp = PK.new_fp(board, d, nets, ref)
        ok = PK.spiral_place(fp, free, *target, rmax=rmax)
        if not ok:                              # (off the board, where it shows: not over other parts)
            PK.pose(fp, 330.0, 150.0, 0, True)
        rep.append("%-5s %s" % (ref, ("at (%.2f, %.2f)" % xy(fp.GetPosition())) if ok else "NOT PLACED"))
        if ok and ref.startswith("U"):
            fine_pitch_rules(fp)
        return fp

    # the crystal's group first, in the middle of the west lane (its pins 20 / 21 face west)
    # Y201 turned so that XIN's pad (1) is at its corner nearest pin 20 and XTAL_O's (3) at the far corner, away from
    # the chip; R208 (XOUT's 1 k) beside it on pin 21's side, the two 22 pF capacitors at the pads they belong to
    x20 = ((pxy["20"][0] + pxy["21"][0]) / 2, (pxy["20"][1] + pxy["21"][1]) / 2)
    y = PK.new_fp(board, d, nets, "Y201")
    yx, yy_ = outward(x20, 3.6)
    yy_ += 2.6                                  # (south of pins 20 / 21: see CRYSTAL_ZONE)
    to_chip = (1 if CENTRE[0] > yx else -1, 0) if abs(CENTRE[0] - yx) > abs(CENTRE[1] - yy_) else (0, 1 if CENTRE[1] > yy_ else -1)
    best = None
    for rot in (0, 90, 180, 270):
        PK.pose(y, yx, yy_, rot, True)
        yp = {p.GetNumber(): xy(p.GetPosition()) for p in y.Pads()}
        score = (yp["1"][0] - yx) * to_chip[0] + (yp["1"][1] - yy_) * to_chip[1] - math.hypot(yp["1"][0] - pxy["20"][0], yp["1"][1] - pxy["20"][1])
        if best is None or score > best[0]:
            best = (score, rot)
    ok = PK.spiral_place(y, free, yx, yy_, rots=(best[1],), rmax=2.5)
    if not ok:
        PK.pose(y, yx, yy_, best[1], True)
        free.take(y)
    yx, yy_ = xy(y.GetPosition())
    yp = {p.GetNumber(): xy(p.GetPosition()) for p in y.Pads()}
    rep.append("Y201  at (%.2f, %.2f), turned %d (XIN's pad toward pin 20)%s" % (yx, yy_, best[1], "" if ok else " - OVERLAPS"))
    put("R208", (yx - 2.6, yy_ - 0.9), rmax=3.0)
    put("C213", (yx - 2.6, yy_ + 0.9), rmax=3.0)
    put("C212", (yx - 3.9, yy_), rmax=3.0)
    free.boxes.append(box(west))
    # the rest east of the chip (the USB / flash side)
    # The flash right at the end of the east corridor, turned so that its pins come in the chip's order: the chip's
    # QSPI pins run (north to south) SD3 SCLK SD0 | SD2 SD1 SS; with pin 1 at the flash's south-east corner its north
    # row reads (west to east) IO0 SCLK IO3 VCC and its south row GND IO2 IO1 CS - the first three reach the north row
    # round the flash's north side, the last three the south row round its south side, nothing crosses; VCC3V3 from
    # pins 48 / 49 (between USB and SD3) goes on to VCC at the north row's east end, USB further north.
    f = PK.new_fp(board, d, nets, "U204")
    fx, fy = cx + 8.6, cy + 0.4
    for rot in (0, 90, 180, 270):
        PK.pose(f, fx, fy, rot, True)
        fp_ = {p.GetNumber(): xy(p.GetPosition()) for p in f.Pads()}
        if fp_["1"][0] > fx and fp_["1"][1] > fy and fp_["5"][0] < fx and fp_["5"][1] < fy:
            break
    fine_pitch_rules(f)
    free.take(f)
    rep.append("U204  at (%.2f, %.2f), turned %d (pin 1 south-east)" % (fx, fy, rot))
    put("R206", (cx + 12.6, cy + 2.6))          # BOOTSEL's 1 k on the flash's chip select (pin 1)
    put("C211", (cx + 12.4, cy - 2.4))          # the flash's VCC (pin 8, north-east)
    put("C207", (cx + 12.4, cy - 4.0))
    # the USB series resistors and the core supply's capacitors north-east
    put("R204", (cx + 7.0, cy - 4.6))
    put("R203", (cx + 8.8, cy - 4.6))
    put("C201", (cx + 4.8, cy - 4.6))           # core supply (VREG_VOUT, pin 45)
    put("C202", (cx + 4.8, cy - 6.4))
    put("C208", (cx + 6.6, cy - 6.4))           # VREG_VIN (pin 44)
    for ref in ("C203", "C204", "C206"):
        put(ref, (cx + 10.6, cy - 6.4))
    ldo = put("U203", (cx + 14.5, cy - 5.0))
    put("C209", xy(ldo.GetPosition()))
    put("C205", xy(ldo.GetPosition()))
    put("SW201", (cx + 16.0, cy + 1.0))
    if any("NOT PLACED" in s for s in rep):
        rep.append("SOME PARTS NOT PLACED")
    pcbnew.SaveBoard(EDIT, board, True)
    PK.with_project(EDIT)
    print("\n".join("  " + s for s in rep))
    print("  -> " + EDIT)


# ------------------------------------------------------------------------------------------------ stage route
CHIP_BOX = (CENTRE[0] - 15.0, CENTRE[1] - 11.5, CENTRE[0] + 15.5, CENTRE[1] + 12.0)


def chip_nets(board):
    out = set()
    for f in board.GetFootprints():
        if f.GetReference() in ("U201", "U204", "Y201", "R208"):
            out |= {p.GetNetname() for p in f.Pads() if p.GetNetname() and p.GetNetname() != "GND"}
    return out | {"VCC5"}                       # (near the chip only the LDO and R156 need it: thin is enough)


def route(passes):
    """kbd_powerkey_board.route_passes on this script's files, with the small (0.5 / 0.3) vias for the chip's nets."""
    import route as R
    import kbd_board as K
    PK.ROUTED = ROUTED
    orig = K.make_router

    def mk(board):
        r, reg, code = orig(board)
        fan = chip_nets(board)
        for n, c in code.items():
            if n in fan:
                r.rc_of[c] = R.RCS["FAN"]
        # no new vias within 2.2 mm of the chip's pads (and under it): at 0.4 mm pitch a via at one pad's tip walls in
        # its two neighbours; every pin leaves on the bottom face first
        from gen_pcb import OX, OY
        G, m = R.G, 3.85 + 1.3
        i0, i1 = int((CENTRE[0] - m - OX - reg.x0) / G), int((CENTRE[0] + m - OX - reg.x0) / G)
        j0, j1 = int((CENTRE[1] - m - OY - reg.y0) / G), int((CENTRE[1] + m - OY - reg.y0) / G)
        i0, j0, i1, j1 = max(0, i0), max(0, j0), min(reg.nx - 1, i1), min(reg.ny - 1, j1)
        if i0 <= i1 and j0 <= j1:
            reg.novia[j0:j1 + 1, i0:i1 + 1] = True
        return r, reg, code
    K.make_router = mk
    try:
        PK.route_passes(passes)
    finally:
        K.make_router = orig


def stage_route():
    import kbd_board as K
    PK.with_project(EDIT)
    shutil.copyfile(EDIT, ROUTED)
    PK.with_project(ROUTED)
    route([("round the chip", CHIP_BOX, None, 2),
           ("the rest", K.ROUTE_BOX, None, 2)])


def stage_route_more():
    import kbd_board as K
    route([("round the chip, longer searches", CHIP_BOX, None, 8),
           ("the rest, longer searches", K.ROUTE_BOX, None, 8)])


def repair_round(k):
    """One rip-up round on build/kbd_rp_routed.kicad_pcb (a process of its own: pcbnew's wrappers break after a board
    is edited and reloaded): for one open net the router's copper of every other net within a circle round its pads
    and copper near the chip is taken out, the open net routed first, then the others.  The file is kept only if
    fewer nets are open afterwards (or as many, without that one).  Exit 0: nothing open, 1: still open."""
    import route as R
    import kbd_board as K
    PK.with_project(ROUTED)
    orig = K.make_router

    def mk(board):
        r, reg, code = orig(board)
        fan = chip_nets(board)
        for n, c in code.items():
            if n in fan:
                r.rc_of[c] = R.RCS["FAN"]
        from gen_pcb import OX, OY
        G, m = R.G, 3.85 + 1.3
        i0, i1 = int((CENTRE[0] - m - OX - reg.x0) / G), int((CENTRE[0] + m - OX - reg.x0) / G)
        j0, j1 = int((CENTRE[1] - m - OY - reg.y0) / G), int((CENTRE[1] + m - OY - reg.y0) / G)
        reg.novia[max(0, j0):j1 + 1, max(0, i0):i1 + 1] = True
        return r, reg, code
    board = pcbnew.LoadBoard(ROUTED)            # (K.ROUTE_BOX: the keyboard's whole routing window)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    r, reg, code = mk(board)
    before = sorted(r.name_of[n] for n in K.split_nets(r, reg))
    if not before:
        raise SystemExit(0)
    name = before[k % len(before)]
    rad = 2.0 + 1.5 * (k // len(before))
    del r, reg

    def key(t):
        a, b = t.GetStart(), t.GetEnd()
        return (t.GetLayer(), t.GetClass(), tuple(sorted(((a.x, a.y), (b.x, b.y)))))
    predrawn = {key(t) for t in pcbnew.LoadBoard(EDIT).GetTracks()}
    bx = K.ROUTE_BOX
    pts = [xy(p.GetPosition()) for f in board.GetFootprints() for p in f.Pads() if p.GetNetname() == name]
    pts += [q for t in board.GetTracks() if t.GetNetname() == name for q in item_points(t)]
    pts = [q for q in pts if bx[0] <= q[0] <= bx[2] and bx[1] <= q[1] <= bx[3]]
    rip = set()
    for t in board.GetTracks():
        n = t.GetNetname()
        if n in ("GND", name, "") or key(t) in predrawn:
            continue
        (ax, ay), (bx_, by) = (item_points(t) * 2)[:2] if t.GetClass() == "PCB_VIA" else item_points(t)
        for px_, py_ in pts:
            vx, vy = bx_ - ax, by - ay
            L2 = vx * vx + vy * vy
            u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px_ - ax) * vx + (py_ - ay) * vy) / L2))
            if math.hypot(ax + u * vx - px_, ay + u * vy - py_) < rad:
                rip.add(n)
                break
    kill = [t for t in board.GetTracks() if (t.GetNetname() in rip or t.GetNetname() == name) and key(t) not in predrawn
            and any(bx[0] <= q[0] <= bx[2] and bx[1] <= q[1] <= bx[3] for q in item_points(t))]
    for t in kill:
        board.Remove(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    r, reg, code = mk(board)
    r.items, r.failed = [], []
    tried, failed = [name] + sorted(rip), set()
    for n in tried:
        c = code.get(n)
        if c is not None and len(r.groups(reg, c)) >= 2:
            _, bad = r.route_net(reg, c)
            if bad:
                failed.add(n)
    after = sorted((set(before) - set(tried)) | failed)
    if len(after) < len(before) or (len(after) == len(before) and name not in after):
        r.flush(r.items)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(ROUTED, board, True)
        PK.with_project(ROUTED)
        print("repair %d: %s (circle %.1f mm) - %d nets taken out and re-routed; open now: %s"
              % (k + 1, name, rad, len(rip), " ".join(after) or "none"), flush=True)
        raise SystemExit(0 if not after else 1)
    print("repair %d: %s (circle %.1f mm) - no better (%d open: %s), not kept" % (k + 1, name, rad, len(after), " ".join(after)), flush=True)
    raise SystemExit(1)


def stage_repair():
    rounds = int(os.environ.get("CP_REPAIR", "12"))
    for k in range(rounds):
        rc = subprocess.run([sys.executable, os.path.abspath(__file__), "--stage", "repair1", str(k)]).returncode
        if rc == 0:
            print("  repair: nothing open any more", flush=True)
            return
        if rc != 1:
            print("  repair %d: the round failed (exit %d)" % (k + 1, rc), flush=True)


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
    if stage == "repair1":
        repair_round(int(sys.argv[sys.argv.index("--stage") + 2]))
        return
    {"plan": stage_plan, "edit": stage_edit, "route": stage_route, "route_more": stage_route_more,
     "repair": stage_repair, "promote": stage_promote}[stage]()


if __name__ == "__main__":
    main()
