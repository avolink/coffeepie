#!/usr/bin/env python
"""commander_cpu_ram: the RK3566 and its LPDDR4 on a board of their own, sized and layered for the memory bus.
Run with the Python that comes with KiCad, CP_ROOT = the project folder (tools/build.py --variant cpu_ram does it all):

    cpu_ram_board.py --stage netlist|place|route|finish

  netlist  src/netlist/90_soc_unused.net: every RK3566 ball the mainboard uses but this board does not, as NC, so the
           footprint keeps all 565 balls (sheets 11, 12, 13 of the mainboard come in unchanged through shared.txt)
  place    10-layer board, the processor and the memory, the passives that sit on memory signals, a via in every
           supply / ground ball (via in pad, filled and capped)              -> build/<prj>_placed.kicad_pcb
  route    the memory bus, the ZQ / RZQ resistors, the memory's 1.8 V supply and the escapes of the ground balls on
           the processor's outer ring: negotiated-congestion routing (PathFinder) on a 0.025 mm grid, every net
           allowed on the five signal layers, through vias only; search core in tools/cr_astar.c
                                                                             -> build/<prj>_routed.kicad_pcb
  finish   decoupling capacitors on the bottom face (via in pad to the planes), the planes, zone fill  -> <prj>.kicad_pcb

Stack-up (JLC 10-layer, 1.6 mm):  F.Cu signal | In1 GND | In2 signal | In3 GND | In4 signal | In5 VCC_DDR + VDD_CPU |
In6 VCC0V6_DDR + VDD_LOGIC | In7 signal (+ VDD_GPU_NPU under the processor) | In8 GND | B.Cu signal + capacitors.

Board coordinates are mm from the board's top-left corner (KiCad's page offset is added on output).
"""
import ctypes
import glob
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpmodel                                  # noqa: E402
import gen_pcb as GP                            # noqa: E402  (footprint loading, poses, page offset)
from gen_schematic import uid                   # noqa: E402

ROOT, PRJ = cpmodel.ROOT, cpmodel.PRJ
OX, OY = GP.OX, GP.OY
BUILD = os.path.join(ROOT, "build")
PLACED = os.path.join(BUILD, PRJ + "_placed.kicad_pcb")
ROUTED = os.path.join(BUILD, PRJ + "_routed.kicad_pcb")
FINAL = os.path.join(ROOT, PRJ + ".kicad_pcb")
REPORT = os.path.join(BUILD, "ddr_report.txt")
NL = chr(10)
PRO = os.path.join(ROOT, PRJ + ".kicad_pro")
_PRO_TEXT = open(PRO, encoding="utf-8").read() if os.path.exists(PRO) else None     # as tools/gen_project.py wrote it


def save(board, path):
    """pcbnew.SaveBoard also writes a .kicad_pro beside the board, from the board's own settings (KiCad's default rules
    and one net class): put the project's file there instead, so the zone filler and DRC see the real rules."""
    pcbnew.SaveBoard(path, board)
    if _PRO_TEXT is not None:
        with open(path[:-len(".kicad_pcb")] + ".kicad_pro", "w", encoding="utf-8", newline="\n") as f:
            f.write(_PRO_TEXT)


def env(name, default):
    return float(os.environ.get(name, default))


def q(v):
    """Round to the routing grid (every ball of both packages then sits on a grid point)."""
    return round(v / G) * G


# ---------------------------------------------------------------------------------------------------- geometry
G = 0.025                       # routing grid, mm: 0.65 / 0.4 / 0.8 pitches and the 0.325 mid-points all fall on it
GAP = env("CR_GAP", 5.0)        # copper-free room between the memory's long side and the processor's top edge
MEM_DX = env("CR_MEM_DX", -7.0)  # memory centre x relative to the processor centre
MARGIN = 5.0
SOC_W, SOC_H = 15.5, 14.4
MEM_W, MEM_H = 14.5, 10.0       # the memory turned 90 degrees: its channel A half on the left, channel B on the right
SOC_X = q(max(MARGIN + SOC_W / 2, MARGIN + MEM_W / 2 - MEM_DX))
SOC_Y = q(MARGIN + MEM_H + GAP + SOC_H / 2)
MEM_X, MEM_Y = q(SOC_X + MEM_DX), q(SOC_Y - SOC_H / 2 - GAP - MEM_H / 2)
# the eMMC (11.5 x 13 mm, turned 90 so its signal corner - columns 2-6 - faces down at the processor's eMMC balls,
# which sit on the right half of its top edge): beside the memory, level with it
EMMC_W, EMMC_H = 13.0, 11.5
EMMC_X, EMMC_Y = q(MEM_X + MEM_W / 2 + env("CR_EMMC_GAP", 2.0) + EMMC_W / 2), MEM_Y
BW = math.ceil((max(SOC_X + SOC_W / 2, MEM_X + MEM_W / 2, EMMC_X + EMMC_W / 2) + MARGIN) * 2) / 2
BH = math.ceil((SOC_Y + SOC_H / 2 + MARGIN) * 2) / 2
CORNER_R = 1.0

# ---------------------------------------------------------------------------------------------------- layers
LAYER_COUNT = 10
RL = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In4_Cu, pcbnew.In7_Cu, pcbnew.B_Cu]        # routing layers
RL_NAME = ["F.Cu", "In2.Cu", "In4.Cu", "In7.Cu", "B.Cu"]
LCOST = [1.15, 1.0, 1.0, 1.0, 1.1]
F_IDX, B_IDX = 0, 4


def soc(dx, dy):
    return SOC_X + dx, SOC_Y + dy


# plane nets -> (layer, polygon in design mm); polygons that share a layer must not touch
def plane_polys():
    x0, y0, x1, y1 = 0.3, 0.3, BW - 0.3, BH - 0.3
    full = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    # the memory bus area: the whole memory, the gap, and the processor's DDR corner (left of its column 10, above
    # its row H); the core rails take the rest of the processor, each reaching out past the package for its capacitors
    mb = MEM_Y + MEM_H / 2 + 0.5
    mr = max(SOC_X - 0.33, MEM_X + MEM_W / 2 + 0.5)
    ddr = [(x0, y0), (mr, y0), (mr, mb), (SOC_X - 0.33, mb), (SOC_X - 0.33, SOC_Y - 1.3), (x0, SOC_Y - 1.3)]
    # the eMMC area: its 3.3 V on In5, its 1.8 V IO (VCCIO_FLASH) on In6 with a strip down to the processor's
    # VCCIO_FLASH ball 1C13 (package (1.625, -4.225))
    eb = EMMC_Y + EMMC_H / 2 + 0.3
    el = max(mr + 0.6, EMMC_X - EMMC_W / 2 - 0.5)
    emmc = [(el, y0), (x1, y0), (x1, eb), (el, eb)]
    fb = SOC_Y - SOC_H / 2 - 0.6            # (on In6 the 1.8 V reaches down to the processor: the pull-ups sit there)
    flash = [(el, y0), (x1, y0), (x1, fb), (SOC_X + 2.6, fb), soc(2.6, -3.6), soc(0.6, -3.6), (SOC_X + 0.6, eb), (el, eb)]
    ct = max(mb, eb) + 0.6
    cr = min(x1, SOC_X + 5.5)
    # VDD_CPU: its corner of the processor, and out to the right edge above the GPU rail's reach for its capacitors
    cpu = [(SOC_X, ct), (x1, ct), (x1, SOC_Y - 4.5), (cr, SOC_Y - 4.5), (cr, SOC_Y - 1.3), (SOC_X, SOC_Y - 1.3)]
    logic = [soc(-2.7, -1.25), soc(0.0, -1.25), soc(0.0, SOC_H / 2), soc(3.0, SOC_H / 2), (SOC_X + 3.0, y1),
             (SOC_X - 6.0, y1), soc(-6.0, SOC_H / 2), soc(-2.7, SOC_H / 2)]
    gpu = [soc(-2.7, -2.0), soc(3.3, -2.0), soc(3.3, -4.0), (x1, SOC_Y - 4.0), (x1, SOC_Y + 4.0),
           soc(3.3, 4.0), soc(3.3, 2.0), soc(-2.7, 2.0)]
    return [("GND", pcbnew.In1_Cu, full, 0), ("GND", pcbnew.In3_Cu, full, 0), ("GND", pcbnew.In8_Cu, full, 0),
            ("VCC_DDR", pcbnew.In5_Cu, ddr, 0), ("VDD_CPU", pcbnew.In5_Cu, cpu, 0),
            ("VCC0V6_DDR", pcbnew.In6_Cu, ddr, 0), ("VDD_LOGIC", pcbnew.In6_Cu, logic, 0),
            ("VDD_GPU_NPU", pcbnew.In7_Cu, gpu, 0),
            ("VCC_3V3", pcbnew.In5_Cu, emmc, 0), ("VCCIO_FLASH", pcbnew.In6_Cu, flash, 0)]


PLANE_NETS = ("GND", "VCC_DDR", "VCC0V6_DDR", "VDD_CPU", "VDD_LOGIC", "VDD_GPU_NPU", "VCC_3V3", "VCCIO_FLASH")
CHIPS = ("U1", "U10", "U20")
# routing layers that carry a plane piece: the router keeps out of it there
RESERVED = [("VDD_GPU_NPU", 3)]
# where each rail's decoupling capacitors go looking for room (bottom face)
CAP_TARGET = {"VDD_CPU": soc(SOC_W / 2 + 2.0, -5.8), "VDD_LOGIC": soc(-1.5, SOC_H / 2 + 1.6),
              "VDD_GPU_NPU": soc(SOC_W / 2 + 1.8, 0.0)}

# ---------------------------------------------------------------------------------------------------- rules
W_TR, CL = 0.09, 0.09           # memory class: 0.09 mm track, 0.09 mm space (JLC multilayer minimum)
VIA_D, VIA_H = 0.25, 0.15       # via in pad (filled, capped); the same via everywhere
HCL, H2H, EDGE = 0.195, 0.25, 0.25
EPS = 0.002
R_TT = W_TR + CL + EPS                                                          # track centre <-> track centre
R_TV = max(VIA_D / 2 + CL + W_TR / 2, VIA_H / 2 + HCL + W_TR / 2) + EPS         # track centre <-> via centre
R_VV = max(VIA_D + CL, VIA_H + H2H, VIA_H / 2 + HCL + VIA_D / 2)               # via centre <-> via centre
OFF_T = CL + W_TR / 2 + EPS                                                     # track centre <-> pad edge
OFF_V = max(CL + VIA_D / 2, HCL + VIA_H / 2) + EPS                              # via centre <-> pad edge
FREE, MULTI = -1, -2


# ================================================================================================ stage netlist
def stage_netlist():
    out = os.path.join(cpmodel.NETDIR, "90_soc_unused.net")
    if os.path.exists(out):
        os.remove(out)
    mine = cpmodel.load()
    main = cpmodel.load(cpmodel.MAIN_NETDIR)
    used = set(mine.comps["U1"].pins)
    rest = sorted(set(main.comps["U1"].pins) - used, key=lambda b: (b.startswith("1"), len(b), b))
    lines = ["# GENERATED by tools/cpu_ram_board.py --stage netlist - do not edit.",
             "# Every RK3566 ball the mainboard uses and this board does not: NC here, so the footprint keeps all 565",
             "# balls (the board is about the processor <-> memory link; the other interfaces stay on the mainboard).",
             "SHEET soc_unused"]
    for k in range(0, len(rest), 24):
        lines.append("NC U1 " + " ".join(rest[k:k + 24]))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(NL.join(lines) + NL)
    print("  src/netlist/90_soc_unused.net: %d balls NC (%d used here, %d on the mainboard)" % (len(rest), len(used), len(main.comps["U1"].pins)))


# ================================================================================================ stage place
def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def pad_xy(pad):
    return ToMM(pad.GetPosition().x) - OX, ToMM(pad.GetPosition().y) - OY


def add_via(board, xy, net):
    v = pcbnew.PCB_VIA(board)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetPosition(P(*xy))
    v.SetDrill(FromMM(VIA_H))
    try:
        v.SetWidth(pcbnew.F_Cu, FromMM(VIA_D))
    except TypeError:
        v.SetWidth(FromMM(VIA_D))
    v.SetNet(net)
    board.Add(v)
    return v


def add_track(board, a, b, net, layer, w=W_TR):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(FromMM(w))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)


def outline(board):
    w, h, r = BW, BH, CORNER_R

    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        board.Add(s)

    def arc(c, a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        mx, my = (a[0] + b[0]) / 2 - c[0], (a[1] + b[1]) / 2 - c[1]
        k = r / math.hypot(mx, my)
        s.SetArcGeometry(P(*a), P(c[0] + mx * k, c[1] + my * k), P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        board.Add(s)

    seg((r, 0), (w - r, 0))
    arc((w - r, r), (w - r, 0), (w, r))
    seg((w, r), (w, h - r))
    arc((w - r, h - r), (w, h - r), (w - r, h))
    seg((w - r, h), (r, h))
    arc((r, h - r), (r, h), (0, h - r))
    seg((0, h - r), (0, r))
    arc((r, r), (0, r), (r, 0))


def note(board, txt, x, y, size=1.0, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)


def put(fp, x, y, rot, bottom=False):
    """Footprint anchor (pad-centre origin for all parts used here) at x, y."""
    GP.set_pose(fp, x, y, rot, bottom)


# memory-side passives on top, just outside the packages: (x, y, rotation, direction they move in until their
# courtyard is clear of the packages') - pad 1 faces the memory where it matters
def fixed_parts():
    top = MEM_Y - MEM_H / 2 - 0.9          # a row just above the memory's far long side (away from the processor)
    left = MEM_X - MEM_W / 2 - 1.3
    up, out = (0, -1), (-1, 0)
    return {
        "U1": (SOC_X, SOC_Y, 0, None), "U10": (MEM_X, MEM_Y, 90, None), "U20": (EMMC_X, EMMC_Y, 90, None),
        # ZQ resistors beside the memory's ZQ balls (A5, A8: the left short side once the memory is turned)
        "R121": (left, MEM_Y + 1.2, 0, out), "R120": (left, MEM_Y - 1.2, 0, out),
        # the memory's 1.8 V (VDD1): series 0R and its capacitors along the far side
        "R123": (MEM_X - 0.6, top, 270, up), "C204": (MEM_X - 4.4, top, 90, up), "C205": (MEM_X - 2.4, top, 90, up),
        "C206": (MEM_X + 1.2, top, 90, up), "C207": (MEM_X + 4.6, top, 90, up),
        "C159": (MEM_X + 2.9, top, 90, up),     # (DNP, on the memory's reset)
        # the processor's DDR calibration resistor, left of its channel A balls
        "R1": (SOC_X - SOC_W / 2 - 1.6, SOC_Y + 1.8, 90, out),
    }


def clear_of(board, fixed):
    """Move each hand-placed passive along its direction until its courtyard is clear of the packages' and of the
    passives already done (0.05 mm steps, then rounded onto the routing grid)."""
    chips = [GP.court(board.FindFootprintByReference(r)) for r in CHIPS]
    done = []
    for ref, (x, y, rot, d) in fixed.items():
        if d is None:
            continue
        fp = board.FindFootprintByReference(ref)
        for k in range(200):
            nx, ny = q(x + d[0] * 0.05 * k), q(y + d[1] * 0.05 * k)
            put(fp, nx, ny, rot)
            cb = GP.court(fp)
            if not any(not (cb[2] <= b[0] or b[2] <= cb[0] or cb[3] <= b[1] or b[3] <= cb[1]) for b in chips + done):
                break
        done.append(GP.court(fp))


def pack_top(board, d, fixed):
    """The other parts that sit on a routed signal (the eMMC's series resistor, pull-ups, VDDI capacitor, test point):
    on the top face, as near the chip balls of that signal as their courtyard is free (spiral search)."""
    count = {}
    for c in d.comps.values():
        for net in c.pins.values():
            if net:
                count[net] = count.get(net, 0) + 1
    routed = {n for n, k in count.items() if k >= 2 and n not in PLANE_NETS}
    boxes = [GP.court(board.FindFootprintByReference(r)) for r in fixed]
    balls = {}
    for ref in CHIPS:
        for p in board.FindFootprintByReference(ref).Pads():
            balls.setdefault(p.GetNetname(), []).append((ref, pad_xy(p)))
    n = 0
    for c in sorted(d.comps.values(), key=lambda c_: c_.ref):
        if c.ref in fixed or c.ref in CHIPS or not any(net in routed for net in c.pins.values()):
            continue
        pts = [xy for net in c.pins.values() if net in routed for (ref, xy) in balls.get(net, [])]
        near = [xy for net in c.pins.values() if net in routed for (ref, xy) in balls.get(net, []) if ref == "U20"]
        # a series resistor (one side only on the processor - EMMC_CLK_SOC) sits at the driver
        src = [xy for net in c.pins.values() if net in routed and balls.get(net)
               and all(ref == "U1" for ref, _ in balls[net]) for (ref, xy) in balls[net]]
        pts = src or near or pts or [(BW / 2, BH / 2)]
        tx, ty = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        fp = board.FindFootprintByReference(c.ref)
        found = None
        for rr in np.arange(0.0, 12.0, 0.1):
            for k in range(max(1, int(2 * math.pi * rr / 0.1))):
                a = 2 * math.pi * k / max(1, int(2 * math.pi * rr / 0.1))
                x, y = q(tx + rr * math.cos(a)), q(ty + rr * math.sin(a))
                for rot in (0, 90):
                    put(fp, x, y, rot)
                    cb = GP.court(fp)
                    if cb[0] < 0.6 or cb[1] < 0.6 or cb[2] > BW - 0.6 or cb[3] > BH - 0.6:
                        continue
                    if any(not (cb[2] + 0.1 <= b[0] or b[2] + 0.1 <= cb[0] or cb[3] + 0.1 <= b[1] or b[3] + 0.1 <= cb[1]) for b in boxes):
                        continue
                    found = cb
                    break
                if found:
                    break
            if found:
                break
        if found:
            boxes.append(found)
            n += 1
        else:
            put(fp, -20.0, 2.0 + 1.5 * n, 0)        # (no room: left for the finish stage, which then reports it)
    return n


def stage_place():
    d = cpmodel.load()
    if d.errors:
        raise SystemExit(NL.join(d.errors))
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(LAYER_COUNT)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = FromMM(W_TR)
    ds.m_MinClearance = FromMM(CL)
    ds.m_ViasMinSize = FromMM(VIA_D)
    ds.m_MinThroughDrill = FromMM(VIA_H)
    ds.m_CopperEdgeClearance = FromMM(EDGE)
    ds.SetBoardThickness(FromMM(1.6))
    outline(board)
    nets = {}
    for name in sorted(d.nets()):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    fixed = fixed_parts()
    park = 0
    for c in sorted(d.comps.values(), key=lambda c_: c_.ref):
        fp = GP.load_fp(c.fp)
        fp.SetReference(c.ref)
        fp.SetValue(c.value)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
        fp.SetSheetname("/" + c.sheet + "/")
        fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
        if c.desc and hasattr(fp, "SetLibDescription"):
            fp.SetLibDescription(c.desc)
        names = {p.GetNumber() for p in fp.Pads()}
        for pin, net in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                if pad not in names:
                    raise SystemExit(f"{c.ref} ({c.fp}): pin {pin} -> pad {pad} not on the footprint")
                if net is not None:
                    for p in fp.Pads():
                        if p.GetNumber() == pad:
                            p.SetNet(nets[net])
        board.Add(fp)
        if c.ref in fixed:
            put(fp, *fixed[c.ref][:3])
        else:                                   # decoupling: placed by the finish stage, parked off the board until then
            put(fp, -10.0 - 3 * (park // 30), 2.0 + 1.5 * (park % 30), 0)
            park += 1
    clear_of(board, fixed)
    npack = pack_top(board, d, fixed)
    park -= npack
    # a via in every supply / ground ball (except the ground balls of the processor's outer ring: those may leave on
    # the top face through the ring's gaps, the router decides)
    nvia = 0
    for ref in CHIPS:
        fp = board.FindFootprintByReference(ref)
        for p in fp.Pads():
            n = p.GetNetname()
            if n not in PLANE_NETS:
                continue
            if ref == "U1" and not p.GetNumber().startswith("1") and n == "GND":
                x, y = pad_xy(p)
                if x < SOC_X + 6.5 and y < SOC_Y + 1.0:       # the ring's memory and eMMC stretches
                    continue
            add_via(board, pad_xy(p), p.GetNet())
            nvia += 1
    note(board, "Commander CPU + RAM  " + cpmodel.REV, 1.5, BH - 2.2, 0.8)
    os.makedirs(BUILD, exist_ok=True)
    save(board, PLACED)
    print("  board %.1f x %.1f mm, %d copper layers; processor at (%.3f, %.3f), memory at (%.3f, %.3f) turned 90; "
          "%d supply / ground vias in the balls; %d parts parked for the finish stage" % (BW, BH, LAYER_COUNT, SOC_X, SOC_Y, MEM_X, MEM_Y, nvia, park))


# ================================================================================================ search core
_CORE = None


def core():
    global _CORE
    if _CORE is not None:
        return _CORE
    src = os.path.join(HERE, "cr_astar.c")
    tmp = os.path.join(tempfile.gettempdir(), "commander_cpu_ram_core")
    os.makedirs(tmp, exist_ok=True)
    dll = os.path.join(tmp, "cr_astar.dll" if os.name == "nt" else "cr_astar.so")
    csrc = os.path.join(tmp, "cr_astar.c")
    text = open(src, encoding="utf-8").read()
    if not os.path.exists(dll) or not os.path.exists(csrc) or open(csrc, encoding="utf-8").read() != text:
        with open(csrc, "w", encoding="utf-8") as f:
            f.write(text)
        gcc = os.environ.get("CP_GCC") or shutil.which("gcc") or (sorted(glob.glob("C:/Qt/Tools/mingw*/bin/gcc.exe")) or [None])[-1]
        if not gcc:
            raise SystemExit("cpu_ram_board.py needs a C compiler for its search core (set CP_GCC to gcc)")
        e = dict(os.environ)
        e["PATH"] = os.path.dirname(gcc) + os.pathsep + e.get("PATH", "")
        subprocess.run([gcc, "-O2", "-shared", "-static-libgcc", "-o", dll, csrc], check=True, env=e, cwd=tmp)
    lib = ctypes.CDLL(dll)
    P_ = ctypes.c_void_p
    lib.stamp.argtypes = [P_, ctypes.c_int, ctypes.c_int, P_, P_, P_, ctypes.c_int, ctypes.c_int, P_, ctypes.c_int32]
    lib.stamp.restype = None
    lib.astar.argtypes = ([ctypes.c_int] * 3 + [P_] * 8 + [ctypes.c_int, ctypes.c_float, ctypes.c_float] + [ctypes.c_int] * 4
                          + [P_, ctypes.c_int, P_, ctypes.c_int] + [ctypes.c_int] * 4 + [ctypes.c_float, ctypes.c_int64, P_, ctypes.c_int])
    lib.astar.restype = ctypes.c_int
    _CORE = lib
    return lib


def ptr(a):
    return a.ctypes.data_as(ctypes.c_void_p)


# ================================================================================================ the grid
class Grid:
    def __init__(self):
        self.W = int(round(BW / G)) + 1
        self.H = int(round(BH / G)) + 1
        self.N = self.W * self.H
        L = len(RL)
        self.L = L
        self.tho = np.full((L, self.H, self.W), FREE, np.int16)
        self.vho = np.full((self.H, self.W), FREE, np.int16)
        self.occt = np.zeros((L, self.H, self.W), np.uint16)
        self.occv = np.zeros((self.H, self.W), np.uint16)
        self.hist = np.zeros((L, self.H, self.W), np.float32)
        self.histv = np.zeros((self.H, self.W), np.float32)
        self.goal = np.zeros(L * self.N, np.uint8)
        self.mark = np.zeros(self.N, np.int32)
        self.epoch = 0
        self.lcost = np.array(LCOST, np.float32)
        self.netid = {}
        # the board edge
        kt, kv = int(math.ceil((EDGE + W_TR / 2) / G)), int(math.ceil((EDGE + VIA_D / 2) / G))
        for a, k in ((self.tho, kt), (self.vho, kv)):
            a[..., :k, :] = MULTI
            a[..., -k:, :] = MULTI
            a[..., :, :k] = MULTI
            a[..., :, -k:] = MULTI

    def nid(self, name):
        if name not in self.netid:
            self.netid[name] = len(self.netid)
        return self.netid[name]

    def cell(self, x, y):
        return int(round(x / G)), int(round(y / G))

    # ---- hard obstacles (owner merge) ----
    @staticmethod
    def _merge(sub, m, net):
        conflict = m & (sub != FREE) & (sub != net)
        free = m & (sub == FREE)
        sub[free] = net
        sub[conflict] = MULTI

    def _box(self, x0, y0, x1, y1):
        i0, j0 = max(0, int(math.floor(x0 / G)) - 1), max(0, int(math.floor(y0 / G)) - 1)
        i1, j1 = min(self.W, int(math.ceil(x1 / G)) + 2), min(self.H, int(math.ceil(y1 / G)) + 2)
        return i0, j0, i1, j1

    def shape_mask(self, shape, off):
        """Cells within off (mm) of a pad shape: ('circle', cx, cy, r) or ('rect', cx, cy, hw, hh)."""
        kind, cx, cy, a, b = shape if len(shape) == 5 else shape + (0,)
        ext = (a if kind == "circle" else max(a, b)) + off
        i0, j0, i1, j1 = self._box(cx - ext, cy - ext, cx + ext, cy + ext)
        xs = np.arange(i0, i1) * G
        ys = np.arange(j0, j1) * G
        if kind == "circle":
            d2 = (xs[None, :] - cx) ** 2 + (ys[:, None] - cy) ** 2
            m = d2 < (a + off) ** 2 - 1e-9
        else:
            dx = np.maximum(np.abs(xs[None, :] - cx) - a, 0)
            dy = np.maximum(np.abs(ys[:, None] - cy) - b, 0)
            m = dx * dx + dy * dy < off * off - 1e-9
        return i0, j0, i1, j1, m

    def hard_shape(self, layers, shape, net, off_t=OFF_T, off_v=OFF_V):
        nid = self.nid(net) if net else MULTI
        if layers:
            i0, j0, i1, j1, m = self.shape_mask(shape, off_t)
            for l in layers:
                self._merge(self.tho[l, j0:j1, i0:i1], m, nid)
        i0, j0, i1, j1, m = self.shape_mask(shape, off_v)
        self._merge(self.vho[j0:j1, i0:i1], m, nid)

    def hard_via(self, x, y, net):
        nid = self.nid(net)
        i0, j0, i1, j1, m = self.shape_mask(("circle", x, y, 0.0), R_TV)
        for l in range(self.L):
            self._merge(self.tho[l, j0:j1, i0:i1], m, nid)
        i0, j0, i1, j1, m = self.shape_mask(("circle", x, y, 0.0), R_VV - 1e-6)
        self._merge(self.vho[j0:j1, i0:i1], m, MULTI)        # hole to hole holds between vias of one net too

    def hard_segment(self, l, a, b, net, w=W_TR):
        nid = self.nid(net)
        for arr, r in ((self.tho[l], w / 2 + CL + W_TR / 2 + EPS), (self.vho, w / 2 + OFF_V)):
            i0, j0, i1, j1 = self._box(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)
            xs = np.arange(i0, i1)[None, :] * G
            ys = np.arange(j0, j1)[:, None] * G
            vx, vy = b[0] - a[0], b[1] - a[1]
            ll = vx * vx + vy * vy
            t = np.clip(((xs - a[0]) * vx + (ys - a[1]) * vy) / ll, 0, 1) if ll > 0 else 0.0
            d2 = (xs - a[0] - t * vx) ** 2 + (ys - a[1] - t * vy) ** 2
            self._merge(arr[j0:j1, i0:i1], d2 < r * r - 1e-9, nid)

    def reserve(self, l, poly, grow=0.2):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        i0, j0, i1, j1 = self._box(min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow)
        X = np.arange(i0, i1)[None, :] * G
        Y = np.arange(j0, j1)[:, None] * G
        inside = np.zeros((j1 - j0, i1 - i0), bool)
        n = len(poly)
        for k in range(n):                      # even-odd ray casting, with the polygon grown by its bounding margin
            (xa, ya), (xb, yb) = poly[k], poly[(k + 1) % n]
            cond = (ya > Y) != (yb > Y)
            xint = xa + (Y - ya) * (xb - xa) / ((yb - ya) if yb != ya else 1e-12)
            inside ^= cond & (X < xint)
        # grow by 'grow': cheap square dilation
        k = int(math.ceil(grow / G))
        grown = inside.copy()
        for dj in range(-k, k + 1):
            for di in range(-k, k + 1):
                grown |= np.roll(np.roll(inside, dj, 0), di, 1)
        self.tho[l, j0:j1, i0:i1][grown] = MULTI

    # ---- soft zones of a routed job ----
    def stamp_job(self, job, delta):
        if not job.pts and not job.vias:
            return
        lib = core()
        r2tt, r2tv, r2vv = (R_TT / G) ** 2, (R_TV / G) ** 2, (R_VV / G) ** 2
        vi = np.array([v[0] for v in job.vias], np.int32)
        vj = np.array([v[1] for v in job.vias], np.int32)
        allv_i, allv_j, allv_r = [vi], [vj], [np.full(len(vi), r2vv, np.float32)]
        for l in range(self.L):
            p = job.pts.get(l)
            pi = p[0] if p is not None else np.zeros(0, np.int32)
            pj = p[1] if p is not None else np.zeros(0, np.int32)
            if len(pi) == 0 and len(vi) == 0:
                continue
            ci = np.concatenate([pi, vi]).astype(np.int32)
            cj = np.concatenate([pj, vj]).astype(np.int32)
            cr = np.concatenate([np.full(len(pi), r2tt, np.float32), np.full(len(vi), r2tv, np.float32)])
            self.epoch += 1
            lib.stamp(ptr(self.occt[l]), self.W, self.H, ptr(ci), ptr(cj), ptr(cr), len(ci), delta, ptr(self.mark), self.epoch)
            if len(pi):
                allv_i.append(pi)
                allv_j.append(pj)
                allv_r.append(np.full(len(pi), r2tv, np.float32))
        ci = np.concatenate(allv_i).astype(np.int32)
        cj = np.concatenate(allv_j).astype(np.int32)
        cr = np.concatenate(allv_r).astype(np.float32)
        self.epoch += 1
        lib.stamp(ptr(self.occv), self.W, self.H, ptr(ci), ptr(cj), ptr(cr), len(ci), delta, ptr(self.mark), self.epoch)

    def search(self, net, starts, goal_states, goalvia, box, pres, viacost, lallow=None, maxexp=4000000):
        lib = core()
        i0, j0, i1, j1 = box
        st = np.array(sorted(set(starts)), np.int64)
        if goal_states:
            gs = np.array(goal_states, np.int64)
            self.goal[gs] = 1
            gc = gs % self.N
            gi, gj = gc % self.W, gc // self.W
            gb = (int(gi.min()), int(gj.min()), int(gi.max()), int(gj.max()))
        else:
            gs, gb = None, (0, 0, 0, 0)
        la = np.array(lallow if lallow is not None else [1] * self.L, np.uint8)
        out = np.zeros(200000, np.int64)
        n = lib.astar(self.W, self.H, self.L, ptr(self.tho), ptr(self.vho), ptr(self.occt), ptr(self.occv), ptr(self.hist),
                      ptr(self.histv), ptr(self.lcost), ptr(la), self.nid(net), pres, viacost, i0, j0, i1, j1,
                      ptr(st), len(st), ptr(self.goal), 1 if goalvia else 0, gb[0], gb[1], gb[2], gb[3], 1.25, maxexp, ptr(out), len(out))
        if gs is not None:
            self.goal[gs] = 0
        return out[:n] if n > 0 else n


# ================================================================================================ jobs
class Job:
    """One thing to route: a net with its terminals (tree), or one supply / ground pad that needs a via (stub)."""

    def __init__(self, k, net, kind, terms):
        self.k, self.net, self.kind, self.terms = k, net, kind, terms
        self.paths = []         # lists of global states
        self.vias = []          # (i, j)
        self.pts = {}           # layer -> (i array, j array) of the cells the tracks run through
        self.ok = False
        self.fails = 0

    def clear(self):
        self.paths, self.vias, self.pts, self.ok = [], [], {}, False

    def set_geometry(self, grid):
        per = {}
        vias = []
        for path in self.paths:
            ls = path // grid.N
            cs = path % grid.N
            for l in np.unique(ls):
                sel = cs[ls == l]
                per.setdefault(int(l), []).append(sel)
            ch = np.nonzero(ls[1:] != ls[:-1])[0]
            for c_ in cs[ch]:
                vias.append((int(c_ % grid.W), int(c_ // grid.W)))
        for v in getattr(self, "stub_via", []):
            vias.append(v)
        self.vias = sorted(set(vias))
        self.pts = {}
        for l, parts in per.items():
            c_ = np.unique(np.concatenate(parts))
            self.pts[l] = ((c_ % grid.W).astype(np.int32), (c_ // grid.W).astype(np.int32))


def pad_shape(p):
    x, y = pad_xy(p)
    sx, sy = ToMM(p.GetSize().x) / 2, ToMM(p.GetSize().y) / 2
    if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
        return ("circle", x, y, sx)
    ang = int(round(p.GetOrientationDegrees())) % 180
    if ang == 90:
        sx, sy = sy, sx
    return ("rect", x, y, sx, sy)


def pad_layers(p):
    out = []
    if p.IsOnLayer(pcbnew.F_Cu):
        out.append(F_IDX)
    if p.IsOnLayer(pcbnew.B_Cu):
        out.append(B_IDX)
    return out


def on_board(x, y):
    return 0 < x < BW and 0 < y < BH


def build_grid(board, routed_as_hard=True):
    """Hard obstacles from everything on the board: pads, vias, tracks (all nets), reserved plane pieces."""
    grid = Grid()
    for fp in board.GetFootprints():
        for p in fp.Pads():
            x, y = pad_xy(p)
            if not on_board(x, y):
                continue
            grid.hard_shape(pad_layers(p), pad_shape(p), p.GetNetname() or None)
    if routed_as_hard:
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                x, y = ToMM(t.GetPosition().x) - OX, ToMM(t.GetPosition().y) - OY
                grid.hard_via(x, y, t.GetNetname())
            elif t.GetLayer() in RL:
                a = (ToMM(t.GetStart().x) - OX, ToMM(t.GetStart().y) - OY)
                b = (ToMM(t.GetEnd().x) - OX, ToMM(t.GetEnd().y) - OY)
                grid.hard_segment(RL.index(t.GetLayer()), a, b, t.GetNetname(), ToMM(t.GetWidth()))
    polys = {(n, l): poly for n, l, poly, _ in plane_polys()}
    for net, l in RESERVED:
        for (n, lay), poly in polys.items():
            if n == net and lay == RL[l]:
                grid.reserve(l, poly)
    return grid


def plane_masks(grid):
    """net -> cells where a via of that supply reaches its plane: inside its polygons, 0.3 mm in from their edges."""
    X = np.arange(grid.W)[None, :] * G
    Y = np.arange(grid.H)[:, None] * G
    out = {}
    for net, _, poly, _ in plane_polys():
        if net == "GND":
            continue
        inside_ = np.zeros((grid.H, grid.W), bool)
        n = len(poly)
        for k in range(n):
            (xa, ya), (xb, yb) = poly[k], poly[(k + 1) % n]
            if ya == yb:
                continue
            cond = (ya > Y) != (yb > Y)
            xint = xa + (Y - ya) * (xb - xa) / (yb - ya)
            inside_ ^= cond & (X < xint)
        out[net] = out.get(net, np.zeros_like(inside_)) | inside_
    k = int(round(0.3 / G))
    for net, m in out.items():
        e = m.copy()
        e[k:, :] &= m[:-k, :]
        e[:-k, :] &= m[k:, :]
        e[:, k:] &= m[:, :-k]
        e[:, :-k] &= m[:, k:]
        out[net] = e
    return out


def make_jobs(board, grid):
    vias_at = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias_at[grid.cell(ToMM(t.GetPosition().x) - OX, ToMM(t.GetPosition().y) - OY)] = t.GetNetname()
    bynet = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            x, y = pad_xy(p)
            if n and on_board(x, y):
                bynet.setdefault(n, []).append(p)
    jobs = []
    for n in sorted(bynet):
        pads = bynet[n]
        terms = []
        for p in pads:
            x, y = pad_xy(p)
            i, j = grid.cell(x, y)
            l = pad_layers(p)[0]
            terms.append((l, i, j, p.GetParentFootprint().GetReference() + "." + p.GetNumber()))
        if n in PLANE_NETS:
            # one job per net for all its pads that still need a via: pads of one net never stand in each other's way
            need = [t for t in terms if vias_at.get((t[1], t[2])) != n]
            if need:
                jobs.append(Job(len(jobs), n, "stub", need))
                # a pad may also reach a pad of its net that already has its via (a short track on the top face)
                jobs[-1].anchors = [t[:3] for t in terms if vias_at.get((t[1], t[2])) == n]
        elif len(terms) >= 2:
            jobs.append(Job(len(jobs), n, "tree", terms))
    # strobe and clock pairs: each half is drawn towards the other's route (see attract())
    byname = {j.net: j for j in jobs}
    for j in jobs:
        m = re.match(r"(LPDDR4_(?:DQS\d|CLK))([PN])(_[AB])$", j.net)
        if m:
            j.partner = byname.get(m.group(1) + ("N" if m.group(2) == "P" else "P") + m.group(3))
    return jobs


ATTRACT = 0.55          # cost taken off a step in the band beside the partner's route (a step costs 1 + history)
PAIR_BAND = (R_TT, 0.25)    # the band: from the closest allowed centre distance to 0.25 mm (DDR pair gap 0.10 -> 0.19)


def attract(grid, other):
    """Make the band beside a routed job's tracks cheaper, layer by layer (the partner of a pair follows it there)."""
    lib = core()
    out = []
    scratch = np.zeros((grid.H, grid.W), np.uint16)
    for l, (pi, pj) in other.pts.items():
        scratch[:] = 0
        n = len(pi)
        pi_, pj_ = np.ascontiguousarray(pi, np.int32), np.ascontiguousarray(pj, np.int32)
        for r in (PAIR_BAND[1], PAIR_BAND[0]):
            grid.epoch += 1
            r2 = np.full(n, (r / G) ** 2, np.float32)
            lib.stamp(ptr(scratch), grid.W, grid.H, ptr(pi_), ptr(pj_), ptr(r2), n, 1, ptr(grid.mark), grid.epoch)
        idx = np.flatnonzero(scratch == 1)
        grid.hist[l].reshape(-1)[idx] -= ATTRACT
        out.append((l, idx))
    return out


def release(grid, band):
    for l, idx in band:
        grid.hist[l].reshape(-1)[idx] += ATTRACT


# ================================================================================================ routing
VIA_COST = 24.0         # in grid steps (0.6 mm of track)


def route_job(grid, job, pres, margin=4.0):
    grid.stamp_job(job, -1) if job.ok else None
    job.clear()
    job.stub_via = []
    N = grid.N
    job.open = []
    if job.kind == "stub":
        # each pad to a via of its own (via in the pad, or a short track to one); the job's own vias keep the hole
        # spacing among themselves (blocked in vho while the job is routed, put back after)
        saved = []
        kv = int(math.ceil(R_VV / G))
        anchors = list(getattr(job, "anchors", []))
        try:
            vmask = getattr(grid, "vmask", {}).get(job.net)
            for (l, i, j, name) in job.terms:
                m = int(2.5 / G)
                box = (max(0, i - m), max(0, j - m), min(grid.W, i + m), min(grid.H, j + m))
                goals = [a[0] * N + a[2] * grid.W + a[1] for a in anchors
                         if box[0] <= a[1] < box[2] and box[1] <= a[2] < box[3] and (a[1], a[2]) != (i, j)]
                if vmask is not None:           # a supply's via must land on its own plane
                    sl = (slice(box[1], box[3]), slice(box[0], box[2]))
                    keep_v = grid.vho[sl].copy()
                    grid.vho[sl][~vmask[sl]] = MULTI
                try:
                    res = grid.search(job.net, [l * N + j * grid.W + i], goals or None, True, box, pres, VIA_COST)
                finally:
                    if vmask is not None:
                        grid.vho[sl] = keep_v
                if isinstance(res, int):
                    job.open.append(name)
                    continue
                job.paths.append(res)
                anchors.append((l, i, j))
                if int(res[-1]) in goals:          # ended on a pad that has its via: no via of its own
                    continue
                c_ = int(res[-1] % N)
                vi, vj = c_ % grid.W, c_ // grid.W
                job.stub_via.append((vi, vj))
                j0_, j1_, i0_, i1_ = max(0, vj - kv), min(grid.H, vj + kv + 1), max(0, vi - kv), min(grid.W, vi + kv + 1)
                saved.append((j0_, j1_, i0_, i1_, grid.vho[j0_:j1_, i0_:i1_].copy()))
                yy, xx = np.mgrid[j0_:j1_, i0_:i1_]
                grid.vho[j0_:j1_, i0_:i1_][(xx - vi) ** 2 + (yy - vj) ** 2 < (R_VV / G) ** 2] = MULTI
        finally:
            for (j0_, j1_, i0_, i1_, arr) in reversed(saved):
                grid.vho[j0_:j1_, i0_:i1_] = arr
        if job.open:
            job.fails += 1
        if not job.paths:
            return False
    else:
        terms = list(job.terms)
        # start from the terminal farthest from the rest's centre (a processor ball), then the nearest one each time
        tree = [terms.pop(0)]
        tree_states = [tree[0][0] * N + tree[0][2] * grid.W + tree[0][1]]
        tree_cells = [(tree[0][1], tree[0][2])]
        while terms:
            terms.sort(key=lambda t: min(abs(t[1] - a) + abs(t[2] - b) for a, b in tree_cells))
            t = terms.pop(0)
            goal = [t[0] * N + t[2] * grid.W + t[1]]
            ii = [a for a, _ in tree_cells] + [t[1]]
            jj = [b for _, b in tree_cells] + [t[2]]
            ok = False
            partner = getattr(job, "partner", None)
            band = attract(grid, partner) if partner is not None and partner.ok else None
            try:
                for mg in (margin, 12.0):
                    m = int(mg / G)
                    box = (max(0, min(ii) - m), max(0, min(jj) - m), min(grid.W, max(ii) + m + 1), min(grid.H, max(jj) + m + 1))
                    res = grid.search(job.net, tree_states, goal, False, box, pres, VIA_COST)
                    if not isinstance(res, int):
                        ok = True
                        break
            finally:
                if band:
                    release(grid, band)
            if not ok:
                job.fails += 1
                job.paths = []
                return False
            job.paths.append(res)
            cs = res % N
            ls = res // N
            # the new branch joins the tree; at a via the tree is reachable on every layer
            for s in res:
                tree_states.append(int(s))
            ch = np.nonzero(ls[1:] != ls[:-1])[0]
            for c_ in cs[ch]:
                for l2 in range(grid.L):
                    tree_states.append(l2 * N + int(c_))
            tree_cells.extend((int(c_ % grid.W), int(c_ // grid.W)) for c_ in cs[::8])
            tree_cells.append((t[1], t[2]))
    job.set_geometry(grid)
    job.ok = True
    grid.stamp_job(job, +1)
    return True


def conflicts(grid, job):
    """Cells of the job's tracks / vias that another job's zone covers (its own zone covers them once)."""
    bad_t, bad_v = [], []
    for l, (pi, pj) in job.pts.items():
        sel = grid.occt[l, pj, pi] >= 2
        if sel.any():
            bad_t.append((l, pi[sel], pj[sel]))
    for (i, j) in job.vias:
        if grid.occv[j, i] >= 2:
            bad_v.append((i, j))
    # a track of this job inside another job's via zone shows up in occv as well
    n = sum(len(b[1]) for b in bad_t) + len(bad_v)
    return n, bad_t, bad_v


def group_of(n):
    if n.startswith("EMMC_"):
        return "E", "emmc"
    if not n.startswith("LPDDR4_"):
        return "-", n
    s = n[len("LPDDR4_"):]
    ch = s[-1] if s[-2:] in ("_A", "_B") else "-"
    base = s[:-2] if ch != "-" else s
    m = re.match(r"DQ(\d+)$", base)
    if m:
        return ch, "byte%d" % (int(m.group(1)) // 8)
    if re.match(r"(DQS\d[NP]|DM\d)$", base):
        return ch, "byte" + re.search(r"\d", base).group(0)
    if base.startswith(("A", "CS", "CKE", "CLK", "ODT")):
        return ch, "cmd"
    return ch, base


def stage_route():
    t0 = time.time()
    board = pcbnew.LoadBoard(PLACED)
    grid = build_grid(board)
    grid.vmask = plane_masks(grid)
    jobs = make_jobs(board, grid)
    trees = [j for j in jobs if j.kind == "tree"]
    stubs = [j for j in jobs if j.kind == "stub"]
    print("  %d nets to route (%d memory bus), %d ground / supply pads that need their via; grid %d x %d x %d layers"
          % (len(trees), sum(1 for j in trees if j.net.startswith("LPDDR4_")), len(stubs), grid.W, grid.H, grid.L), flush=True)
    iters = int(os.environ.get("CR_ITERS", "60"))
    pres, pf, hinc = 0.6, 1.35, 0.4
    best = None
    log = []
    order = sorted(jobs, key=lambda j: (j.kind != "stub", -len(j.terms)))
    for it in range(iters):
        if it < 3 or it % 6 == 0:
            todo = order
        else:
            todo = [j for j in order if not j.ok or conflicts(grid, j)[0]]
        for j in todo:
            route_job(grid, j, pres)
        total, nbad, unrouted = 0, 0, 0
        for j in jobs:
            if not j.ok:
                unrouted += 1
                continue
            n, bt, bv = conflicts(grid, j)
            if n:
                nbad += 1
                total += n
                for l, pi, pj in bt:
                    grid.hist[l, pj, pi] += hinc
                for (i, jj) in bv:
                    grid.histv[jj, i] += hinc
        log.append("iteration %2d: pressure %7.2f, rerouted %3d, jobs in conflict %3d (%5d cells), not routable %d  [%4.0f s]"
                   % (it + 1, pres, len(todo), nbad, total, unrouted, time.time() - t0))
        print("  " + log[-1], flush=True)
        if best is None or (nbad + unrouted) < best[0]:
            best = (nbad + unrouted, it)
        if nbad == 0 and unrouted == 0:
            break
        pres *= pf
    # ---- clean-up: drop jobs until nothing is in conflict, then try each dropped one again with the others as walls
    dropped = []
    while True:
        worst = None
        for j in jobs:
            if j.ok:
                n = conflicts(grid, j)[0]
                if n and (worst is None or n > worst[0]):
                    worst = (n, j)
        if worst is None:
            break
        j = worst[1]
        grid.stamp_job(j, -1)
        j.clear()
        dropped.append(j)
    dropped += [j for j in jobs if not j.ok and j not in dropped]
    recovered = 0
    for j in sorted(dropped, key=lambda j_: (j_.kind != "stub", j_.net)):
        if route_job(grid, j, -1.0, margin=8.0) and conflicts(grid, j)[0] == 0:
            recovered += 1
        elif j.ok:
            grid.stamp_job(j, -1)
            j.clear()
    # ---- repair: an open net takes its way through the others; the ones then in its way are routed again around it
    # (with everything else as walls); if any of them finds no way, all of it is undone
    rounds = int(os.environ.get("CR_REPAIR", "40"))
    for rnd in range(rounds):
        failed = [j for j in jobs if not j.ok]
        if not failed:
            break
        j = failed[rnd % len(failed)]
        route_job(grid, j, 30.0, margin=8.0)
        if not j.ok:
            continue
        victims = [o for o in jobs if o is not j and o.ok and conflicts(grid, o)[0]]
        snap = {o.k: (o.paths, o.vias, o.pts, list(getattr(o, "stub_via", [])), list(getattr(o, "open", []))) for o in victims}
        for o in victims:
            grid.stamp_job(o, -1)
            o.clear()
        good = conflicts(grid, j)[0] == 0
        if good:
            for o in sorted(victims, key=lambda o_: -len(o_.terms)):
                if not (route_job(grid, o, -1.0, margin=8.0) and conflicts(grid, o)[0] == 0):
                    good = False
                    break
        if good:
            log.append("repair %d: %s routed, %d nets in its way routed again around it (%s)"
                       % (rnd + 1, j.net, len(victims), " ".join(o.net for o in victims)))
        else:
            for o in victims + [j]:
                if o.ok:
                    grid.stamp_job(o, -1)
                o.clear()
            for o in victims:
                o.paths, o.vias, o.pts, o.stub_via, o.open = snap[o.k]
                o.ok = True
                grid.stamp_job(o, +1)
            log.append("repair %d: %s - no way found (%d nets in its way), undone" % (rnd + 1, j.net, len(victims)))
        print("  " + log[-1], flush=True)
    failed = [j for j in jobs if not j.ok]
    open_pads = sorted(n for j in jobs if j.ok for n in getattr(j, "open", []))
    log.append("clean-up: %d jobs dropped from conflicts, %d of them routed again with the others as walls; %d left open: %s%s"
               % (len(dropped), recovered, len(failed), " ".join(sorted({j.net for j in failed})),
                  ("; supply / ground pads without their via: " + " ".join(open_pads)) if open_pads else ""))
    print("  " + log[-1], flush=True)
    # ---- smooth (string pulling against the final neighbours) and write to the board
    nets = board.GetNetsByName()
    ntr = nvia = 0
    for j in sorted(jobs, key=lambda j_: j_.k):
        if not j.ok:
            continue
        grid.stamp_job(j, -1)
        segs = []
        keep = {int(p[0]) for p in j.paths[1:]}         # where the later branches start on the earlier ones
        for path in j.paths:
            segs += smooth(grid, j.net, path, keep)
        # re-stamp from the smoothed geometry
        j.pts = raster_segments(grid, segs)
        grid.stamp_job(j, +1)
        net = nets[j.net]
        for (l, a, b) in segs:
            add_track(board, (a[0] * G, a[1] * G), (b[0] * G, b[1] * G), net, RL[l])
            ntr += 1
        for (i, jj) in j.vias:
            add_via(board, (i * G, jj * G), net)
            nvia += 1
    save(board, ROUTED)
    rep = report(board, jobs, log, time.time() - t0)
    print(rep, flush=True)
    print("  %d tracks, %d vias -> %s" % (ntr, nvia, ROUTED))


def raster_segments(grid, segs):
    per = {}
    for (l, a, b) in segs:
        n = max(1, int(math.ceil(max(abs(b[0] - a[0]), abs(b[1] - a[1])))))
        t = np.linspace(0, 1, n + 1)
        xi = np.rint(a[0] + (b[0] - a[0]) * t).astype(np.int64)
        yj = np.rint(a[1] + (b[1] - a[1]) * t).astype(np.int64)
        per.setdefault(l, []).append(yj * grid.W + xi)
    out = {}
    for l, parts in per.items():
        c_ = np.unique(np.concatenate(parts))
        out[l] = ((c_ % grid.W).astype(np.int32), (c_ // grid.W).astype(np.int32))
    return out


def clear_line(grid, net, l, a, b):
    """True when a straight track a -> b (cells) on layer l keeps its clearances: every grid cell around the line is
    free of hard obstacles of other nets and of other jobs' zones."""
    nid = grid.nid(net)
    n = max(1, int(math.ceil(2 * max(abs(b[0] - a[0]), abs(b[1] - a[1])))))
    t = np.linspace(0, 1, n + 1)
    x = a[0] + (b[0] - a[0]) * t
    y = a[1] + (b[1] - a[1]) * t
    for xi in (np.floor(x).astype(np.int64), np.ceil(x).astype(np.int64)):
        for yj in (np.floor(y).astype(np.int64), np.ceil(y).astype(np.int64)):
            o = grid.tho[l, yj, xi]
            if np.any((o != FREE) & (o != nid)) or np.any(grid.occt[l, yj, xi] > 0):
                return False
    return True


def smooth(grid, net, path, keep=frozenset()):
    """Path (global states) -> straight segments [(layer, (i, j), (i, j))]; within a layer run, greedy string pulling.
    States in keep (where another branch of the net joins this one) stay corners of the result."""
    N, W = grid.N, grid.W
    ls = (path // N).astype(int)
    cs = path % N
    pts = [(int(c_ % W), int(c_ // W)) for c_ in cs]
    segs = []
    k = 0
    while k < len(path) - 1:
        e = k
        while e + 1 < len(path) and ls[e + 1] == ls[k]:
            e += 1
        for (s0, s1) in _pieces(path, k, e, keep):
            segs += _pull(grid, net, ls[k], pts[s0:s1 + 1])
        k = e + 1 if e > k else k + 1
    return segs


def _pieces(path, k, e, keep):
    cut = [k] + [x for x in range(k + 1, e) if int(path[x]) in keep] + [e]
    return list(zip(cut[:-1], cut[1:]))


def _pull(grid, net, l, run):
    segs = []
    if True:
        a = 0
        while a < len(run) - 1:
            bb = a + 1
            lo, hi = a + 1, len(run) - 1
            # the farthest point still in sight (binary search over a monotone-enough test, then a linear back-off)
            best = a + 1
            step = 1
            while a + step < len(run) and clear_line(grid, net, l, run[a], run[a + step]):
                best = a + step
                step *= 2
            hi = min(len(run) - 1, a + step)
            lo = best
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if clear_line(grid, net, l, run[a], run[mid]):
                    lo = mid
                else:
                    hi = mid
            bb = max(best, lo)
            if run[bb] != run[a]:
                segs.append((l, run[a], run[bb]))
            a = bb
    return segs


def report(board, jobs, log, secs):
    board.BuildConnectivity()
    conn = board.GetConnectivity()
    length = {}
    vias = {}
    layers = {}
    for t in board.GetTracks():
        n = t.GetNetname()
        if t.GetClass() == "PCB_VIA":
            vias[n] = vias.get(n, 0) + 1
        else:
            length[n] = length.get(n, 0.0) + ToMM(t.GetLength())
            layers.setdefault(n, set()).add(board.GetLayerName(t.GetLayer()))
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname().startswith(("LPDDR4_", "EMMC_")) or p.GetNetname() in ("DDR_RZQ", "VCC1V8_DDR"):
                pads.setdefault(p.GetNetname(), []).append(p)
    complete = set()
    for n, ps in pads.items():
        items = {x.m_Uuid.AsString() for x in conn.GetConnectedItems(ps[0], 0)} | {ps[0].m_Uuid.AsString()}
        if all(p.m_Uuid.AsString() in items for p in ps):
            complete.add(n)
    groups = {}
    for n in pads:
        groups.setdefault(group_of(n), []).append(n)
    ddr = [n for n in pads if n.startswith("LPDDR4_")]
    lines = ["Memory bus of %s (%s), routed by tools/cpu_ram_board.py in %.0f s" % (PRJ, cpmodel.REV, secs),
             "board %.1f x %.1f mm, 10 layers; processor at (%.3f, %.3f), memory at (%.3f, %.3f), gap %.1f mm" % (BW, BH, SOC_X, SOC_Y, MEM_X, MEM_Y, GAP),
             ""] + log + ["",
             "memory bus nets complete end to end (KiCad's connectivity): %d of %d" % (sum(1 for n in ddr if n in complete), len(ddr)),
             "other routed nets complete: " + " ".join("%s=%s" % (n, "yes" if n in complete else "NO") for n in sorted(pads) if not n.startswith("LPDDR4_")),
             "",
             "group             complete   length of the complete nets      spread   vias  layers"]
    for key in sorted(groups):
        ns = groups[key]
        ok = [n for n in ns if n in complete]
        ls = [length.get(n, 0) for n in ok]
        lay = sorted({l for n in ok for l in layers.get(n, ())})
        lines.append("  %s %-12s  %2d / %2d   %s   %s  %-5s  %s" % (
            key[0], key[1], len(ok), len(ns), ("%6.2f .. %6.2f mm" % (min(ls), max(ls))) if ls else "        -         ",
            ("%5.2f" % (max(ls) - min(ls))) if ls else "  -  ",
            ("%d-%d" % (min(vias.get(n, 0) for n in ok), max(vias.get(n, 0) for n in ok))) if ok else "-", " ".join(lay)))
    lines.append("")
    lines.append("pairs (P / N length, skew; the layers each half uses)")
    for n in sorted(pads):
        m = re.match(r"(LPDDR4_(?:DQS\d|CLK))P(_[AB])$", n)
        if m:
            nn = m.group(1) + "N" + m.group(2)
            lp, ln = length.get(n, 0), length.get(nn, 0)
            lines.append("  %-20s %6.2f / %6.2f mm  skew %5.2f   P: %s   N: %s" % (
                m.group(1)[7:] + m.group(2), lp, ln, abs(lp - ln), " ".join(sorted(layers.get(n, ()))), " ".join(sorted(layers.get(nn, ())))))
    lines.append("")
    for key in sorted(groups):
        for n in sorted(groups[key]):
            lines.append("  %-24s %-9s %7.2f mm  %d via  %s%s" % (n, key[1], length.get(n, 0), vias.get(n, 0),
                                                                 " ".join(sorted(layers.get(n, ()))), "" if n in complete else "   NOT COMPLETE"))
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(NL.join(lines) + NL)
    return NL.join(lines[:len(log) + 12 + len(groups)])


# ================================================================================================ stage finish
def inside(poly, x, y):
    c = False
    n = len(poly)
    for k in range(n):
        (xa, ya), (xb, yb) = poly[k], poly[(k + 1) % n]
        if (ya > y) != (yb > y) and x < xa + (y - ya) * (xb - xa) / (yb - ya):
            c = not c
    return c


def place_caps(board, grid):
    """Every part still parked: on the bottom face as near its rail's balls as there is room, a via in each pad."""
    polys = plane_polys()
    rail_area = {}
    for n, l, poly, _ in polys:
        rail_area.setdefault(n, []).append(poly)
    chip_of_sheet = {"soc_ddr": "U1", "soc_power": "U1", "lpddr4": "U10", "soc_usb": "U1", "storage": "U20"}
    balls = {}
    for ref in CHIPS:
        for p in board.FindFootprintByReference(ref).Pads():
            balls.setdefault((ref, p.GetNetname()), []).append(pad_xy(p))
    nets = board.GetNetsByName()
    placed_boxes = []
    todo = []
    for fp in board.GetFootprints():
        x, y = ToMM(fp.GetPosition().x) - OX, ToMM(fp.GetPosition().y) - OY
        if not on_board(x, y):
            todo.append(fp)
    # big parts first (they need the bigger holes)
    todo.sort(key=lambda f: (-ToMM(f.GetBoundingBox(False).GetWidth()) * ToMM(f.GetBoundingBox(False).GetHeight()), f.GetReference()))
    done, failed = 0, []
    for fp in todo:
        pads = list(fp.Pads())
        names = [p.GetNetname() for p in pads if p.GetNetname() and p.GetNetname() != "GND"]
        rail = next((n for n in names if n in PLANE_NETS), names[0] if names else "GND")
        sheet = fp.GetSheetname().strip("/")
        chip = chip_of_sheet.get(sheet, "U1")
        if rail in CAP_TARGET:
            tx, ty = CAP_TARGET[rail]
        else:
            pts = (balls.get((chip, rail)) or [xy for r in CHIPS for xy in balls.get((r, rail), [])] or [(SOC_X, SOC_Y)])
            tx, ty = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        ok = False
        for rr in np.arange(0.0, 16.0, 0.15):
            nstep = max(1, int(2 * math.pi * rr / 0.15))
            for k in range(nstep):
                a = 2 * math.pi * k / nstep
                cx, cy = q(tx + rr * math.cos(a)), q(ty + rr * math.sin(a))
                for rot in (0, 90):
                    if try_cap(board, grid, fp, cx, cy, rot, rail, rail_area, placed_boxes, nets):
                        ok = True
                        break
                if ok:
                    break
            if ok:
                break
        if ok:
            done += 1
        else:
            failed.append(fp.GetReference())
    return done, failed


def try_cap(board, grid, fp, cx, cy, rot, rail, rail_area, boxes, nets):
    GP.set_pose(fp, cx, cy, rot, True)
    cb = GP.court(fp)
    if cb[0] < 0.6 or cb[1] < 0.6 or cb[2] > BW - 0.6 or cb[3] > BH - 0.6:
        return False
    for b in boxes:
        if not (cb[2] <= b[0] or b[2] <= cb[0] or cb[3] <= b[1] or b[3] <= cb[1]):
            return False
    for p in fp.Pads():
        shape = pad_shape(p)
        n = p.GetNetname()
        nid = grid.nid(n) if n else MULTI
        i0, j0, i1, j1, m = grid.shape_mask(shape, OFF_T - W_TR / 2)       # the pad itself, grown by the clearance
        sub = grid.tho[B_IDX, j0:j1, i0:i1]
        if np.any(m & (sub != FREE) & (sub != nid)):
            return False
        x, y = pad_xy(p)
        i, j = grid.cell(x, y)
        if n in PLANE_NETS and grid.vho[j, i] not in (FREE, nid):
            return False
        if n != "GND" and n in PLANE_NETS and not any(inside(poly, x, y) for poly in rail_area.get(n, [])):
            return False
    # accept: vias in the pads on plane nets (a pad of a supply that comes from off the board - VCC_1V8 on R69 - stays
    # a bare pad), obstacles for the next ones
    for p in fp.Pads():
        x, y = pad_xy(p)
        n = p.GetNetname()
        if n in PLANE_NETS:
            add_via(board, (q(x), q(y)), p.GetNet())
            grid.hard_via(q(x), q(y), n)
        grid.hard_shape([B_IDX], pad_shape(p), n or None)
    boxes.append(cb)
    fp.Reference().SetLayer(pcbnew.B_Fab)      # 63 names do not fit on the silkscreen between the vias: assembly drawing
    return True


def add_zone(board, net, layer, pts, prio=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.12))
    z.SetMinThickness(FromMM(0.1))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(FromMM(OX + x), FromMM(OY + y))
    board.Add(z)
    return z


def stage_finish():
    board = pcbnew.LoadBoard(ROUTED)
    grid = build_grid(board)
    done, failed = place_caps(board, grid)
    nets = board.GetNetsByName()
    for net, layer, poly, prio in plane_polys():
        add_zone(board, nets[net], layer, poly, prio)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    save(board, FINAL)
    board.BuildConnectivity()
    print("  decoupling on the bottom face: %d placed%s; planes filled; open connections: %d -> %s"
          % (done, (", NOT placed: " + " ".join(failed)) if failed else "", board.GetConnectivity().GetUnconnectedCount(False), FINAL))
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(NL + "finish: %d capacitors / resistors placed on the bottom face%s" % (done, (", NOT placed: " + " ".join(failed)) if failed else "") + NL)


def main():
    stage = sys.argv[sys.argv.index("--stage") + 1] if "--stage" in sys.argv else "all"
    for s in ("netlist", "place", "route", "finish"):
        if stage in (s, "all"):
            print("--- " + s, flush=True)
            {"netlist": stage_netlist, "place": stage_place, "route": stage_route, "finish": stage_finish}[s]()


if __name__ == "__main__":
    main()
