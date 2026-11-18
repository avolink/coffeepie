#!/usr/bin/env python
"""Routing, tranche 1.  Run with KiCad's Python, after gen_pcb.py:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route.py

What it does
  * declares the stack-up roles: F.Cu signal, In1 GND, In2 signal, In3 power, In4 GND, B.Cu signal
  * pours the GND planes (In1, In4) and the 5 V plane (In3) over the SELV part of the board only -
    nothing is poured under the PoE primary or the RJ45 / magnetics head
  * routes, on a 0.05 mm grid, the nets whose pads sit in a region with a collision-free placement
    (the bay strip and the front / battery area), and drops a via to the planes for every GND / 5 V pad there
It deliberately does NOT route
  * anything inside the codec core, Ethernet, PoE and HDMI areas (placement there still has collisions)
  * impedance-controlled pairs (USB 2.0, USB 3, HDMI, MDI, RGMII, DDR): those want the interactive
    differential-pair router and length tuning, not a maze router
The result is written back to commander_mainboard.kicad_pcb and summarised in build/routing_report.txt.
"""
import fnmatch
import heapq
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402
import gen_project                              # noqa: E402
from gen_pcb import CFG, OX, OY, STRIP, outline_pts    # noqa: E402

ROOT = cpmodel.ROOT
NL = chr(10)
G = float(os.environ.get("CP_GRID", "0.05"))     # routing grid, mm (0.025 for work between BGA balls)
TOL = G / 2                 # copper never extends more than this beyond a marked cell centre
FREE, MULTI = -1, -2
RLAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
VIA_KIND = None     # (via type, top layer, bottom layer) for a run with blind vias (the memory field); None = through
# NOT routed by this script, for the reason given in DESIGN_NOTES.md: the memory bus (it needs the vendor's
# length-matched reference layout; a maze-routed copy of it would look finished and not work).
SKIP_CLASSES = {"DDR"}
PAIR_CLASSES = ("USB2", "USB3_SS", "HDMI", "ETH_MDI")      # routed as coupled pairs: a trunk of two parallel tracks, then the ends
# supply nets: joined on the power layer in a stage of their own, then given copper pours there
POWER_PREFIX = ("VCC", "VDD", "VBUS", "VOUT", "MIPI_AVDD", "SVC_VBUS")
SKIP_NETS = {"CHASSIS"}
SY = CFG["STRIP_Y"]
HUB_FACE = 69.0         # hub board: left edge of its body = the socket's front face (board mm; 73.0 before 2026-11-18)
REGIONS = [   # name, x0, y0, x1, y1 (design mm); each window overlaps the real board edge by 1 mm
    # (the strip window starts in the right-hand corridor of the column: the USB 3 hub sits at the junction, and the
    #  pins on its left side need room to turn round)
    ("strip", CFG["SELV_COR"] + 0.3, SY - 1.0, CFG["COL_W"] + CFG["STRIP_L"] + 1.0, SY + CFG["STRIP_H"] + 1.0),
    ("front", -1.0, CFG["FRONT_Y0"], CFG["COL_W"] + 1.0, CFG["COL_L"] + 1.0),
    # the PoE converter: primary block, transformer, secondary, source selector (the test board has no Ethernet head,
    # so there the region runs to the rear edge and takes in the tap header)
    ("poe", -1.0, -1.0 if STRIP else 8.6, CFG["COL_W"], 60.3),
]
if cpmodel.VARIANT == "hub":
    # The hub board (branch m2-hub): the strip from the socket's front face (board x 73.0) to its far end, plus the
    # part of the M.2 tongue that sits in the socket's slot (from x 71.6), without the key notch.  The fingers
    # themselves (x 69.5-71.5) are joined to that by straight stubs drawn by tools/hub_board.py.  Design mm.
    # (2026-11-18: socket and card edge 4 mm further left, tools/j41_shift.py + tools/hub_shift.py: the body now starts
    #  at HUB_FACE = 69.0, it was 73.0)
    _F = HUB_FACE
    _HUB = [(_F, 81.3), (361.73, 81.3), (364.73, 84.3), (364.73, 100.02), (361.73, 103.02), (_F, 103.02),
            (_F, 102.08), (_F - 1.4, 102.08), (_F - 1.4, 86.8), (_F - 0.1, 86.8), (_F - 0.1, 85.3), (_F - 1.4, 85.3),
            (_F - 1.4, 82.24), (_F, 82.24)]

    # The bays' sink-mount receptacles sit in notches of the rear edge (tools/hub_midmount_swap.py): 9.42 mm wide,
    # 7.6 mm deep behind the mouth, R0.5 reliefs at the inner corners (taken here as 0.5 x 1.0 mm steps).  The bay
    # centres are read from the board file itself.
    def _hub_notched():
        import re as _re
        from hub_make_room import MOUTH_Y, NOTCH_HW, NOTCH_END, RELIEF, Y_TOP
        path = os.environ.get("CP_PCB") or os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb")
        txt = open(path, encoding="utf-8").read()
        cxs = sorted(float(m.group(1)) for m in _re.finditer(
            r'\(at ([\d.\-]+) [\d.\-]+[^)]*\)\s*\(descr "[^"]*"\)\s*\(tags "[^"]*"\)\s*\(property "Reference" "J3[1-9]"', txt))
        ye = MOUTH_Y + NOTCH_END
        top = [(HUB_FACE, Y_TOP)]
        for cx in cxs:
            lft, rgt = cx - NOTCH_HW, cx + NOTCH_HW
            top += [(lft, Y_TOP), (lft, ye - 2 * RELIEF), (lft - RELIEF, ye - 2 * RELIEF), (lft - RELIEF, ye),
                    (rgt + RELIEF, ye), (rgt + RELIEF, ye - 2 * RELIEF), (rgt, ye - 2 * RELIEF), (rgt, Y_TOP)]
        return top + _HUB[1:], len(cxs)

    _HUB_N, HUB_NOTCHES = _hub_notched()

    def outline_pts():                          # noqa: F811
        return [(x - OX, y - OY) for x, y in _HUB_N]
_OUT = outline_pts()
# the whole codec column, head to front edge: the stage that joins what the local windows could not
COLUMN = ("column", -1.0, math.floor(min(p_[1] for p_ in _OUT)) - 1.0, CFG["COL_W"] + 1.0, math.ceil(CFG["COL_L"]) + 1.0)
# Where a net leaves the strip window for the column: a line across the right-hand corridor, just above the stretch
# where the corridor steps back for the transformer.  The strip stage ends such a net there, the column stage picks it up.
PORT_Y = CFG["NOTCH_Y0"] - 0.35
PORT_X = (CFG["SELV_COR"] + 0.5, CFG["COL_W"] - 0.6)
# Pairs are handed over 1 mm further on: their two ends then stand clear of the row of single ends, and the column
# stage can start a coupled trunk from them.
PORT_Y_PAIR = PORT_Y + 1.0
ESCAPE_MARGIN = 0.6         # a ball is brought this far outside its package before the 0.05 mm grid takes over
# The Ethernet head (RJ45, magnetics, PHY) is NOT routed by this script: its line side must be kept 1.5 kV away from
# everything else, the transplanted placement mixes the two sides front and back, and where that boundary runs is a
# decision for a person.  Nothing is routed inside this box, and pads inside it are left alone.
HEAD_BOX = (10.6, -30.0, CFG["COL_W"] + 2.0, 8.0)
# SELV plane outlines (design mm); the board edge clips them
# right corridor + strip + lower column + left (HDMI) corridor and tab; the PoE primary block in the middle and the
# RJ45 / magnetics head stay bare
XL, XR = CFG["HDMI_COR"], CFG["SELV_COR"]
N0, N1, NXL, NXR = CFG["NOTCH_Y0"], CFG["NOTCH_Y1"], CFG["NOTCH_XL"], CFG["NOTCH_XR"]
LEFT_EDGE = [(XL, N0), (NXL, N0), (NXL, N1), (XL, N1)]                  # going towards the front (+y): step back past the transformer's primary row
RIGHT_EDGE = [(XR, N1), (NXR, N1), (NXR, N0), (XR, N0)]                 # going towards the rear (-y)
PLANE_GND = ([(XR, SY - 1.0), (326.0, SY - 1.0), (326.0, SY + 22.8), (31.0, SY + 22.8), (31.0, 120.0), (-1.0, 120.0),
              (-1.0, -21.0), (10.0, -21.0), (10.0, 7.0), (XL, 7.0)] + LEFT_EDGE + [(XL, 46.0), (XR, 46.0)] + RIGHT_EDGE)
PLANE_5V = [(XR, SY - 1.0), (326.0, SY - 1.0), (326.0, SY + 22.8), (31.0, SY + 22.8), (31.0, 60.0), (XR, 60.0)] + RIGHT_EDGE
if STRIP:           # test board: no Ethernet head, both corridors run to the rear edge; In2 is the power plane
    PLANE_GND = ([(XR, -1.0), (31.0, -1.0), (31.0, SY - 1.0), (326.0, SY - 1.0), (326.0, SY + 22.8), (31.0, SY + 22.8),
                  (31.0, 121.0), (-1.0, 121.0), (-1.0, -1.0), (XL, -1.0)] + LEFT_EDGE + [(XL, 46.0), (XR, 46.0)] + RIGHT_EDGE)
PLANES = {"GND": ("strip", "front", "poe", "column", "bga"), "VCC5V_BUS": ("strip",)}       # net -> regions where a plane is under the pads
# Where the PoE-primary copper may be (design mm rectangles): the primary zone, the band of the transformer's
# primary pad row, and on the test board the lane up to the tap header.  Everything else must stay
# BARRIER mm away from these rectangles, and primary nets must stay inside them.
BARRIER = 2.0
_ROW = CFG["T1_Y"] - 11.225
PRIMARY_AREA = [(CFG["PRI_X0"] - 0.3, CFG["PRI_Y0"] - 0.3, CFG["PRI_X1"] + 0.3, CFG["PRI_Y1"] + 0.3),
                (CFG["NOTCH_XL"] + BARRIER, _ROW - 1.5, CFG["NOTCH_XR"] - BARRIER, _ROW + 1.5)]
if STRIP:
    PRIMARY_AREA.append((CFG["PRI_X0"] + 1.0, 1.0, CFG["PRI_X1"] - 1.0, CFG["PRI_Y0"]))
# The Ethernet head, routed once its placement was settled by hand (2026-11-14; CP_HEAD=1, region "head").
# Its LINE side - the RJ45 pairs up to the transformers (PHY_MDI*), the centre taps (TR?_48V, already POE_PRIMARY)
# and the Bob Smith nodes (BS?) - is the same isolated domain as the PoE primary: it gets areas of its own, here PER
# LAYER (layer indices into RLAYERS: 0 F, 1 In2, 2 B), so that the centre-tap lines can run down an In2 corridor
# under the low-voltage side to the bridges.  A via needs the area on all three layers.
#   band: B / In2 under the RJ45 body, from the jack's pads down to the transformers' line pins (row at y -1.0),
#         with the Bob Smith resistors under the jack's pads and the 2 kV cap C60 by the left shield pin
#   jack: F under the RJ45 body (its pads and the vias down to the band)
#   corridor: In2, from the band down to the PoE primary zone
HEAD = os.environ.get("CP_HEAD") == "1"
LINE_NETS = ("PHY_MDI?_[PN]", "BS", "BS?")
HEAD_LINE_AREA = [
    (10.4, -5.7, 30.0, -1.8, (1, 2)),        # band (from C60's 2.3 mm wide BS pad)
    (14.9, -8.2, 27.0, -5.7, (1, 2)),        # band, under the jack's pads (Bob Smith resistors, jack vias)
    (11.0, -8.2, 29.6, -4.2, (0,)),          # jack (top face; nothing else under the RJ45 body)
    (9.0, -1.8, 12.2, 10.7, (1,)),           # centre-tap corridor
]
if HEAD:
    PRIMARY_AREA[0] = (PRIMARY_AREA[0][0], 10.2) + PRIMARY_AREA[0][2:]      # (the real primary copper starts at y 10.6)
    PRIMARY_AREA += HEAD_LINE_AREA
    HEAD_BOX = (0.0, 0.0, -1.0, -1.0)           # (nothing is kept out any more)
    REGIONS.append(("head", -1.0, -20.6, CFG["COL_W"] + 1.0, 17.0))      # down to the bridges' centre-tap pads
    PLANES["GND"] = PLANES["GND"] + ("head",)    # (the head's own ground pours, cut back 2 mm from the line areas)
    SKIP_NETS.discard("CHASSIS")                # (the Bob Smith cap and the 4.7 nF / 1 M to the jack's shield)
# Branch m2-hub (CP_LINK=1, region "link"): the bay strip became its own board, plugged into socket J41 at the column's
# right edge (tools/main_cut.py).  The window covers the socket and the barrier parts moved out of its way; the two
# extra primary areas hold the primary pads of the optocoupler U31 (now below the clamp diode, 0.7 mm past the zone's
# lower edge) and of the Y capacitor C518 (in the bump beside the transformer's primary pins).
LINK = os.environ.get("CP_LINK") == "1"
# (2026-11-18) The user moved the PoE primary block by hand (its parts, not the transformer T1 nor the barrier parts
# U31 / C518), and socket J41 went 4 mm left with tools/j41_shift.py:
#   CP_PRI_SHIFT=dx,dy  shifts the primary zone's rectangle (PRIMARY_AREA[0]) by that much (design mm);
#   CP_PRI_FROM_BOARD=1 adds every primary pad / track / via already on the board (CP_PCB) as an area of its own,
#                       so that hand-moved primary copper outside the rectangles is still kept 2 mm off;
#   CP_LINK_DX=dx       moves the link window's left edge with the socket (its right edge then stops at the column's
#                       edge: the tab is gone);
#   CP_SKIP_CLASSES=A,B net classes this run leaves alone (e.g. POE_PRIMARY: the hand-placed primary copper).
if os.environ.get("CP_PRI_SHIFT"):
    _sx, _sy = (float(v_) for v_ in os.environ["CP_PRI_SHIFT"].split(","))
    PRIMARY_AREA[0] = (PRIMARY_AREA[0][0] + _sx, PRIMARY_AREA[0][1] + _sy, PRIMARY_AREA[0][2] + _sx,
                       PRIMARY_AREA[0][3] + _sy) + tuple(PRIMARY_AREA[0][4:])
if os.environ.get("CP_PRI_FROM_BOARD") == "1":
    def _pri_from_board():
        bd = pcbnew.LoadBoard(os.environ.get("CP_PCB") or os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb"))
        pri_cls = {c_["name"]: c_ for c_ in gen_project.CLASSES}.get("POE_PRIMARY", {})
        pats = pri_cls.get("nets", []) if isinstance(pri_cls, dict) else []
        out_ = []

        def is_pri(n_):
            return any(fnmatch.fnmatch(n_, p_) for p_ in pats) if pats else (
                n_.startswith("POE_") and n_ not in ("POE_SEC", "POE_SNUB")) or fnmatch.fnmatch(n_, "TR?_48V")
        items_ = [p_ for fp_ in bd.GetFootprints() for p_ in fp_.Pads()] + list(bd.GetTracks())
        for it_ in items_:
            if it_.GetNetname() and is_pri(it_.GetNetname()):
                bb_ = it_.GetBoundingBox()
                out_.append((ToMM(bb_.GetLeft()) - OX, ToMM(bb_.GetTop()) - OY, ToMM(bb_.GetRight()) - OX,
                             ToMM(bb_.GetBottom()) - OY))
        return out_
    PRIMARY_AREA += _pri_from_board()
if os.environ.get("CP_SKIP_CLASSES"):
    SKIP_CLASSES.update(x_ for x_ in os.environ["CP_SKIP_CLASSES"].split(",") if x_)
if LINK:
    PRIMARY_AREA += [(18.6, 40.6, 21.2, 43.0), (22.0, 34.5, 24.2, 37.8)]
    # (x to 33.3: the tab's edge is at 33.9 and the router still knows the old L outline; down to y 85: the link
    #  nets run on to the RK3566's balls)
    _ldx = float(os.environ.get("CP_LINK_DX", "0"))
    # (the router still takes the old L outline for the board edge, so with the tab gone the window itself has to stop
    #  short of the column's edge: 0.7 mm leaves a 0.45 mm via 0.25 mm from it)
    REGIONS.append(("link", 21.5 + _ldx, 4.0, 33.3 if _ldx == 0 else CFG["COL_W"] - 0.7, 85.0))
    PLANES["GND"] = PLANES["GND"] + ("link",)
    PLANES["VCC5V_BUS"] = PLANES["VCC5V_BUS"] + ("link",)     # (In3 plane under the socket's front row)

CLS ={c["name"]: c for c in gen_project.CLASSES}


def ceil_(v):
    return int(math.ceil(v - 1e-9))


# Every net keeps its own class clearance from foreign copper; copper of a class with a LARGER clearance is marked
# that much fatter, so that the others keep its distance too.  "Larger" is measured from the smallest clearance a
# track can end up with: 0.10 mm on the 0.05 mm grid (rounding gives the 0.09 classes that much), 0.09 mm on a finer one.
BASE_CL = 0.10 if G >= 0.05 - 1e-9 else 0.09
HOLE_CL = 0.20              # board rule: a drilled hole stays this far from copper of another net


def hole_extra(via_d, via_drill):
    """Cells a via is marked fatter, for TRACKS of other nets, so that they keep HOLE_CL from its hole (matters for the
    0.25 / 0.15 vias, whose annular ring is only 0.05 mm).  Another via is judged by the ordinary clearance."""
    need = HOLE_CL - (via_d - via_drill) / 2 - 0.09
    if need <= 1e-9:
        return 0
    return ceil_((via_d / 2 - TOL + need) / G) - max(0, ceil_((via_d / 2 - TOL) / G))


class RC:
    """Routing parameters of a net class, in grid cells."""

    def __init__(self, name, w, cl, via_d, via_drill):
        self.name, self.w, self.cl, self.via_d, self.via_drill = name, w, cl, via_d, via_drill
        self.extra = ceil_((cl - BASE_CL) / G) if cl > BASE_CL + 1e-9 else 0   # extra growth so other classes keep cl
        self.Kt = ceil_((cl + w / 2 + TOL) / G) - 1                       # track centre: no foreign copper within Kt cells
        self.mt = max(0, ceil_((w / 2 - TOL) / G)) + self.extra           # how far a track's copper is marked
        self.Kv = ceil_((cl + via_d / 2 + TOL) / G) - 1
        self.mv = max(0, ceil_((via_d / 2 - TOL) / G)) + self.extra
        self.hx = max(0, hole_extra(via_d, via_drill) - self.extra)      # further growth, in the maps that tracks are judged by


RCS = {
    "Default": RC("Default", 0.15, CLS["Default"]["clearance"], 0.45, 0.20),
    "PWR": RC("PWR", CLS["PWR"]["track_width"], CLS["PWR"]["clearance"], 0.60, 0.30),
    "PWR_5V": RC("PWR_5V", CLS["PWR_5V"]["track_width"], CLS["PWR_5V"]["clearance"], 0.60, 0.30),
    # memory bus: finest track the board allows, and a via small enough to sit in a 0.25 mm BGA pad
    "DDR": RC("DDR", 0.09, 0.09, 0.25, 0.15),
    # PoE primary: 57 V between neighbours, solder-masked board; 0.20 mm (the controller's own pin gap; IPC-2221B: 0.13)
    "POE_PRIMARY": RC("POE_PRIMARY", 0.40, 0.20, 0.80, 0.40),
    # USB data: the pair geometry of the class (90 ohm differential nominal)
    "USB2": RC("USB2", CLS["USB2"]["diff_pair_width"], CLS["USB2"]["clearance"], 0.45, 0.20),
    "USB3_SS": RC("USB3_SS", CLS["USB3_SS"]["diff_pair_width"], CLS["USB3_SS"]["clearance"], 0.45, 0.20),
    "HDMI": RC("HDMI", CLS["HDMI"]["diff_pair_width"], CLS["HDMI"]["clearance"], 0.45, 0.20),
    "ETH_MDI": RC("ETH_MDI", CLS["ETH_MDI"]["diff_pair_width"], CLS["ETH_MDI"]["clearance"], 0.45, 0.20),
    "RGMII": RC("RGMII", CLS["RGMII"]["track_width"], CLS["RGMII"]["clearance"], 0.45, 0.20),
    # links between the vias of supply balls under a BGA (the pours widen them afterwards)
    "BALL": RC("BALL", 0.09, 0.10, 0.25, 0.15),
    # the way out from under a BGA for a net whose class wants 0.10 mm (the 0.09 mm classes use the DDR figures)
    "ESC10": RC("ESC10", 0.09, 0.10, 0.25, 0.15),
}
SCALE = 0.05 / G            # search windows and budgets are written for the 0.05 mm grid
# neck-down used where the class width cannot enter a fine-pitch pad
THIN = {n: RC(n + "_thin", 0.15, RCS[n].cl, RCS[n].via_d, RCS[n].via_drill) for n in ("PWR", "PWR_5V", "POE_PRIMARY")}
# (0.15 also for the PoE primary: at the TPS23754's 0.65 mm pitch nothing wider leaves a pin with 0.20 mm to the next)
# A pair is searched as ONE fat track; the two real tracks are then drawn either side of its centre line.
PAIR_MARGIN = 0.125         # mm of extra room in the fat corridor: mitred corners and the flared ends stay inside it
PAIR_VIA_OFF = 0.30         # where a pair changes layer, its two vias sit this far either side of the centre line
PAIR_BACK = 0.35            # ... and the tracks start to spread this far before the vias
PAIR_FLARE = 0.10           # the two ends of a trunk are spread by this much, so each can be reached on its own
PAIR_GATE = 6.0             # a P pad and an N pad closer than this form one end of a pair
PAIR_VIA_COST = 300         # (in steps of the coarse trunk grid: about 3 mm of track)
PAIR_RIM = 2.9              # the pairs of a big fine-pitch IC are first brought straight out to a ring this far from its pads


class PairRC:
    def __init__(self, cname):
        rc = RCS[cname]
        self.rc = rc
        self.gap = CLS[cname]["diff_pair_gap"]
        self.off = (rc.w + self.gap) / 2                                    # centre line -> centre of each track
        self.K = ceil_((rc.cl + rc.w + self.gap / 2 + PAIR_MARGIN + TOL) / G) - 1
        self.Kv = ceil_((rc.cl + PAIR_VIA_OFF + rc.via_d / 2 + TOL) / G) - 1


PAIRS = {c: PairRC(c) for c in PAIR_CLASSES}
KSET = sorted({rc.Kt for rc in list(RCS.values()) + list(THIN.values())} | {rc.Kv for rc in RCS.values()}
              | {p_.K for p_ in PAIRS.values()} | {p_.Kv for p_ in PAIRS.values()})
# Clearance maps that only a SMALL via is judged by (fine grid; no track class has this K): in these the small vias
# are not grown for their holes - two of them on neighbouring balls are legal.  Everything else, tracks and the
# larger vias alike, sees them grown.
VIA_ONLY_K = set()
if G < 0.05 - 1e-9:
    VIA_ONLY_K = {rc.Kv for rc in RCS.values() if rc.hx} - ({rc.Kt for rc in RCS.values()} | {p_.K for p_ in PAIRS.values()})
# Where a 0.15 mm hole may go: nothing foreign within HOLE_CL of the hole.  A map of its own (fine grid only), in
# which the balls of a BGA are marked one cell smaller: the ball next door, 0.4 mm away, is exactly at the limit and
# must not be rounded into a violation.
K_HOLE = (ceil_((HOLE_CL + 0.075 + TOL) / G) - 1) if G < 0.05 - 1e-9 else None
if K_HOLE is not None:
    for k_ in (K_HOLE, K_HOLE + 1):         # (+1: the same map for a via that is not in a ball - there the one cell is not given away)
        assert k_ not in ({rc.Kt for rc in RCS.values()} | {p_.K for p_ in PAIRS.values()}), "K_HOLE collides with a track class"
    KSET = sorted(set(KSET) | {K_HOLE, K_HOLE + 1})
    VIA_ONLY_K = VIA_ONLY_K | {K_HOLE, K_HOLE + 1}
HOLE_KS = (K_HOLE, K_HOLE + 1) if K_HOLE is not None else ()
K_NOVIA = ceil_((0.30 + 0.05) / G)      # no via centre this close to a pad (keeps vias out of pads)
K_VIAVIA = ceil_(0.60 / G)              # ... nor this close to another via centre (hole-to-hole 0.25)
EDGE = ceil_(0.30 / G)                  # copper stays this far from the board edge
LANE = 1.0                              # mm reserved straight out of every pad of a fine-pitch part, for that pad only
SOFT_LEN = 3.0                          # mm in front of such a pad where other nets pay extra to pass (keeps exits open)
SOFT = 40                               # that extra cost, per cell


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def dilate(mask, k):
    """Chebyshev dilation of a boolean array by k cells (array must already have room)."""
    if k <= 0:
        return mask.copy()
    acc = mask.copy()
    for s in range(1, k + 1):
        acc[:, s:] |= mask[:, :-s]
        acc[:, :-s] |= mask[:, s:]
    out = acc.copy()
    for s in range(1, k + 1):
        out[s:, :] |= acc[:-s, :]
        out[:-s, :] |= acc[s:, :]
    return out


class Region:
    def __init__(self, name, x0, y0, x1, y1):
        self.name, self.x0, self.y0, self.x1, self.y1 = name, x0, y0, x1, y1
        self.nx = int(round((x1 - x0) / G)) + 1
        self.ny = int(round((y1 - y0) / G)) + 1
        self.D = {k: np.full((3, self.ny, self.nx), FREE, np.int16) for k in KSET}
        if STRIP:                           # 4-layer board: the middle routing layer is the power plane
            for D in self.D.values():
                D[1] = MULTI
        self.novia = np.zeros((self.ny, self.nx), bool)
        self.soft = np.full((3, self.ny, self.nx), FREE, np.int16)      # whose exit zone a cell is in
        self.pri = self.nopri = None        # isolation: where primary copper may be / where other copper may not
        # (both masks per routing layer: an area may hold on some layers only, see HEAD_LINE_AREA)
        pri = np.zeros((3, self.ny, self.nx), bool)
        for area in PRIMARY_AREA:
            xa, ya, xb, yb = area[:4]
            lays = list(area[4]) if len(area) > 4 else [0, 1, 2]
            i0, j0 = max(0, ceil_((xa - x0) / G)), max(0, ceil_((ya - y0) / G))
            i1, j1 = min(self.nx - 1, int((xb - x0) / G)), min(self.ny - 1, int((yb - y0) / G))
            if i0 <= i1 and j0 <= j1:
                pri[lays, j0:j1 + 1, i0:i1 + 1] = True
        if pri.any() or (x0 < CFG["PRI_X1"] + BARRIER + 1 and y0 < CFG["PRI_Y1"] + BARRIER + 1 and y1 > 0):
            # a track or via of a primary net has its CENTRE at least 0.5 mm inside the area: with the largest via
            # (0.8 mm) its copper then ends where the area ends, 2 mm from the planes and from everything else
            ke = ceil_(0.5 / G)
            self.pri = np.zeros((3, self.ny, self.nx), bool)
            for l in range(3):
                big = np.zeros((self.ny + 2 * ke, self.nx + 2 * ke), bool)
                big[ke:-ke, ke:-ke] = ~pri[l]
                self.pri[l] = ~dilate(big, ke)[ke:-ke, ke:-ke]
            kb = ceil_((BARRIER + 0.25) / G)     # + half the widest track and a grid step
            self.nopri = np.zeros((3, self.ny, self.nx), bool)
            for l in range(3):
                big = np.zeros((self.ny + 2 * kb, self.nx + 2 * kb), bool)
                for area in PRIMARY_AREA:       # (rasterised again with a border, so a primary area just outside the window counts)
                    if len(area) > 4 and l not in area[4]:
                        continue
                    xa, ya, xb, yb = area[:4]
                    i0, j0 = max(0, ceil_((xa - x0) / G) + kb), max(0, ceil_((ya - y0) / G) + kb)
                    i1, j1 = min(big.shape[1] - 1, int((xb - x0) / G) + kb), min(big.shape[0] - 1, int((yb - y0) / G) + kb)
                    if i0 <= i1 and j0 <= j1:
                        big[j0:j1 + 1, i0:i1 + 1] = True
                self.nopri[l] = dilate(big, kb)[kb:-kb, kb:-kb]
        self.pads = {}          # netcode -> [dict(pad=, cells=[(l,i,j)], cx=, cy=, layers=, node=)]
        self.padcell = {}       # netcode -> {(l,i,j): index into pads[netcode]}
        self.tree = {}          # netcode -> {(l,i,j): node} centre-line cells of routed copper
        self.exact = {}         # netcode -> {(l,i,j): (x, y)} where a track end is not on the grid
        self.tips = {}          # netcode -> [(l, x, y)] loose ends of copper that was already on the board
        self.uf = []            # union-find over nodes: which pads / tracks of a net are already joined

    def node(self):
        self.uf.append(len(self.uf))
        return len(self.uf) - 1

    def find(self, a):
        uf = self.uf
        while uf[a] != a:
            uf[a] = uf[uf[a]]
            a = uf[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.uf[ra] = rb

    def assign(self, net, cells, node):
        """These centre-line cells are copper of 'net' belonging to 'node'; whatever they touch is joined to it."""
        t = self.tree.setdefault(net, {})
        pc = self.padcell.get(net)
        for c in cells:
            o = t.get(c)
            if o is None:
                t[c] = node
            elif o != node:
                self.union(o, node)
            if pc is not None:
                n = pc.get(c)
                if n is not None:
                    self.union(self.pads[net][n]["node"], node)

    def seg_cells(self, a, b):
        """Grid cells along the segment a-b (design mm), in order, inside the window; and whether it lies on the grid."""
        (ax, ay), (bx, by) = a, b
        fa, fb, ga, gb = (ax - self.x0) / G, (ay - self.y0) / G, (bx - self.x0) / G, (by - self.y0) / G
        on = all(abs(v - round(v)) < 1e-3 for v in (fa, fb, ga, gb)) and (
            round(fa) == round(ga) or round(fb) == round(gb) or abs(round(fa) - round(ga)) == abs(round(fb) - round(gb)))
        n = max(1, int(math.ceil(max(abs(ga - fa), abs(gb - fb)) * (1 if on else 2))))
        out, last = [], None
        for k in range(n + 1):
            c = (int(round(fa + (ga - fa) * k / n)), int(round(fb + (gb - fb) * k / n)))
            if c != last and 0 <= c[0] < self.nx and 0 <= c[1] < self.ny:
                out.append(c)
            last = c
        return out, on

    def xy(self, i, j):
        return self.x0 + i * G, self.y0 + j * G

    def stamp_via(self, i, j, r, hx, net, via_d=None):
        """A via of 'net' at cell (i, j): radius r cells in every map, r + hx in the maps that tracks are judged by.
        In the map that the HOLE of a new small via is judged by, it is marked like a ball: its bare pad, one cell
        smaller (two such vias on neighbouring 0.4 mm-pitch balls are exactly at the limit, and legal)."""
        rh = None
        if K_HOLE is not None and via_d is not None:
            rh = max(0, ceil_((via_d / 2 - TOL) / G) - 1)
        for l in range(3):
            self.stamp(l, i - r, j - r, disc(r), net, skip=HOLE_KS if rh is not None else ())
            if rh is not None:
                self.stamp(l, i - rh, j - rh, disc(rh), net, only=HOLE_KS)
            if hx:
                self.stamp(l, i - r - hx, j - r - hx, disc(r + hx), net, skip=VIA_ONLY_K)

    def stamp(self, l, i0, j0, mask, net, skip=(), only=None):
        """Mark copper cells (mask anchored at i0, j0) of 'net' on routing layer l in every clearance map."""
        h, w = mask.shape
        for k, D in self.D.items():
            if k in skip or (only is not None and k not in only):
                continue
            big = np.zeros((h + 2 * k, w + 2 * k), bool)
            big[k:k + h, k:k + w] = mask
            big = dilate(big, k)
            a0, b0 = i0 - k, j0 - k
            ia, ja = max(a0, 0), max(b0, 0)
            ib, jb = min(a0 + big.shape[1], self.nx), min(b0 + big.shape[0], self.ny)
            if ia >= ib or ja >= jb:
                continue
            sel = big[ja - b0:jb - b0, ia - a0:ib - a0]
            view = D[l, ja:jb, ia:ib]
            if net == MULTI:
                view[sel] = MULTI
            else:
                free = sel & (view == FREE)
                other = sel & (view != FREE) & (view != net)
                view[free] = net
                view[other] = MULTI

    def stamp_cells(self, l, cells, grow, net):
        """cells: [(i, j)] centre-line cells; grown by 'grow' cells into copper."""
        for n in range(0, len(cells), 48):
            ch = cells[n:n + 49]
            i0 = min(c[0] for c in ch) - grow
            j0 = min(c[1] for c in ch) - grow
            w = max(c[0] for c in ch) + grow - i0 + 1
            h = max(c[1] for c in ch) + grow - j0 + 1
            m = np.zeros((h, w), bool)
            for i, j in ch:
                m[j - j0, i - i0] = True
            self.stamp(l, i0, j0, dilate(m, grow), net)


def raster_outline(reg, pts):
    ins = np.zeros((reg.ny, reg.nx), bool)
    xs = reg.x0 + np.arange(reg.nx) * G
    edges = list(zip(pts, pts[1:] + pts[:1]))
    for j in range(reg.ny):
        y = reg.y0 + j * G + 1e-6
        xc = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in edges if (ay > y) != (by > y))
        for a, b in zip(xc[0::2], xc[1::2]):
            ins[j, (xs >= a) & (xs <= b)] = True
    return ins


def pad_mask(reg, pad):
    """Cells whose centre lies within TOL of the pad copper -> (i0, j0, mask) or None."""
    bb = pad.GetBoundingBox()
    xa, ya = ToMM(bb.GetLeft()) - OX - TOL, ToMM(bb.GetTop()) - OY - TOL
    xb, yb = ToMM(bb.GetRight()) - OX + TOL, ToMM(bb.GetBottom()) - OY + TOL
    i0, j0 = max(0, ceil_((xa - reg.x0) / G)), max(0, ceil_((ya - reg.y0) / G))
    i1, j1 = min(reg.nx - 1, int(math.floor((xb - reg.x0) / G + 1e-9))), min(reg.ny - 1, int(math.floor((yb - reg.y0) / G + 1e-9)))
    if i0 > i1 or j0 > j1:
        return None
    m = np.zeros((j1 - j0 + 1, i1 - i0 + 1), bool)
    acc = FromMM(TOL)
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            x, y = reg.xy(i, j)
            if pad.HitTest(P(x, y), acc):
                m[j - j0, i - i0] = True
    return (i0, j0, m) if m.any() else None


def disc(r_cells):
    n = int(r_cells)
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1]
    return (xx * xx + yy * yy) <= (r_cells + 0.3) ** 2


# --------------------------------------------------------------------------
# search
# --------------------------------------------------------------------------
STEP = ((10, 14), (13, 18), (11, 15))       # per routing layer: orthogonal / diagonal cost (In2 and B cost a little more)
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
TURN = 3
VIA_COST = 500
FANOUT_VIA = 300
HW = 2                      # heuristic weight (weighted A*)
VIA_L = [0, 2] if STRIP else [0, 1, 2]     # routing layers a via must find free copper on (the 4-layer board's In2 is a plane)


def search(okb, vokb, goalb, W, H, starts, gbox, fanout=False, max_exp=1500000, penb=None):
    """A* on a (3, H, W) window.  Returns the list of states from a start to the goal, or None.
    fanout: the goal is any cell where a via fits (on the start layer), or a cell of goalb."""
    WH = W * H
    INF = 1 << 60
    g, par = {}, {}
    heap = []
    gx0, gy0, gx1, gy1 = gbox
    for s in starts:
        g[s] = 0
        heapq.heappush(heap, (0, 0, s, -1))
    exp = 0
    while heap:
        f, gc, s, pd = heapq.heappop(heap)
        if s < 0:                               # virtual "drop a via here" node (fan-out mode)
            return _path(par, -s - 1), True
        if g.get(s, INF) < gc:
            continue
        l, r = divmod(s, WH)
        if goalb is not None and goalb[l][r]:
            return _path(par, s), False
        exp += 1
        if exp > max_exp:
            return None, False
        y, x = divmod(r, W)
        okl = okb[l]
        pl = penb[l] if penb is not None else None
        co, cd = STEP[l]
        if fanout and vokb[r]:
            heapq.heappush(heap, (gc + FANOUT_VIA, gc + FANOUT_VIA, -s - 1, -1))
        for d in range(8):
            dx, dy = DIRS[d]
            x2, y2 = x + dx, y + dy
            if x2 < 0 or y2 < 0 or x2 >= W or y2 >= H:
                continue
            r2 = y2 * W + x2
            if not okl[r2]:
                continue
            if d >= 4 and not (okl[y * W + x2] and okl[y2 * W + x]):
                continue
            nc = gc + (cd if d >= 4 else co) + (TURN if d != pd and pd >= 0 else 0)
            if pl is not None and pl[r2]:
                nc += SOFT
            s2 = l * WH + r2
            if nc < g.get(s2, INF):
                g[s2] = nc
                par[s2] = s
                if fanout:
                    hh = 0
                else:
                    ax = gx0 - x2 if x2 < gx0 else (x2 - gx1 if x2 > gx1 else 0)
                    ay = gy0 - y2 if y2 < gy0 else (y2 - gy1 if y2 > gy1 else 0)
                    hh = HW * (10 * max(ax, ay) + 4 * min(ax, ay))
                heapq.heappush(heap, (nc + hh, nc, s2, d))
        if not fanout and vokb is not None and vokb[r]:
            for l2 in (0, 1, 2):
                if l2 == l or not okb[l2][r]:
                    continue
                nc = gc + VIA_COST
                s2 = l2 * WH + r
                if nc < g.get(s2, INF):
                    g[s2] = nc
                    par[s2] = s
                    ax = gx0 - x if x < gx0 else (x - gx1 if x > gx1 else 0)
                    ay = gy0 - y if y < gy0 else (y - gy1 if y > gy1 else 0)
                    heapq.heappush(heap, (nc + HW * (10 * max(ax, ay) + 4 * min(ax, ay)), nc, s2, -1))
    return None, False


ANG = (0, 4, 2, 6, 1, 7, 3, 5)           # direction index -> multiples of 45 degrees
TURN8 = [[min(abs(ANG[a] - ANG[b]), 8 - abs(ANG[a] - ANG[b])) for b in range(8)] for a in range(8)]


def search_pair(okb, vokb, goalb, W, H, starts, gbox, max_exp=1500000, penb=None):
    """Like search(), for the centre line of a pair: the direction is part of the state, a step turns by 45 degrees
    at most, and the direction is kept through a layer change.  Returns [(layer, x, y)] or None."""
    WH = W * H
    INF = 1 << 60
    g, par = {}, {}
    heap = []
    gx0, gy0, gx1, gy1 = gbox
    for s, c0 in starts:
        g[s * 9] = c0
        heapq.heappush(heap, (c0, c0, s, -1))
    exp = 0
    while heap:
        f, gc, s, pd = heapq.heappop(heap)
        key = s * 9 + pd + 1
        if g.get(key, INF) < gc:
            continue
        l, r = divmod(s, WH)
        if goalb[l][r]:
            out = []
            while True:
                s_, pd_ = divmod(key, 9)
                l_, r_ = divmod(s_, WH)
                out.append((l_, r_ % W, r_ // W))
                if key not in par:
                    break
                key = par[key]
            out.reverse()
            return out
        exp += 1
        if exp > max_exp:
            return None
        y, x = divmod(r, W)
        okl = okb[l]
        pl = penb[l] if penb is not None else None
        co, cd = STEP[l]
        for d in range(8):
            if pd >= 0 and TURN8[pd][d] > 1:
                continue
            dx, dy = DIRS[d]
            x2, y2 = x + dx, y + dy
            if x2 < 0 or y2 < 0 or x2 >= W or y2 >= H:
                continue
            r2 = y2 * W + x2
            if not okl[r2]:
                continue
            if d >= 4 and not (okl[y * W + x2] and okl[y2 * W + x]):
                continue
            nc = gc + (cd if d >= 4 else co) + (2 * TURN if d != pd and pd >= 0 else 0)
            if pl is not None and pl[r2]:
                nc += SOFT
            k2 = (l * WH + r2) * 9 + d + 1
            if nc < g.get(k2, INF):
                g[k2] = nc
                par[k2] = key
                ax = gx0 - x2 if x2 < gx0 else (x2 - gx1 if x2 > gx1 else 0)
                ay = gy0 - y2 if y2 < gy0 else (y2 - gy1 if y2 > gy1 else 0)
                heapq.heappush(heap, (nc + HW * (10 * max(ax, ay) + 4 * min(ax, ay)), nc, l * WH + r2, d))
        if vokb is not None and vokb[r] and pd >= 0:
            for l2 in (0, 1, 2):
                if l2 == l or not okb[l2][r]:
                    continue
                nc = gc + PAIR_VIA_COST
                k2 = (l2 * WH + r) * 9 + pd + 1
                if nc < g.get(k2, INF):
                    g[k2] = nc
                    par[k2] = key
                    ax = gx0 - x if x < gx0 else (x - gx1 if x > gx1 else 0)
                    ay = gy0 - y if y < gy0 else (y - gy1 if y > gy1 else 0)
                    heapq.heappush(heap, (nc + HW * (10 * max(ax, ay) + 4 * min(ax, ay)), nc, l2 * WH + r, pd))
    return None


# ---- geometry of a pair ----
def _simplify(pts):
    """Drop the points inside straight runs."""
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        ax, ay = out[-1]
        (bx, by), (cx, cy) = pts[k], pts[k + 1]
        if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
            out.append(pts[k])
    out.append(pts[-1])
    return out


def _corners(pts, lmin):
    """A short segment between two turns of the same sense becomes one corner (its offset copies would fold over)."""
    pts = list(pts)
    changed = True
    while changed and len(pts) >= 4:
        changed = False
        for k in range(1, len(pts) - 2):
            a, b, c, d = pts[k - 1], pts[k], pts[k + 1], pts[k + 2]
            if math.hypot(c[0] - b[0], c[1] - b[1]) >= lmin:
                continue
            z1 = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            z2 = (c[0] - b[0]) * (d[1] - c[1]) - (c[1] - b[1]) * (d[0] - c[0])
            if z1 * z2 <= 0:
                continue
            ux, uy, vx, vy = b[0] - a[0], b[1] - a[1], d[0] - c[0], d[1] - c[1]
            den = ux * vy - uy * vx
            if abs(den) < 1e-12:
                continue
            t = ((c[0] - a[0]) * vy - (c[1] - a[1]) * vx) / den
            pts[k:k + 2] = [(a[0] + ux * t, a[1] + uy * t)]
            changed = True
            break
    return pts


def _unit(a, b):
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _trim(pts, back, at_end):
    """The polyline shortened by 'back' mm at one end -> (points, the point cut off)."""
    q = list(reversed(pts)) if at_end else list(pts)
    left = back
    while len(q) >= 2:
        d = math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1])
        if d > left + 1e-9:
            u = _unit(q[0], q[1])
            q[0] = (q[0][0] + u[0] * left, q[0][1] + u[1] * left)
            return (list(reversed(q)) if at_end else q)
        left -= d
        q.pop(0)
    return None


def _offset(pts, d):
    """Polyline moved sideways by d mm (to the left of the direction of travel for d > 0), mitred."""
    out = []
    for k in range(len(pts)):
        if k == 0:
            u = _unit(pts[0], pts[1])
            n = (-u[1], u[0])
            den = 1.0
        elif k == len(pts) - 1:
            u = _unit(pts[-2], pts[-1])
            n = (-u[1], u[0])
            den = 1.0
        else:
            u1, u2 = _unit(pts[k - 1], pts[k]), _unit(pts[k], pts[k + 1])
            n = (-u1[1] - u2[1], u1[0] + u2[0])
            den = max(0.3, 1 + u1[0] * u2[0] + u1[1] * u2[1])
        out.append((pts[k][0] + d * n[0] / den, pts[k][1] + d * n[1] / den))
    return out


def _cross(a, b, c, d):
    """Do the segments a-b and c-d cross?"""
    def z(p_, q_, r_):
        return (q_[0] - p_[0]) * (r_[1] - p_[1]) - (q_[1] - p_[1]) * (r_[0] - p_[0])
    return z(a, b, c) * z(a, b, d) < 0 and z(c, d, a) * z(c, d, b) < 0


def pair_partner(name, names):
    """Name of the N net that goes with this P net, or None."""
    if name.endswith("_DP") and name[:-1] + "M" in names:
        return name[:-1] + "M"
    for k in range(len(name) - 1, -1, -1):
        if name[k] == "P":
            cand = name[:k] + "N" + name[k + 1:]
            if cand in names:
                return cand
    return None


def _path(par, s):
    out = [s]
    while s in par:
        s = par[s]
        out.append(s)
    out.reverse()
    return out


# --------------------------------------------------------------------------
class Router:
    def __init__(self, board):
        self.board = board
        self.regs = [Region(*r) for r in REGIONS]
        self.rc_of = {}
        self.name_of = {}
        self.cls_of = {}
        for name, ni in board.GetNetsByName().items():
            code = ni.GetNetCode()
            cname = ni.GetNetClassName()
            self.name_of[code] = str(name)
            self.cls_of[code] = cname
            self.rc_of[code] = RCS.get(cname, RCS["Default"])
        self.stats = dict(tracks=0, vias=0, length=0.0)
        self.log = []
        self.failed = []
        self.items = []
        self.pairs = []             # (region, P net, N net, (length P, length N, vias) or None)
        self.trunk_node = {}        # net -> node of the trunk drawn last
        self.quick = False          # give up sooner on an island that cannot be reached
        self.cross = {}             # nets that leave the strip window for the column (set by run())
        self.only = None            # fnmatch pattern: route these nets only (and no plane fan-out)
        self.bga = False            # allow vias between / in the pads of BGA packages

    # ---- obstacles ----
    def build(self):
        pts = outline_pts()
        for reg in self.regs:
            t0 = time.time()
            ins = raster_outline(reg, pts)
            out = ~ins
            for k, D in reg.D.items():
                D[:, dilate(out, EDGE + k)] = MULTI
            npads = 0
            lanes = []
            for fp in self.board.GetFootprints():
                bb = fp.GetBoundingBox(False)
                if (ToMM(bb.GetRight()) - OX < reg.x0 - 1 or ToMM(bb.GetLeft()) - OX > reg.x1 + 1 or
                        ToMM(bb.GetBottom()) - OY < reg.y0 - 1 or ToMM(bb.GetTop()) - OY > reg.y1 + 1):
                    continue
                for z in fp.Zones():                # keep-out areas drawn in the footprint (e.g. under a connector's shell)
                    if not z.GetIsRuleArea():
                        continue
                    zb = z.GetBoundingBox()
                    i0 = max(0, int((ToMM(zb.GetLeft()) - OX - reg.x0) / G))
                    j0 = max(0, int((ToMM(zb.GetTop()) - OY - reg.y0) / G))
                    i1 = min(reg.nx - 1, ceil_((ToMM(zb.GetRight()) - OX - reg.x0) / G))
                    j1 = min(reg.ny - 1, ceil_((ToMM(zb.GetBottom()) - OY - reg.y0) / G))
                    if i0 > i1 or j0 > j1:
                        continue
                    for l, layer in enumerate(RLAYERS):
                        if z.IsOnLayer(layer) and z.GetDoNotAllowTracks():
                            reg.stamp(l, i0, j0, np.ones((j1 - j0 + 1, i1 - i0 + 1), bool), MULTI)
                    if z.GetDoNotAllowVias():
                        kz = ceil_(0.35 / G)
                        reg.novia[max(0, j0 - kz):j1 + kz + 1, max(0, i0 - kz):i1 + kz + 1] = True
                tight = set()                       # balls of a BGA that are too close to another ball for a via in the pad
                if fp.GetPadCount() >= 100:
                    cs_ = [(p_.GetPosition().x, p_.GetPosition().y, p_.GetNumber()) for p_ in fp.Pads()]
                    cs_.sort()
                    lim = FromMM(0.3995)                # hole 0.15 + 0.20 to the next pad (0.25 mm): centres 0.40 mm apart
                    for a_ in range(len(cs_)):
                        for b_ in range(a_ + 1, len(cs_)):
                            if cs_[b_][0] - cs_[a_][0] >= lim:
                                break
                            if (cs_[b_][0] - cs_[a_][0]) ** 2 + (cs_[b_][1] - cs_[a_][1]) ** 2 < lim * lim:
                                tight.add(cs_[a_][2])
                                tight.add(cs_[b_][2])
                sig = [p for p in fp.Pads() if p.GetNetCode() > 0 or not p.HasHole()]
                fx = sum(ToMM(p.GetPosition().x) for p in sig) / max(1, len(sig)) - OX
                fy = sum(ToMM(p.GetPosition().y) for p in sig) / max(1, len(sig)) - OY
                for pad in fp.Pads():
                    layers = [n for n, l in enumerate(RLAYERS) if pad.IsOnLayer(l)]
                    cx, cy = ToMM(pad.GetPosition().x) - OX, ToMM(pad.GetPosition().y) - OY
                    if not layers or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:      # keep copper off the hole on every layer
                        if pad.HasHole():
                            rr = ceil_((max(ToMM(pad.GetDrillSize().x), ToMM(pad.GetDrillSize().y)) / 2 + 0.30) / G)
                            i, j = int(round((cx - reg.x0) / G)), int(round((cy - reg.y0) / G))
                            if -rr <= i < reg.nx + rr and -rr <= j < reg.ny + rr:
                                for l in range(3):
                                    reg.stamp(l, i - rr, j - rr, disc(rr), MULTI)
                        continue
                    pm = pad_mask(reg, pad)
                    if pm is None:
                        continue
                    i0, j0, m = pm
                    code = pad.GetNetCode()
                    net = code if code > 0 else MULTI
                    grow = self.rc_of[code].extra if code > 0 and self.cls_of[code] in RCS else 0
                    if code > 0 and self.cls_of[code] not in RCS:
                        cl = CLS.get(self.cls_of[code], CLS["Default"])["clearance"]
                        grow = ceil_((cl - BASE_CL) / G) if cl > BASE_CL + 1e-9 else 0
                    mm = m
                    if grow:
                        big = np.zeros((m.shape[0] + 2 * grow, m.shape[1] + 2 * grow), bool)
                        big[grow:-grow, grow:-grow] = m
                        mm = dilate(big, grow)
                    if K_HOLE is not None and fp.GetPadCount() >= 100:
                        m1 = np.zeros((m.shape[0] + 2, m.shape[1] + 2), bool)
                        m1[1:-1, 1:-1] = m
                        m1 = ~dilate(~m1, 1)                    # the pad itself, one cell smaller (whatever its class)
                        for l in layers:
                            reg.stamp(l, i0 - grow, j0 - grow, mm, net, skip=HOLE_KS)
                            reg.stamp(l, i0 - 1, j0 - 1, m1, net, only=HOLE_KS)
                    else:
                        for l in layers:
                            reg.stamp(l, i0 - grow, j0 - grow, mm, net)
                    k = 0 if (self.bga and fp.GetPadCount() >= 100) else K_NOVIA      # BGA: via-in-pad and dog-bones are the only way out
                    if VIA_KIND and layers == [0]:  # a blind via from B.Cu never reaches a top-face pad
                        k = 0
                    big = np.zeros((m.shape[0] + 2 * k, m.shape[1] + 2 * k), bool)
                    big[k:k + m.shape[0], k:k + m.shape[1]] = m
                    big = dilate(big, k) if k else np.zeros_like(big)
                    ia, ja = max(i0 - k, 0), max(j0 - k, 0)
                    ib, jb = min(i0 - k + big.shape[1], reg.nx), min(j0 - k + big.shape[0], reg.ny)
                    reg.novia[ja:jb, ia:ib] |= big[ja - (j0 - k):jb - (j0 - k), ia - (i0 - k):ib - (i0 - k)]
                    npads += 1
                    nlane = len(lanes)
                    if code > 0 and len(sig) >= 5 and len(layers) == 1:
                        bb = pad.GetBoundingBox()
                        xa, ya, xb, yb = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
                        w_, h_ = xb - xa, yb - ya
                        # the lane leaves the pad away from the part's middle - unless that way is off the board
                        # (a connector's row of pads along the board edge): then it leaves towards the middle
                        def on_board(x_, y_):
                            i_, j_ = int(round((x_ - reg.x0) / G)), int(round((y_ - reg.y0) / G))
                            return 0 <= i_ < reg.nx and 0 <= j_ < reg.ny and bool(ins[j_, i_])
                        if h_ >= 1.4 * w_ and abs(cy - fy) > 0.3 and w_ <= 0.9:
                            dn = cy > fy
                            if not on_board(cx, (yb + LANE + 0.4) if dn else (ya - LANE - 0.4)):
                                dn = not dn
                            lanes.append((layers[0], code, xa, yb if dn else ya - LANE, xb, yb + LANE if dn else ya, 0, 1 if dn else -1))
                        elif w_ >= 1.4 * h_ and abs(cx - fx) > 0.3 and h_ <= 0.9:
                            rt = cx > fx
                            if not on_board((xb + LANE + 0.4) if rt else (xa - LANE - 0.4), cy):
                                rt = not rt
                            lanes.append((layers[0], code, xb if rt else xa - LANE, ya, xb + LANE if rt else xa, yb, 1 if rt else -1, 0))
                    inside = reg.x0 + 0.2 <= cx <= reg.x1 - 0.2 and reg.y0 + 0.2 <= cy <= reg.y1 - 0.2
                    if code > 0 and inside:
                        js, is_ = np.nonzero(m)
                        cells = [(l, i0 + int(i), j0 + int(j)) for l in layers for i, j in zip(is_, js)]
                        ux, uy = lanes[-1][6:8] if len(lanes) > nlane else (0, 0)       # which way a fine-pitch pad is left
                        lst = reg.pads.setdefault(code, [])
                        lst.append(dict(
                            pad=pad, ref=fp.GetReference(), num=pad.GetNumber(), cells=cells, cx=cx, cy=cy, layers=layers,
                            tht=pad.HasHole(), area=ToMM(pad.GetSize().x) * ToMM(pad.GetSize().y),
                            minw=min(ToMM(pad.GetSize().x), ToMM(pad.GetSize().y)),
                            node=reg.node(), ex=cx + 1.3 * ux, ey=cy + 1.3 * uy, bga=fp.GetPadCount() >= 100,
                            via_ok=pad.GetNumber() not in tight))
                        pc = reg.padcell.setdefault(code, {})
                        for c in cells:
                            if c in pc:                         # two pads of one net on top of each other: one island
                                reg.union(lst[pc[c]]["node"], lst[-1]["node"])
                            pc[c] = len(lst) - 1
            # exit lanes: a strip straight out of each pad that only its own net may use; where two lanes of
            # different nets meet, or a lane would touch another pad, nobody gets it
            owner = np.full((3, reg.ny, reg.nx), FREE, np.int16)
            boxes = []
            for l, code, xa, ya, xb, yb, ux, uy in lanes:
                ex = SOFT_LEN - LANE                                 # soft zone = the lane, widened and extended outwards
                sa, sc = (xa - 0.1, xb + 0.1) if ux == 0 else ((xa, xb + ex) if ux > 0 else (xa - ex, xb))
                sb, sd = (ya - 0.1, yb + 0.1) if uy == 0 else ((ya, yb + ex) if uy > 0 else (ya - ex, yb))
                si0, sj0 = max(0, ceil_((sa - reg.x0) / G)), max(0, ceil_((sb - reg.y0) / G))
                si1, sj1 = min(reg.nx - 1, int((sc - reg.x0) / G)), min(reg.ny - 1, int((sd - reg.y0) / G))
                if si0 <= si1 and sj0 <= sj1:
                    v = reg.soft[l, sj0:sj1 + 1, si0:si1 + 1]
                    other = (v != FREE) & (v != code)
                    v[v == FREE] = code
                    v[other] = MULTI
                i0, j0 = max(0, ceil_((xa - reg.x0) / G)), max(0, ceil_((ya - reg.y0) / G))
                i1, j1 = min(reg.nx - 1, int((xb - reg.x0) / G + 1e-9)), min(reg.ny - 1, int((yb - reg.y0) / G + 1e-9))
                if i0 > i1 or j0 > j1:
                    continue
                v = owner[l, j0:j1 + 1, i0:i1 + 1]
                other = (v != FREE) & (v != code)
                v[v == FREE] = code
                v[other] = MULTI
                boxes.append((l, code, i0, j0, i1, j1))
            for l, code, i0, j0, i1, j1 in boxes:
                m = (owner[l, j0:j1 + 1, i0:i1 + 1] == code) & ~reg.novia[j0:j1 + 1, i0:i1 + 1]
                if m.any():
                    reg.stamp(l, i0, j0, m, code)
            del owner
            if not STRIP and reg.x0 < HEAD_BOX[2] and reg.x1 > HEAD_BOX[0] and reg.y0 < HEAD_BOX[3]:
                i0, i1 = max(0, ceil_((HEAD_BOX[0] - reg.x0) / G)), min(reg.nx - 1, int((HEAD_BOX[2] - reg.x0) / G))
                j0, j1 = max(0, ceil_((HEAD_BOX[1] - reg.y0) / G)), min(reg.ny - 1, int((HEAD_BOX[3] - reg.y0) / G))
                for D in reg.D.values():
                    D[:, j0:j1 + 1, i0:i1 + 1] = MULTI
                for code in list(reg.pads):
                    keep = [pd for pd in reg.pads[code] if not (pd["cx"] >= HEAD_BOX[0] and pd["cy"] <= HEAD_BOX[3])]
                    if len(keep) != len(reg.pads[code]):
                        for pd in reg.pads[code]:
                            if pd not in keep:
                                for c in pd["cells"]:
                                    reg.padcell[code].pop(c, None)
                        reg.pads[code] = keep
                        reg.padcell[code] = {c: n for n, pd in enumerate(keep) for c in pd["cells"]}
                        if not keep:
                            del reg.pads[code]
            nold = self.import_copper(reg)
            self.log.append(f"region {reg.name}: {reg.nx} x {reg.ny} cells, {npads} pads rasterised, {len(boxes)} exit lanes, "
                            f"{nold} tracks and vias already there, in {time.time() - t0:.1f} s")
            print(self.log[-1], flush=True)

    def import_copper(self, reg):
        """Tracks and vias that are already on the board (earlier regions, earlier stages): obstacles for the other
        nets, and for their own net something to connect to.  Loose track ends are remembered as 'tips'."""
        ends, cover, segs, viapos = {}, {}, [], set()
        count = 0
        for t in self.board.GetTracks():
            code = t.GetNetCode()
            if code <= 0:
                continue
            extra = self.rc_of[code].extra
            if t.GetClass() == "PCB_VIA":
                x, y = ToMM(t.GetPosition().x) - OX, ToMM(t.GetPosition().y) - OY
                if not (reg.x0 - 1 <= x <= reg.x1 + 1 and reg.y0 - 1 <= y <= reg.y1 + 1):
                    continue
                fi, fj = (x - reg.x0) / G, (y - reg.y0) / G
                i, j = int(round(fi)), int(round(fj))
                exact_ = not (abs(fi - i) < 1e-3 and abs(fj - j) < 1e-3)
                tol_ = 0.26 if G < 0.05 - 1e-9 else 1e-3        # (on the fine grid a quarter cell off counts as on the grid)
                off = 0 if abs(fi - i) < tol_ and abs(fj - j) < tol_ else 1
                try:
                    d = ToMM(t.GetWidth(pcbnew.F_Cu))
                except TypeError:
                    d = ToMM(t.GetWidth())
                r = max(0, ceil_((d / 2 - TOL) / G)) + extra + off
                reg.stamp_via(i, j, r, max(0, hole_extra(d, ToMM(t.GetDrillValue())) - extra), code, via_d=d if not off else None)
                k = min(K_VIAVIA, ceil_((ToMM(t.GetDrillValue()) + 0.25) / G) - 1) + off
                ia, ja, ib, jb = max(i - k, 0), max(j - k, 0), min(i + k + 1, reg.nx), min(j + k + 1, reg.ny)
                if ia < ib and ja < jb:
                    reg.novia[ja:jb, ia:ib] = True
                if 0 <= i < reg.nx and 0 <= j < reg.ny:
                    reg.assign(code, [(l, i, j) for l in range(3)], reg.node())
                    viapos.add((code, i, j))
                    if exact_:
                        for l in range(3):
                            reg.exact.setdefault(code, {})[(l, i, j)] = (x, y)
                count += 1
                continue
            a = (ToMM(t.GetStart().x) - OX, ToMM(t.GetStart().y) - OY)
            b = (ToMM(t.GetEnd().x) - OX, ToMM(t.GetEnd().y) - OY)
            if (max(a[0], b[0]) < reg.x0 - 1 or min(a[0], b[0]) > reg.x1 + 1 or
                    max(a[1], b[1]) < reg.y0 - 1 or min(a[1], b[1]) > reg.y1 + 1):
                continue
            cells, on = reg.seg_cells(a, b)
            if not cells:
                continue
            if t.GetLayer() not in RLAYERS:
                # (the signal layer In2 while the supply nets are routed on In3, and the other way round)
                kv = ceil_((ToMM(t.GetWidth()) / 2 + 0.15 + (0.125 if self.bga else 0.40)) / G) + 1
                for n_ in range(0, len(cells), 48):
                    ch = cells[n_:n_ + 49]
                    ia, ja = min(c[0] for c in ch) - kv, min(c[1] for c in ch) - kv
                    m = np.zeros((max(c[1] for c in ch) + kv - ja + 1, max(c[0] for c in ch) + kv - ia + 1), bool)
                    for i_, j_ in ch:
                        m[j_ - ja, i_ - ia] = True
                    m = dilate(m, kv)
                    xa, ya = max(ia, 0), max(ja, 0)
                    xb, yb = min(ia + m.shape[1], reg.nx), min(ja + m.shape[0], reg.ny)
                    if xa < xb and ya < yb:
                        reg.novia[ya:yb, xa:xb] |= m[ya - ja:yb - ja, xa - ia:xb - ia]
                count += 1
                continue
            l = RLAYERS.index(t.GetLayer())
            c3 = [(l, i, j) for i, j in cells]
            pc = reg.padcell.get(code, {})
            if on or not all(c in pc for c in c3):              # (a stub inside its own pad adds nothing)
                reg.stamp_cells(l, cells, max(0, ceil_((ToMM(t.GetWidth()) / 2 - TOL) / G)) + extra + (0 if on else 1), code)
            reg.assign(code, c3, reg.node())
            for c in c3:
                cover[(code, c)] = cover.get((code, c), 0) + 1
            segs.append((code, l, a, b))
            count += 1
        for code, l, a, b in segs:
            for e in (a, b):
                fi, fj = (e[0] - reg.x0) / G, (e[1] - reg.y0) / G
                c = (l, int(round(fi)), int(round(fj)))
                if not (0 <= c[1] < reg.nx and 0 <= c[2] < reg.ny) or c in reg.padcell.get(code, {}):
                    continue
                if abs(fi - c[1]) > 1e-3 or abs(fj - c[2]) > 1e-3:
                    reg.exact.setdefault(code, {}).setdefault(c, e)
                if cover.get((code, c), 0) == 1 and (code, c[1], c[2]) not in viapos:
                    reg.tips.setdefault(code, []).append((l, e[0], e[1]))
        return count

    # ---- output ----
    def add_track(self, reg, net, l, a, b, w):
        if a == b:
            return
        self.items.append(("t", net, l, a, b, w))

    def add_via(self, reg, net, i, j, rc, node=None):
        self.items.append(("v", net, reg.xy(i, j), rc.via_d, rc.via_drill))
        reg.stamp_via(i, j, rc.mv, rc.hx, net, via_d=rc.via_d)
        k = min(K_VIAVIA, ceil_((rc.via_drill + 0.25) / G) - 1)       # hole-to-hole 0.25 mm
        ia, ja, ib, jb = max(i - k, 0), max(j - k, 0), min(i + k + 1, reg.nx), min(j + k + 1, reg.ny)
        reg.novia[ja:jb, ia:ib] = True          # no second via on top of / touching this one
        reg.assign(net, [(l, i, j) for l in range(3)], reg.node() if node is None else node)

    def via_at(self, reg, net, i, j, rc, node, layers=()):
        """A via at a grid cell - or, if that cell lies in a BGA pad of the net, exactly on the pad's centre (a hole
        off the centre would come too close to the next ball), with the tracks on 'layers' led to it."""
        pc = reg.padcell.get(net)
        if pc:
            for l in range(3):
                n = pc.get((l, i, j))
                if n is not None and reg.pads[net][n].get("bga"):
                    pd = reg.pads[net][n]
                    xy = (pd["cx"], pd["cy"])
                    self.add_via_xy(reg, net, xy, rc, node)
                    for l2 in layers:
                        self.add_track(reg, net, l2, reg.xy(i, j), xy, rc.w)
                    return
        self.add_via(reg, net, i, j, rc, node)

    def add_via_xy(self, reg, net, xy, rc, node):
        """A via that is not on the grid (the two vias of a pair)."""
        self.items.append(("v", net, xy, rc.via_d, rc.via_drill))
        i, j = int(round((xy[0] - reg.x0) / G)), int(round((xy[1] - reg.y0) / G))
        tol_ = 0.26 if G < 0.05 - 1e-9 else 1e-3    # (on the fine grid a quarter cell off counts as on the grid: a via in a ball)
        on = abs((xy[0] - reg.x0) / G - i) < tol_ and abs((xy[1] - reg.y0) / G - j) < tol_
        reg.stamp_via(i, j, rc.mv + (0 if on else 1), rc.hx, net, via_d=rc.via_d if on else None)
        k = min(K_VIAVIA, ceil_((rc.via_drill + 0.25) / G) - 1) + 1
        ia, ja, ib, jb = max(i - k, 0), max(j - k, 0), min(i + k + 1, reg.nx), min(j + k + 1, reg.ny)
        reg.novia[ja:jb, ia:ib] = True
        reg.assign(net, [(l, i, j) for l in range(3)], node)
        for l in range(3):
            reg.exact.setdefault(net, {})[(l, i, j)] = xy

    def flush(self, items):
        """Write the tracks and vias of the chosen pass to the board."""
        for it in items:
            ni = self.board.FindNet(self.name_of[it[1]])
            if it[0] == "t":
                _, net, l, a, b, w = it
                t = pcbnew.PCB_TRACK(self.board)
                t.SetStart(P(*a))
                t.SetEnd(P(*b))
                t.SetWidth(FromMM(w))
                t.SetLayer(RLAYERS[l])
                t.SetNet(ni)
                self.board.Add(t)
                self.stats["tracks"] += 1
                self.stats["length"] += math.hypot(a[0] - b[0], a[1] - b[1])
            else:
                _, net, xy, d, drill = it
                v = pcbnew.PCB_VIA(self.board)
                v.SetViaType(VIA_KIND[0] if VIA_KIND else pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(*(VIA_KIND[1:] if VIA_KIND else (pcbnew.F_Cu, pcbnew.B_Cu)))
                v.SetPosition(P(*xy))
                v.SetDrill(FromMM(drill))
                try:
                    v.SetWidth(pcbnew.F_Cu, FromMM(d))
                except TypeError:
                    v.SetWidth(FromMM(d))
                v.SetNet(ni)
                self.board.Add(v)
                self.stats["vias"] += 1

    def commit(self, reg, net, rc, states, W, H, i0, j0, via_at_end=False):
        """Turn a state path into tracks / vias, mark it as copper, add it to the net's tree."""
        WH = W * H
        cells = []
        for s in states:
            l, r = divmod(s, WH)
            y, x = divmod(r, W)
            cells.append((l, i0 + x, j0 + y))
        nd = reg.node()
        run = [cells[0]]
        runs = []
        for c in cells[1:]:
            if c[0] != run[-1][0]:
                self.via_at(reg, net, c[1], c[2], rc, nd, (run[-1][0], c[0]))
                runs.append(run)
                run = [c]
            else:
                run.append(c)
        runs.append(run)
        for run in runs:
            l = run[0][0]
            ij = [(c[1], c[2]) for c in run]
            reg.stamp_cells(l, ij, rc.mt, net)
            a = 0
            for n in range(1, len(ij)):
                last = n == len(ij) - 1
                if not last:
                    d1 = (ij[n][0] - ij[n - 1][0], ij[n][1] - ij[n - 1][1])
                    d2 = (ij[n + 1][0] - ij[n][0], ij[n + 1][1] - ij[n][1])
                    if d1 == d2:
                        continue
                self.add_track(reg, net, l, reg.xy(*ij[a]), reg.xy(*ij[n]), rc.w)
                a = n
        ex = reg.exact.get(net)
        if ex:                                  # the copper this path starts or ends on is not on the grid there
            for c in (cells[0], cells[-1]):
                if c in ex:
                    self.add_track(reg, net, c[0], reg.xy(c[1], c[2]), ex[c], rc.w)
        for run in runs:
            reg.assign(net, run, nd)
        if via_at_end:
            l, i, j = cells[-1]
            self.via_at(reg, net, i, j, rc, nd, (l,) if len(cells) > 1 else ())
        return cells

    def stub(self, reg, net, rc, cell, pd):
        """Short segment from a path end inside a pad to the pad centre, so the connection is unambiguous."""
        l, i, j = cell
        w = min(rc.w, 0.15) if pd["area"] < 0.12 else rc.w
        self.add_track(reg, net, l, reg.xy(i, j), (pd["cx"], pd["cy"]), max(0.09, min(w, pd.get("minw", w))))

    def window(self, reg, net, rc, box, margin):
        i0 = max(0, int((box[0] - reg.x0) / G) - margin)
        j0 = max(0, int((box[1] - reg.y0) / G) - margin)
        i1 = min(reg.nx - 1, int((box[2] - reg.x0) / G) + margin)
        j1 = min(reg.ny - 1, int((box[3] - reg.y0) / G) + margin)
        W, H = i1 - i0 + 1, j1 - j0 + 1
        Dk = reg.D[rc.Kt][:, j0:j1 + 1, i0:i1 + 1]
        ok = (Dk == FREE) | (Dk == net)
        if reg.pri is not None:             # the isolation barrier is not negotiable
            ok &= (reg.pri if self.is_line(net) else ~reg.nopri)[:, j0:j1 + 1, i0:i1 + 1]
        Dv = reg.D[rc.Kv][:, j0:j1 + 1, i0:i1 + 1]
        vok = ((Dv == FREE) | (Dv == net))[VIA_L].all(axis=0) & ~reg.novia[j0:j1 + 1, i0:i1 + 1] & ok[VIA_L].all(axis=0)
        if K_HOLE is not None and rc.hx:    # a small via: its hole, too, must be clear of what is already there
            Dh = reg.D[K_HOLE][:, j0:j1 + 1, i0:i1 + 1]
            vok &= ((Dh == FREE) | (Dh == net))[VIA_L].all(axis=0)
            # In a ball of its own net it may sit (the balls are marked one cell small in that map, so the next ball,
            # exactly 0.4 mm away, does not count) - unless another ball is closer than that.  Anywhere else it needs
            # the full distance, judged in a map where nothing is marked small.
            good = np.zeros((H, W), bool)
            bad = np.zeros((H, W), bool)
            for pd in reg.pads.get(net, ()):
                if pd.get("bga"):
                    m_ = good if pd.get("via_ok") else bad
                    for c in pd["cells"]:
                        if i0 <= c[1] <= i1 and j0 <= c[2] <= j1:
                            m_[c[2] - j0, c[1] - i0] = True
            Ds = reg.D[K_HOLE + 1][:, j0:j1 + 1, i0:i1 + 1]
            vok &= (good | ((Ds == FREE) | (Ds == net))[VIA_L].all(axis=0)) & ~bad
        S = reg.soft[:, j0:j1 + 1, i0:i1 + 1]
        self.pen = [((S[l] != FREE) & (S[l] != net)).tobytes() for l in range(3)]
        return i0, j0, W, H, ok, vok

    # ---- a signal / power net: join everything of it that sits in this region ----
    def is_line(self, net):
        """PoE primary, or (in the Ethernet head run) the line side of the magnetics: kept inside PRIMARY_AREA."""
        return self.cls_of[net] == "POE_PRIMARY" or (HEAD and any(fnmatch.fnmatch(self.name_of[net], p_) for p_ in LINE_NETS))

    def groups(self, reg, net):
        """The islands of a net: {root: (pad indices, centre-line cells)}."""
        g = {}
        for n, pd in enumerate(reg.pads.get(net, [])):
            g.setdefault(reg.find(pd["node"]), ([], []))[0].append(n)
        for c, nd in reg.tree.get(net, {}).items():
            g.setdefault(reg.find(nd), ([], []))[1].append(c)
        return g

    def route_net(self, reg, net):
        """Joins the islands of a net.  Each step takes the two islands that are closest and searches from one of them
        to ALL the others; an island that cannot get out is set aside (others may still reach it)."""
        rc = self.rc_of[net]
        pads = reg.pads.get(net, [])
        pc = reg.padcell.get(net, {})
        dead = {}                # root -> why it could not be joined
        tries = [(rc0, int(m_ * SCALE), int(e_ * SCALE * SCALE)) for m_, e_ in (((80, 30000),) if self.quick else ((60, 40000), (300, 200000)))
                 for rc0 in ([rc] + ([THIN[rc.name]] if rc.name in THIN else []))]
        while True:
            g = self.groups(reg, net)
            if len(g) < 2:
                break
            pts = {}
            for r, (pn, cs) in g.items():
                pts[r] = [(pads[n]["cx"], pads[n]["cy"]) for n in pn] + [reg.xy(c[1], c[2]) for c in cs[::max(1, len(cs) // 40)]]
            best = None
            roots = list(g)
            for ka in range(len(roots)):
                for kb in range(ka + 1, len(roots)):
                    ra, rb = roots[ka], roots[kb]
                    if ra in dead and rb in dead:
                        continue
                    for p1 in pts[ra]:
                        for p2 in pts[rb]:
                            d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
                            if best is None or d < best[0]:
                                best = (d, ra, rb, p1, p2)
            if best is None:
                break
            _, ra, rb, pa, pb = best
            if ra in dead or (rb not in dead and len(g[rb][0]) * 1000 + len(g[rb][1]) < len(g[ra][0]) * 1000 + len(g[ra][1])):
                ra, rb, pa, pb = rb, ra, pb, pa             # search from the smaller island (never from one that is set aside)
            cells_a = [c for n in g[ra][0] for c in pads[n]["cells"]] + g[ra][1]
            res = None
            why = "no free cell on it"
            far = int(math.hypot(pa[0] - pb[0], pa[1] - pb[1]) / G) * (60 if self.quick else 400)      # a long gap may search longer
            for rc_use, margin, max_exp in [(a_, b_, max(c_, far)) for a_, b_, c_ in tries]:
                box = (min(pa[0], pb[0]), min(pa[1], pb[1]), max(pa[0], pb[0]), max(pa[1], pb[1]))
                i0, j0, W, H, ok, vok = self.window(reg, net, rc_use, box, margin)
                goal = np.zeros((3, H, W), bool)
                for r in roots:
                    if r == ra:
                        continue
                    for n in g[r][0]:
                        for c in pads[n]["cells"]:
                            if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                                goal[c[0], c[2] - j0, c[1] - i0] = True
                    for c in g[r][1]:
                        if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                            goal[c[0], c[2] - j0, c[1] - i0] = True
                goal &= ok
                starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in cells_a
                          if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
                if not starts or not goal.any():
                    why = "hemmed in by neighbouring copper" if not starts else "target copper hemmed in"
                    continue
                gl, gy, gx = np.nonzero(goal)
                gbox = (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max()))
                okb = [ok[l].tobytes() for l in range(3)]
                res, _ = search(okb, vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts, gbox, max_exp=max_exp, penb=self.pen)
                if res:
                    break
                why = "no path found"
            if not res:
                pn, cs = g[ra]
                dead[ra] = ((f'{pads[pn[0]]["ref"]}.{pads[pn[0]]["num"]}' if pn else "the copper at %.1f, %.1f" % reg.xy(cs[0][1], cs[0][2])) + f" ({why})")
                continue
            cells = self.commit(reg, net, rc_use, res, W, H, i0, j0)
            for c in (cells[0], cells[-1]):
                n = pc.get(c)
                if n is not None:
                    self.stub(reg, net, rc_use, c, pads[n])
            if len(self.groups(reg, net)) >= len(g):         # (cannot happen; if it does, do not loop on it)
                dead[ra] = "an island that a new track did not join"
                continue
            for r in roots:                                  # whatever this path touched is worth another try
                if reg.find(r) == reg.find(ra):
                    dead.pop(r, None)
        g2 = self.groups(reg, net)
        ok_pads = max((len(v[0]) for v in g2.values()), default=0)
        left = {}
        for r, why in dead.items():                          # one line per island that is still apart
            left.setdefault(reg.find(r), why)
        if len(g2) > 1:
            big = max(g2, key=lambda r: (len(g2[r][0]), len(g2[r][1])))
            left.pop(big, None)
        return ok_pads, (list(left.values()) if len(g2) > 1 else [])

    def join(self, reg, net, pd, node):
        """A track from one pad to the island that 'node' belongs to.  True if it was drawn."""
        rc = self.rc_of[net]
        root = reg.find(node)
        if reg.find(pd["node"]) == root:
            return True
        cs = [c for c, nd in reg.tree.get(net, {}).items() if reg.find(nd) == root]
        if not cs:
            return False
        xs, ys = [reg.x0 + c[1] * G for c in cs] + [pd["cx"]], [reg.y0 + c[2] * G for c in cs] + [pd["cy"]]
        i0, j0, W, H, ok, vok = self.window(reg, net, rc, (min(xs), min(ys), max(xs), max(ys)), int(40 * SCALE))
        goal = np.zeros((3, H, W), bool)
        for c in cs:
            if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                goal[c[0], c[2] - j0, c[1] - i0] = True
        goal &= ok
        starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in pd["cells"]
                  if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
        if not starts or not goal.any():
            return False
        gl, gy, gx = np.nonzero(goal)
        res, _ = search([ok[l].tobytes() for l in range(3)], vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts,
                        (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max())), max_exp=int(60000 * SCALE * SCALE), penb=self.pen)
        if not res:
            return False
        cells = self.commit(reg, net, rc, res, W, H, i0, j0)
        self.stub(reg, net, rc, cells[0], pd)
        return True

    def fan_out_pairs(self, reg, pnames):
        """Every pair that starts on a big fine-pitch IC (a hub) gets a short coupled stub straight out of its two
        pins, ending on a ring around the IC - all of them before any long trunk is routed, so that no pair is walled
        in by its neighbours.  The trunks then start from the ends of these stubs."""
        made = 0
        for fp in self.board.GetFootprints():
            if not 40 <= fp.GetPadCount() < 100:
                continue
            ref = fp.GetReference()
            mine = {}
            for code, lst in reg.pads.items():
                for pd in lst:
                    if pd["ref"] == ref and len(pd["layers"]) == 1:
                        mine.setdefault(code, []).append(pd)
            if not mine:
                continue
            xs = [pd["cx"] for lst in mine.values() for pd in lst]
            ys = [pd["cy"] for lst in mine.values() for pd in lst]
            layer = next(iter(mine.values()))[0]["layers"][0]
            ring = np.zeros((3, reg.ny, reg.nx), bool)

            def box(m):
                return (max(0, int((min(xs) - m - reg.x0) / G)), max(0, int((min(ys) - m - reg.y0) / G)),
                        min(reg.nx - 1, ceil_((max(xs) + m - reg.x0) / G)), min(reg.ny - 1, ceil_((max(ys) + m - reg.y0) / G)))
            a, b = box(PAIR_RIM + 0.3), box(PAIR_RIM)
            ring[layer, a[1]:a[3] + 1, a[0]:a[2] + 1] = True
            ring[layer, b[1]:b[3] + 1, b[0]:b[2] + 1] = False
            todo = []
            pnames = {self.name_of[c]: c for c in mine if self.cls_of[c] in PAIR_CLASSES}
            for code, lst in mine.items():
                name = self.name_of[code]
                other = pair_partner(name, pnames) if name in pnames else None
                if other is None:
                    continue
                led = {reg.find(nd) for nd in reg.tree.get(code, {}).values()}
                for pd in lst:
                    if reg.find(pd["node"]) in led:
                        continue                            # (an earlier stage has been here)
                    qd = min(mine[pnames[other]], key=lambda q: math.hypot(q["cx"] - pd["cx"], q["cy"] - pd["cy"]))
                    if math.hypot(qd["cx"] - pd["cx"], qd["cy"] - pd["cy"]) <= 1.5:
                        todo.append((math.atan2(pd["cy"] - sum(ys) / len(ys), pd["cx"] - sum(xs) / len(xs)), name, code, pnames[other], pd, qd))
            for _, name, cp, cn, pd, qd in sorted(todo, key=lambda t_: t_[:2]):
                tr = self.route_pair(reg, cp, cn, zone=ring, zone_layers={layer}, stub=True)
                if not tr:
                    if os.environ.get("CP_VERBOSE"):
                        print("   fan-out %s %-18s none: %s" % (ref, name, self.pair_why), flush=True)
                    continue
                okp = self.join(reg, cp, pd, self.trunk_node[cp])
                okn = self.join(reg, cn, qd, self.trunk_node[cn])
                made += 1
                if os.environ.get("CP_VERBOSE"):
                    print("   fan-out %s %-18s %s" % (ref, name, "ok" if okp and okn else "stub drawn, pin not joined yet"), flush=True)
        return made

    def port_zone(self, reg, pair=False):
        """The line where nets leave the strip window for the column, as a (3, ny, nx) mask."""
        zone = np.zeros((3, reg.ny, reg.nx), bool)
        jl = int(round(((PORT_Y_PAIR if pair else PORT_Y) - reg.y0) / G))
        ia, ib = ceil_((PORT_X[0] - reg.x0) / G), int((PORT_X[1] - reg.x0) / G)
        if 0 <= jl < reg.ny:
            zone[:, jl, max(0, ia):ib + 1] = True
        return zone

    def route_ports(self, reg, names, zone):
        """The strip end of every net that goes on into the column: a pair as a coupled trunk, the others as a track,
        from the strip to the hand-over line.  names: {net name: code}.  Returns (reached, not reached, other failures)."""
        def dist(code):
            return min(abs(p_["cy"] - PORT_Y) + max(0.0, p_["cx"] - PORT_X[1]) for p_ in reg.pads[code])

        zone_pair = self.port_zone(reg, pair=True)

        def there(code):
            return any(zone_pair[c[0], c[2], c[1]] for c in reg.tree.get(code, ()))
        done, ok, bad, other = set(), [], [], []
        order = sorted(names, key=lambda n_: (0 if self.cls_of[names[n_]] in PAIR_CLASSES else 1, dist(names[n_])))
        for name in order:
            code = names[name]
            if code in done:
                continue
            group = [code]
            if self.cls_of[code] in PAIR_CLASSES:
                partner = pair_partner(name, names) or next((o for o in names if pair_partner(o, names) == name), None)
                if partner is not None and names[partner] not in done:
                    pn, nn = (name, partner) if pair_partner(name, names) == partner else (partner, name)
                    group = [names[pn], names[nn]]
                    if not (there(names[pn]) and there(names[nn])):
                        tr = self.route_pair(reg, names[pn], names[nn], zone=zone_pair)
                        self.pairs.append(("ports", pn, nn, tr or self.pair_why))
            for c in group:
                done.add(c)
                okp, fails = self.route_net(reg, c)             # whatever of it sits in the strip, joined (to the trunk, too)
                end = self.route_port(reg, c, zone_pair if len(group) == 2 else zone)
                (ok if end is not None else bad).append(self.name_of[c])
                other += [(self.name_of[c], f) for f in fails]
        return ok, bad, other

    def route_port(self, reg, net, zone, rc=None, pad=None, room=None):
        """From the biggest island of the net (or from one pad) to the nearest free cell of 'zone' (a (3, ny, nx) mask).
        room: clearance map the end cell must be free in (so that the next stage can pick the end up).
        Returns the end cell, or None."""
        rc = rc or self.rc_of[net]
        pads = reg.pads.get(net, [])
        if pad is not None:
            cells_a = list(pad["cells"])
            pts = [(pad["cx"], pad["cy"])]
        else:
            g = self.groups(reg, net)
            if not g:
                return None
            pn, cs = g[max(g, key=lambda r: (len(g[r][0]), len(g[r][1])))]
            cells_a = [c for n in pn for c in pads[n]["cells"]] + cs
            pts = [(pads[n]["cx"], pads[n]["cy"]) for n in pn] + [reg.xy(c[1], c[2]) for c in cs[::max(1, len(cs) // 40)]]
        hit = [c for c in cells_a if zone[c[0], c[2], c[1]]]
        if hit:
            return hit[0]
        zl, zy, zx = np.nonzero(zone)
        if not len(zx):
            return None
        zpts = list(zip(reg.x0 + zx[::max(1, len(zx) // 400)] * G, reg.y0 + zy[::max(1, len(zy) // 400)] * G))
        _, pa, pb = min(((math.hypot(a[0] - b[0], a[1] - b[1]), a, b) for a in pts for b in zpts), key=lambda t_: t_[0])
        res = None
        for rc_use, margin, max_exp in [(rc0, int(m_ * SCALE), e_) for m_, e_ in ((80, 300000), (320, 1500000))
                                        for rc0 in ([rc] + ([THIN[rc.name]] if rc.name in THIN else []))]:
            box = (min(pa[0], pb[0]), min(pa[1], pb[1]), max(pa[0], pb[0]), max(pa[1], pb[1]))
            i0, j0, W, H, ok, vok = self.window(reg, net, rc_use, box, margin)
            goal = zone[:, j0:j0 + H, i0:i0 + W] & ok
            if room is not None:
                Dr = reg.D[room][:, j0:j0 + H, i0:i0 + W]
                goal &= (Dr == FREE) | (Dr == net)
            starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in cells_a
                      if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
            if not starts or not goal.any():
                continue
            gl, gy, gx = np.nonzero(goal)
            gbox = (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max()))
            res, _ = search([ok[l].tobytes() for l in range(3)], vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts, gbox,
                            max_exp=max_exp, penb=self.pen)
            if res:
                break
        if not res:
            return None
        cells = self.commit(reg, net, rc_use, res, W, H, i0, j0)
        n = reg.padcell.get(net, {}).get(cells[0])
        if n is not None:
            self.stub(reg, net, rc_use, cells[0], pads[n])
        return cells[-1]

    # ---- a differential pair: the coupled part ----
    def terminals(self, reg, net):
        """Where a net can be picked up: its pads, and the loose ends of copper that was already there."""
        t = reg.tree.get(net, {})
        tips = []
        for l, x, y in reg.tips.get(net, []):
            c = (l, int(round((x - reg.x0) / G)), int(round((y - reg.y0) / G)))
            if c in t:
                tips.append(dict(x=x, y=y, ex=x, ey=y, layers={l}, node=t[c], tip=True, layer=l))
        led = {reg.find(t_["node"]) for t_ in tips}
        return tips + [dict(x=pd["cx"], y=pd["cy"], ex=pd["ex"], ey=pd["ey"], layers=set(pd["layers"]), node=pd["node"])
                       for pd in reg.pads.get(net, []) if reg.find(pd["node"]) not in led]

    def route_pair(self, reg, p, n, zone=None, zone_layers=None, stub=False):
        """One fat path between the two ends of the pair that are furthest apart, drawn as two parallel tracks with
        spread ends.  Returns (length P, length N, vias per net) or None; the ends are joined by route_net afterwards.
        zone: a (3, ny, nx) mask - the trunk then runs from the pair's end nearest to it into that zone."""
        prc = PAIRS[self.cls_of[p]]
        rc = prc.rc
        tp, tn = self.terminals(reg, p), self.terminals(reg, n)
        cand = sorted((math.hypot(a["x"] - b["x"], a["y"] - b["y"]), ia, ib)
                      for ia, a in enumerate(tp) for ib, b in enumerate(tn))
        gates, ua, ub = [], set(), set()
        for d, ia, ib in cand:
            if d > PAIR_GATE:
                break
            if ia in ua or ib in ub:
                continue
            ua.add(ia)
            ub.add(ib)
            a, b = tp[ia], tn[ib]
            # (two ends on different layers: the trunk may end on either, the other wire changes layer on its last bit)
            gates.append(dict(x=(a["x"] + b["x"]) / 2, y=(a["y"] + b["y"]) / 2, sep=d,
                              layers=(a["layers"] & b["layers"]) or (a["layers"] | b["layers"]), p=a, n=b))
        best = None
        if zone is not None and gates:
            zl, zy, zx = np.nonzero(zone)
            if not len(zx):
                self.pair_why = "no free cell in the target zone"
                return None
            zc = (reg.x0 + float(zx.mean()) * G, reg.y0 + float(zy.mean()) * G)
            g1 = min(gates, key=lambda g_: math.hypot(g_["x"] - zc[0], g_["y"] - zc[1]))
            k_ = int(np.argmin((zx - (g1["x"] - reg.x0) / G) ** 2 + (zy - (g1["y"] - reg.y0) / G) ** 2))
            zn = (reg.x0 + float(zx[k_]) * G, reg.y0 + float(zy[k_]) * G)          # the zone cell nearest to that end
            best = (8.0, g1, dict(x=zn[0], y=zn[1], sep=0.0, layers={0, 1, 2} if zone_layers is None else zone_layers,
                                  zone=True, p=None, n=None))
        near = {}
        for k1 in range(len(gates) if zone is None else 0):
            for k2 in range(k1 + 1, len(gates)):
                g1, g2 = gates[k1], gates[k2]
                c1, c2 = reg.find(g1["p"]["node"]), reg.find(g2["p"]["node"])
                if c1 == c2 or reg.find(g1["n"]["node"]) == reg.find(g2["n"]["node"]):
                    continue
                d = math.hypot(g1["x"] - g2["x"], g1["y"] - g2["y"])
                key = (min(c1, c2), max(c1, c2))
                if key not in near or d < near[key][0]:
                    near[key] = (d, g1, g2)
        for cand_ in near.values():
            if best is None or cand_[0] > best[0]:
                best = cand_
        if best is None or best[0] < 8.0:
            self.pair_why = "ends too close for a trunk" if best else "fewer than two free ends"
            return None
        dist, ga, gb = best
        self.pair_why = "no room at one end"
        t0 = time.time()
        for margin, radius, vias in (((60, 2.1, False),) if stub else ((100, 2.2, True), (320, 3.0, True), (320, 3.0, False))):
            radius = min(radius, dist / 2 - 1.5)
            box = (min(ga["x"], gb["x"]), min(ga["y"], gb["y"]), max(ga["x"], gb["x"]), max(ga["y"], gb["y"]))
            margin = int(margin * SCALE)
            i0 = max(0, int((box[0] - reg.x0) / G) - margin)
            j0 = max(0, int((box[1] - reg.y0) / G) - margin)
            i1 = min(reg.nx - 1, int((box[2] - reg.x0) / G) + margin)
            j1 = min(reg.ny - 1, int((box[3] - reg.y0) / G) + margin)
            ok = reg.D[prc.K][:, j0:j1 + 1, i0:i1 + 1] == FREE
            if reg.pri is not None:
                ok &= ~reg.nopri[:, j0:j1 + 1, i0:i1 + 1]
            vok = ((reg.D[prc.Kv][:, j0:j1 + 1, i0:i1 + 1] == FREE)[VIA_L].all(axis=0) & ok[VIA_L].all(axis=0)
                   & ~dilate(reg.novia[j0:j1 + 1, i0:i1 + 1], ceil_((PAIR_VIA_OFF + 0.05) / G)))
            # the trunk is searched on every second cell (0.1 mm): a cell counts when its eight neighbours are free too,
            # so the cells between two steps are free as well
            okc = np.stack([~dilate(~ok[l], 1) for l in range(3)])[:, ::2, ::2]
            vokc = vok[::2, ::2] & okc[VIA_L].all(axis=0)
            H, W = okc.shape[1:]
            S = reg.soft[:, j0:j1 + 1:2, i0:i1 + 1:2]
            pen = [((S[l] != FREE) & (S[l] != p) & (S[l] != n)).tobytes() for l in range(3)]
            yy, xx = np.mgrid[0:H, 0:W]

            def near(g_, r_):
                cx, cy = ((g_["x"] - reg.x0) / G - i0) / 2, ((g_["y"] - reg.y0) / G - j0) / 2
                return (xx - cx) ** 2 + (yy - cy) ** 2 <= ((g_["sep"] / 2 + r_) / G / 2) ** 2
            ma, mb = near(ga, radius), near(gb, radius)
            starts = []
            goal = np.zeros((3, H, W), bool)
            if zone is not None:
                zw = zone[:, j0:j1 + 1, i0:i1 + 1]
                zw = (zw | np.roll(zw, 1, axis=1) | np.roll(zw, -1, axis=1))[:, ::2, ::2]      # (a line one cell thick must survive the coarse grid)
            for l in range(3):                  # on a layer the pads are not on, the trunk starts / ends with its two vias
                if l in ga["layers"] or vias:
                    ys, xs = np.nonzero(okc[l] & ma & (True if l in ga["layers"] else vokc))
                    c0 = 0 if l in ga["layers"] else PAIR_VIA_COST
                    starts += [((l * H + int(y_)) * W + int(x_), c0) for y_, x_ in zip(ys, xs)]
                if zone is not None:
                    if l in gb["layers"]:
                        goal[l] = okc[l] & zw[l]
                elif l in gb["layers"] or vias:
                    goal[l] = okc[l] & mb & (True if l in gb["layers"] else vokc)
            if not starts or not goal.any():
                continue
            gl, gy, gx = np.nonzero(goal)
            gbox = (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max()))
            path = search_pair([okc[l].tobytes() for l in range(3)], vokc.tobytes() if vias else None,
                               [goal[l].tobytes() for l in range(3)], W, H, starts, gbox, max_exp=500000, penb=pen)
            if not path:
                self.pair_why = "no corridor found (%.0f s)" % (time.time() - t0)
                continue
            cells_ = [(l, i0 + 2 * x, j0 + 2 * y) for l, x, y in path]
            geo = self.pair_geometry(reg, prc, cells_, ga, gb)
            if geo and geo[2]:              # docked ends: only if their last bits are clear of everything else
                Dk = reg.D[rc.Kt]
                for m_, l_, a_, b_ in geo[2]:
                    net_ = (p, n)[m_]
                    cs_, on_ = reg.seg_cells(a_, b_)
                    if not cs_ or any(int(Dk[l_, j_, i_]) not in (FREE, net_) for i_, j_ in cs_):
                        geo = self.pair_geometry(reg, prc, cells_, ga, gb, dock=False)
                        break
            if geo:
                break
            self.pair_why = "corridor found but too cramped to draw"
        else:
            return None
        lines, vias_xy = geo[0], geo[1]
        length = {}
        for k, net in enumerate((p, n)):
            nd = reg.node()
            length[net] = 0.0
            for l, line in lines[k]:
                for a, b in zip(line, line[1:]):
                    if math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6:
                        continue
                    self.add_track(reg, net, l, a, b, rc.w)
                    length[net] += math.hypot(a[0] - b[0], a[1] - b[1])
                    cells, on = reg.seg_cells(a, b)
                    if cells:
                        reg.stamp_cells(l, cells, rc.mt + 1, net)
                        reg.assign(net, [(l, i, j) for i, j in cells], nd)
            for l, pt in ((lines[k][0][0], lines[k][0][1][0]), (lines[k][-1][0], lines[k][-1][1][-1])):
                c = (l, int(round((pt[0] - reg.x0) / G)), int(round((pt[1] - reg.y0) / G)))
                reg.exact.setdefault(net, {})[c] = pt
                reg.tips.setdefault(net, []).append((l, pt[0], pt[1]))
            self.trunk_node[net] = nd
            for xy in vias_xy[k]:
                self.add_via_xy(reg, net, xy, rc, nd)
        return length[p], length[n], len(vias_xy[0])

    def pair_geometry(self, reg, prc, cells, ga, gb, dock=True):
        """Centre-line cells -> for P and for N: [(layer, [points])], the via positions, and the docked ends
        [(wire, layer, tip, where the trunk track meets it)].  None if it cannot be drawn."""
        runs = [[cells[0]]]
        for c in cells[1:]:
            if c[0] != runs[-1][-1][0]:
                runs.append([c])
            else:
                runs[-1].append(c)
        polys, layers = [], []
        for run in runs:
            if len(run) < 2:
                return None
            polys.append(_corners(_simplify([reg.xy(c[1], c[2]) for c in run]), 0.2))
            layers.append(run[0][0])

        def plen(q):
            return sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(q, q[1:]))
        # an end that is not on the pads' layer, or a first / last run too short to draw, becomes a via pair
        via_a, via_b = layers[0] not in ga["layers"], layers[-1] not in gb["layers"]
        if len(polys) > 1 and not via_a and plen(polys[0]) < PAIR_BACK + 0.3:
            polys.pop(0)
            layers.pop(0)
            via_a = True
        if len(polys) > 1 and not via_b and plen(polys[-1]) < PAIR_BACK + 0.3:
            polys.pop()
            layers.pop()
            via_b = True
        u0 = _unit(polys[0][0], polys[0][1])
        u1 = _unit(polys[-1][-2], polys[-1][-1])
        S, E = polys[0][0], polys[-1][-1]

        def tips(sign):
            oa = sign * (PAIR_VIA_OFF if via_a else prc.off + PAIR_FLARE)
            ob = sign * (PAIR_VIA_OFF if via_b else prc.off + PAIR_FLARE)
            return ((S[0] - oa * u0[1], S[1] + oa * u0[0]), (S[0] + oa * u0[1], S[1] - oa * u0[0]),
                    (E[0] - ob * u1[1], E[1] + ob * u1[0]), (E[0] + ob * u1[1], E[1] - ob * u1[0]))

        def score(sign):                            # which side P goes: no crossing at the ends, then the shorter ends
            pa, na, pb, nb = tips(sign)
            ea, fa = (ga["p"]["ex"], ga["p"]["ey"]), (ga["n"]["ex"], ga["n"]["ey"])
            sc = 10 * _cross(ea, pa, fa, na) + 0.1 * (math.hypot(ea[0] - pa[0], ea[1] - pa[1]) + math.hypot(fa[0] - na[0], fa[1] - na[1]))
            if gb["p"] is not None:
                eb, fb = (gb["p"]["ex"], gb["p"]["ey"]), (gb["n"]["ex"], gb["n"]["ey"])
                sc += 10 * _cross(eb, pb, fb, nb) + 0.1 * (math.hypot(eb[0] - pb[0], eb[1] - pb[1]) + math.hypot(fb[0] - nb[0], fb[1] - nb[1]))
            return sc
        sign = min((1, -1), key=score)
        ta = tips(sign)
        lines, vias_xy = ([], []), ([], [])
        docks = []

        def dock_to(gate, m, layer):
            """The loose end this wire can be drawn onto: the gate's terminal for wire m, if it is a loose end on this layer."""
            t_ = gate.get("p" if m == 0 else "n") if dock else None
            return (t_["x"], t_["y"]) if t_ and t_.get("tip") and t_.get("layer") == layer else None
        via_at = {}
        nruns = len(polys)
        for k, pts in enumerate(polys):
            first, last = k == 0, k == nruns - 1
            q = pts
            if not first or via_a:
                q = _trim(q, PAIR_BACK, False)
            if q and (not last or via_b):
                q = _trim(q, PAIR_BACK, True)
            if not q or len(q) < 2 or plen(q) < 0.25:
                return None
            for m, sg in enumerate((sign, -sign)):
                line = _offset(q, sg * prc.off)
                o = sg * (prc.off + PAIR_FLARE)
                if first and via_a:
                    vias_xy[m].append(ta[m])
                    line.insert(0, ta[m])
                elif first and dock_to(ga, m, layers[k]):
                    docks.append((m, layers[k], dock_to(ga, m, layers[k]), line[0]))
                    line.insert(0, dock_to(ga, m, layers[k]))
                elif first:
                    u = _unit(q[0], q[1])
                    tip = (q[0][0] - o * u[1], q[0][1] + o * u[0])
                    if math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1]) >= 2.5 * PAIR_FLARE:
                        line[0] = (line[0][0] + u[0] * PAIR_FLARE, line[0][1] + u[1] * PAIR_FLARE)
                    line.insert(0, tip)
                else:
                    line.insert(0, via_at[(k - 1, m)])
                if last and via_b:
                    vias_xy[m].append(ta[2 + m])
                    line.append(ta[2 + m])
                elif last and dock_to(gb, m, layers[k]):
                    docks.append((m, layers[k], dock_to(gb, m, layers[k]), line[-1]))
                    line.append(dock_to(gb, m, layers[k]))
                elif last:
                    u = _unit(q[-2], q[-1])
                    tip = (q[-1][0] - o * u[1], q[-1][1] + o * u[0])
                    if math.hypot(q[-1][0] - q[-2][0], q[-1][1] - q[-2][1]) >= 2.5 * PAIR_FLARE:
                        line[-1] = (line[-1][0] - u[0] * PAIR_FLARE, line[-1][1] - u[1] * PAIR_FLARE)
                    line.append(tip)
                else:
                    u = _unit(pts[-2], pts[-1])
                    v = (pts[-1][0] - sg * PAIR_VIA_OFF * u[1], pts[-1][1] + sg * PAIR_VIA_OFF * u[0])
                    via_at[(k, m)] = v
                    vias_xy[m].append(v)
                    line.append(v)
                lines[m].append((layers[k], line))
        # the two tracks must keep their distance from each other everywhere (a folded corner can bring them together)
        def seg_dist(a1, b1, a2, b2):
            def pt(p_, a_, b_):
                dx, dy = b_[0] - a_[0], b_[1] - a_[1]
                L2 = dx * dx + dy * dy
                u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p_[0] - a_[0]) * dx + (p_[1] - a_[1]) * dy) / L2))
                return math.hypot(a_[0] + u * dx - p_[0], a_[1] + u * dy - p_[1])
            if _cross(a1, b1, a2, b2):
                return 0.0
            return min(pt(a1, a2, b2), pt(b1, a2, b2), pt(a2, a1, b1), pt(b2, a1, b1))
        apart = prc.rc.w + prc.rc.cl + 0.015
        for (l0, line0), (l1, line1) in ((x_, y_) for x_ in lines[0] for y_ in lines[1]):
            if l0 != l1:
                continue
            for a1, b1 in zip(line0, line0[1:]):
                for a2, b2 in zip(line1, line1[1:]):
                    if seg_dist(a1, b1, a2, b2) < apart:
                        return None
        need = prc.rc.via_d / 2 + prc.rc.w / 2 + prc.rc.cl + 0.03
        for m in (0, 1):
            for vx, vy in vias_xy[1 - m]:
                for _, line in lines[m]:
                    for a, b in zip(line, line[1:]):
                        dx, dy = b[0] - a[0], b[1] - a[1]
                        L2 = dx * dx + dy * dy
                        u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((vx - a[0]) * dx + (vy - a[1]) * dy) / L2))
                        if math.hypot(a[0] + u * dx - vx, a[1] + u * dy - vy) < need:
                            return None
        return lines, vias_xy, docks

    # ---- plane nets: one via per SMD pad (or a shared one close by), a via array in exposed pads ----
    def fanout(self, reg, net, only=None, rc=None):
        rc = rc or (self.rc_of[net] if self.cls_of[net] in RCS else RCS["Default"])
        okc = bad = 0
        badl = []
        had = {reg.find(nd) for nd in reg.tree.get(net, {}).values()}       # islands with copper from an earlier region / stage
        for pd in sorted(reg.pads[net], key=lambda p: (p["cx"], p["cy"])):
            if pd["tht"] or pd.get("fanned") or reg.find(pd["node"]) in had:
                continue                                        # through-hole pads meet the planes directly
            if only is not None and (pd["ref"] + "." + pd["num"]) not in only:
                continue
            pd["fanned"] = True
            if pd["area"] >= 6.0 and self.ep_vias(reg, net, rc, pd):
                okc += 1
                continue                                        # (a big pad with no room for vias inside it fans out like any other)
            res = None
            for rc_use, margin in [(r0, m_) for r0 in ([rc] + ([THIN[rc.name]] if rc.name in THIN else [])) for m_ in (50, 120)]:
                box = (pd["cx"], pd["cy"], pd["cx"], pd["cy"])
                i0, j0, W, H, ok, vok = self.window(reg, net, rc_use, box, margin)
                goal = np.zeros((3, H, W), bool)
                for c in reg.tree.get(net, ()):
                    if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                        goal[c[0], c[2] - j0, c[1] - i0] = True
                starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in pd["cells"]
                          if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
                if not starts:
                    continue
                okb = [ok[l].tobytes() for l in range(3)]
                res, via = search(okb, vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts, (0, 0, 0, 0), fanout=True, max_exp=200000)
                if res:
                    break
            if not res:
                bad += 1
                badl.append(f'{pd["ref"]}.{pd["num"]}')
                continue
            cells = self.commit(reg, net, rc_use, res, W, H, i0, j0, via_at_end=via)
            self.stub(reg, net, rc_use, cells[0], pd)
            okc += 1
        return okc, badl

    def ep_vias(self, reg, net, rc, pd):
        bb = pd["pad"].GetBoundingBox()
        xa, ya = ToMM(bb.GetLeft()) - OX + 0.7, ToMM(bb.GetTop()) - OY + 0.7
        xb, yb = ToMM(bb.GetRight()) - OX - 0.7, ToMM(bb.GetBottom()) - OY - 0.7
        nxv = max(1, int((xb - xa) / 1.3) + 1)
        nyv = max(1, int((yb - ya) / 1.3) + 1)
        n = 0
        Dv = reg.D[rc.Kv]
        for a in range(nxv):
            for b in range(nyv):
                x = xa + (xb - xa) * (a / (nxv - 1) if nxv > 1 else 0.5)
                y = ya + (yb - ya) * (b / (nyv - 1) if nyv > 1 else 0.5)
                i, j = int(round((x - reg.x0) / G)), int(round((y - reg.y0) / G))
                if all(Dv[l, j, i] in (FREE, net) for l in VIA_L) and not reg.novia[j, i]:
                    self.add_via(reg, net, i, j, rc)
                    n += 1
        return n

    # ---- driver ----
    def run_region(self, reg, prio_nets, prio_fan):
        """One pass over a region.  Nets (and plane pads) that failed in an earlier pass go first."""
        nets_done, nets_part, fan_ok, fan_bad = [], [], 0, []
        code_of = {v: k for k, v in self.name_of.items()}
        planes = [code_of[n] for n in sorted(PLANES) if reg.name in PLANES[n] and n in code_of and code_of[n] in reg.pads]
        if prio_fan:
            for net in planes:
                okc, bad = self.fanout(reg, net, only=prio_fan)
                fan_ok += okc
                fan_bad += [(reg.name, self.name_of[net], b) for b in bad]
        cand = []
        pcand = []
        for net in sorted(set(reg.pads) | set(reg.tree)):
            pads = reg.pads.get(net, [])
            name = self.name_of[net]
            if name in PLANES and reg.name in PLANES[name]:
                continue
            # (PoE primary nets are routed like the others, but only inside the primary area: see Region.pri)
            if self.cls_of[net] in SKIP_CLASSES or name in SKIP_NETS or len(self.groups(reg, net)) < 2:
                continue
            if self.only and not fnmatch.fnmatch(name, self.only):
                continue
            xs = [p["cx"] for p in pads] + [reg.x0 + c[1] * G for c in list(reg.tree.get(net, {}))[::50]]
            ys = [p["cy"] for p in pads] + [reg.y0 + c[2] * G for c in list(reg.tree.get(net, {}))[::50]]
            if self.cls_of[net] in PAIR_CLASSES and not self.is_line(net):     # (the jack's pairs: a few mm, single)
                pcand.append((0 if name in prio_nets else 1, max(xs) - min(xs) + max(ys) - min(ys), name, net))
                continue
            if name in prio_nets:
                cand.append((-1, prio_nets.index(name), name, net))
            else:
                rank = {"PWR_5V": 0, "PWR": 1, "POE_PRIMARY": 1}.get(self.cls_of[net], 2)      # wide tracks first, while there is room
                if reg.name == "column" and rank < 2:
                    rank = 3                    # (what the power stage left open is tried again here, after the signals)
                cand.append((rank, max(xs) - min(xs) + max(ys) - min(ys), name, net))
        # differential pairs: first a short stub out of every pair of pins on the hubs, later each pair whole
        # (the coupled trunk, then its two nets)
        pcand.sort(key=lambda t_: (t_[0], -t_[1], t_[2]))      # the long ones first: they have the least choice
        pnames = {name: net for _, _, name, net in pcand}
        if pnames and not self.only:
            nfan = self.fan_out_pairs(reg, pnames)
            if nfan:
                self.log.append(f"region {reg.name}: {nfan} pairs fanned out of the big ICs before the trunks")
        # then the nets that leave this window for the column (the processor's USB links to the hubs, SD card, I2C):
        # once the strip is full there is no way left from the hubs to the column
        if reg.name == "strip" and self.cross and not self.only:
            names = {self.name_of[c]: c for c in self.cross if c in reg.pads}
            okl, badl, other = self.route_ports(reg, names, self.port_zone(reg))
            for n_ in badl:
                self.failed.append((reg.name, n_, "the hand-over line to the column"))
            for n_, f in other:
                self.failed.append((reg.name, n_, f))
            self.log.append(f"region {reg.name}: {len(okl)} nets brought to the hand-over line to the column first, {len(badl)} not")
            if os.environ.get("CP_VERBOSE"):
                print("   " + self.log[-1], flush=True)
        if os.environ.get("CP_ONLY_CROSS"):
            return nets_done, nets_part, fan_ok, fan_bad
        # then the supply nets, while there is room for their wide tracks (the pairs can change layer to get past them)
        cand.sort()
        first = [c for c in cand if c[0] in (0, 1)]
        cand = [c for c in cand if c[0] not in (0, 1)]
        for rank, hp, name, net in first:
            t0 = time.time()
            if os.environ.get("CP_VERBOSE") == "2":
                print("   ... %s (%d islands)" % (name, len(self.groups(reg, net))), flush=True)
            okp, bad = self.route_net(reg, net)
            if os.environ.get("CP_VERBOSE") and time.time() - t0 > (3 if os.environ["CP_VERBOSE"] == "1" else -1):
                print("   net %-24s %d/%d pads, %d not joined, %.0f s" % (name, okp, len(reg.pads.get(net, [])), len(bad), time.time() - t0), flush=True)
            (nets_part if bad else nets_done).append((reg.name, name, okp, len(reg.pads.get(net, []))))
            for b in bad:
                self.failed.append((reg.name, name, b))
        seen = set()
        for rank, hp, name, net in pcand:
            if net in seen:
                continue
            other = pair_partner(name, pnames) or next((o for o in pnames if pair_partner(o, pnames) == name), None)
            group = [net]
            if other is not None and pnames[other] not in seen:
                pn, nn = (name, other) if pair_partner(name, pnames) == other else (other, name)
                t0 = time.time()
                tr = self.route_pair(reg, pnames[pn], pnames[nn])
                self.pairs.append((reg.name, pn, nn, tr or self.pair_why))
                if os.environ.get("CP_VERBOSE"):
                    print("   pair %-22s %-60s %.0f s" % (pn, tr or self.pair_why, time.time() - t0), flush=True)
                group = [pnames[pn], pnames[nn]]
            for net2 in group:
                seen.add(net2)
                t0 = time.time()
                okp, bad = self.route_net(reg, net2)
                if os.environ.get("CP_VERBOSE") and time.time() - t0 > (3 if os.environ["CP_VERBOSE"] == "1" else -1):
                    print("   net %-24s %d/%d pads, %d not joined, %.0f s" % (self.name_of[net2], okp, len(reg.pads.get(net2, [])), len(bad), time.time() - t0), flush=True)
                (nets_part if bad else nets_done).append((reg.name, self.name_of[net2], okp, len(reg.pads.get(net2, []))))
                for b in bad:
                    self.failed.append((reg.name, self.name_of[net2], b))
        cand.sort()
        for rank, hp, name, net in cand:
            t0 = time.time()
            okp, bad = self.route_net(reg, net)
            if os.environ.get("CP_VERBOSE") and time.time() - t0 > (3 if os.environ["CP_VERBOSE"] == "1" else -1):
                print("   net %-24s %d/%d pads, %d not joined, %.0f s" % (name, okp, len(reg.pads.get(net, [])), len(bad), time.time() - t0), flush=True)
            (nets_part if bad else nets_done).append((reg.name, name, okp, len(reg.pads.get(net, []))))
            for b in bad:
                self.failed.append((reg.name, name, b))
        if os.environ.get("CP_VERBOSE"):
            print("   signals done, plane fan-out next", flush=True)
        for net in ([] if self.only else planes):
            only = None
            if reg.name in ("poe", "column"):       # here the planes do not reach everywhere: a via elsewhere would connect nothing
                only = {p_["ref"] + "." + p_["num"] for p_ in reg.pads[net] if over_plane(p_["cx"], p_["cy"])}
            okc, bad = self.fanout(reg, net, only=only)
            fan_ok += okc
            fan_bad += [(reg.name, self.name_of[net], b) for b in bad]
        if reg.name in ("poe", "column") and not self.only and "VCC5V_BUS" in code_of and code_of["VCC5V_BUS"] in reg.pads:
            net = code_of["VCC5V_BUS"]
            over = {p_["ref"] + "." + p_["num"] for p_ in reg.pads[net]
                    if p_["cx"] >= XR + 0.8 and not (N0 - 0.5 <= p_["cy"] <= N1 + 0.5 and p_["cx"] < NXR + 0.8)}
            if over:
                okc, bad = self.fanout(reg, net, only=over)
                fan_ok += okc
        return nets_done, nets_part, fan_ok, fan_bad

    def run(self, passes=4):
        """Every region is routed up to 'passes' times; what failed goes first next time; the best pass is kept."""
        nets_done, nets_part, fan_ok, fan_bad, failed = [], [], 0, [], []
        only = [x for x in os.environ.get("CP_REGIONS", "").split(",") if x]       # (by hand: re-route some regions only)
        for spec in [s_ for s_ in REGIONS if not only or s_[0] in only]:
            best = None
            prio_nets, prio_fan = [], set()
            self.cross = cross_nets(self.board, self, spec) if spec[0] == "strip" else {}
            for n in range(passes):
                t0 = time.time()
                self.regs = [Region(*spec)]
                self.build()
                self.items, self.failed = [], []
                npair = len(self.pairs)
                res = self.run_region(self.regs[0], prio_nets, prio_fan)
                pass_pairs = self.pairs[npair:]
                del self.pairs[npair:]
                nfail = len(self.failed) + len(res[3])
                self.log.append("region %s, pass %d: %d connections open, %.0f s" % (spec[0], n + 1, nfail, time.time() - t0))
                print(self.log[-1], flush=True)
                if best is None or nfail < best[0]:
                    best = (nfail, self.items, list(self.failed), res, pass_pairs)
                if nfail == 0:
                    break
                for _, name, _ in self.failed:
                    if name not in prio_nets:
                        prio_nets.append(name)
                prio_fan |= {b for _, _, b in res[3]}
            self.flush(best[1])
            self.pairs += best[4]
            failed += best[2]
            nets_done += best[3][0]
            nets_part += best[3][1]
            fan_ok += best[3][2]
            fan_bad += best[3][3]
        self.failed = ["%s: %s: could not reach %s" % f for f in failed]
        return nets_done, nets_part, fan_ok, ["%s: %s: no via for %s" % f for f in fan_bad]


def _inside(pts, x, y):
    n, c = len(pts), False
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            c = not c
    return c


def over_plane(x, y, margin=1.6):
    """True if the ground plane is under this point and for 'margin' mm around it (room for the fan-out via)."""
    return all(_inside(PLANE_GND, x + dx, y + dy) for dx in (-margin, 0, margin) for dy in (-margin, 0, margin))


def add_zone(board, net, layer, pts, name, prio=0):
    z = pcbnew.ZONE(board)
    z.SetNet(board.FindNet(net))
    z.SetLayer(layer)
    z.SetZoneName(name)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.20))
    z.SetMinThickness(FromMM(0.15))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    try:
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    except AttributeError:
        pass
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(FromMM(OX + x), FromMM(OY + y))
    board.Add(z)
    return z


def drop_dangling(board):
    """Remove one-cell stubs with an end that touches nothing (no pad, via or other track end)."""
    ends = {}
    vias = set()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            vias.add((t.GetPosition().x, t.GetPosition().y))
            continue
        for e in (t.GetStart(), t.GetEnd()):
            k = (e.x, e.y, t.GetLayer())
            ends[k] = ends.get(k, 0) + 1
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pads.setdefault(p.GetNetCode(), []).append(p)
    kill = []
    for t in [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and ToMM(t.GetLength()) <= 0.075]:
        loose = False
        for e in (t.GetStart(), t.GetEnd()):
            if ends[(e.x, e.y, t.GetLayer())] > 1 or (e.x, e.y) in vias:
                continue
            if not any(p.IsOnLayer(t.GetLayer()) and p.HitTest(VECTOR2I(e.x, e.y), 0) for p in pads.get(t.GetNetCode(), ())):
                loose = True
        if loose:
            kill.append(t)
    for t in kill:
        board.Remove(t)
    return len(kill)


# --------------------------------------------------------------------------
# stages: each one is a process of its own (the escape stage needs a finer grid), working on the same board file
# --------------------------------------------------------------------------
STAGES = ("clean", "escape", "links", "local", "ports", "power", "column", "prune", "finish")
STAGE_GRID = {"escape": "0.025"}


def is_power(name, cname):
    return cname in ("PWR", "PWR_5V") or name.startswith(POWER_PREFIX)


def stage_file(name):
    tag = os.path.splitext(os.path.basename(os.environ.get("CP_PCB") or cpmodel.PRJ))[0]      # (a test copy keeps its own files)
    return os.path.join(ROOT, "build", "route_stage_%s_%s.json" % (tag, name))


def cross_nets(board, r, spec):
    """Nets with pads inside the window and pads outside it that are not joined yet -> {code: (inside pads, outside pads)}."""
    import report_open
    board.BuildConnectivity()
    out = {}
    for code, groups in report_open.islands(board).items():
        if len(groups) < 2:
            continue
        name = r.name_of.get(code, "")
        if name in PLANES or name in SKIP_NETS or r.cls_of.get(code) in SKIP_CLASSES:
            continue
        ins = outs = 0
        for g in groups:
            for p_ in g:
                x, y = ToMM(p_.GetPosition().x) - OX, ToMM(p_.GetPosition().y) - OY
                if spec[1] + 0.2 <= x <= spec[3] - 0.2 and spec[2] + 0.2 <= y <= spec[4] - 0.2:
                    ins += 1
                else:
                    outs += 1
        if ins and outs:
            out[code] = (ins, outs)
    return out


def stage_links(board, r):
    """The processor's USB pairs to the two hubs (and to the capacitors of the hub's SuperSpeed upstream), each routed in
    ONE piece on the still empty board: from the ends that the escape stage left beside the RK3566, up the right-hand
    corridor, along the strip to the hub.  Routed in pieces by three later stages, one joint or another kept failing.
    A window of its own, from the column's left edge to just past the second hub."""
    soc = next((f for f in board.GetFootprints() if f.GetPadCount() >= 400), None)
    if soc is None:
        return dict(done=[], part=[])
    xs = [ToMM(p_.GetPosition().x) - OX for f in board.GetFootprints() if 40 <= f.GetPadCount() < 100 for p_ in f.Pads()
          if p_.GetNet() is not None and r.cls_of.get(p_.GetNetCode()) in PAIR_CLASSES]
    ys = [ToMM(p_.GetPosition().y) - OY for p_ in soc.Pads()]
    spec = ("links", -1.0, math.floor(SY - 1.5), math.ceil(max(xs) + 6.0), math.ceil(max(ys) + 2.0))
    reg = Region(*spec)
    r.regs = [reg]
    r.build()
    r.items, r.failed = [], []
    soc_nets = {p_.GetNetCode() for p_ in soc.Pads() if p_.GetNetCode() > 0}
    names = {}
    for code in soc_nets:
        if r.cls_of.get(code) in ("USB2", "USB3_SS") and code in reg.pads and len(r.groups(reg, code)) > 1:
            n_all = sum(1 for f in board.GetFootprints() for p_ in f.Pads() if p_.GetNetCode() == code)
            if n_all == len(reg.pads[code]):                # every pad of the net is inside this window
                names[r.name_of[code]] = code
    nfan = r.fan_out_pairs(reg, names)                      # a stub out of every pair of hub pins (kept by the strip stage)
    done, part, seen = [], [], set()

    def span(code):
        pd = reg.pads[code]
        return max(q["cx"] for q in pd) - min(q["cx"] for q in pd) + max(q["cy"] for q in pd) - min(q["cy"] for q in pd)
    # the shortest first: the USB 3 hub sits at the corner of the strip, and its upstream pins face the board edge -
    # a long link routed before them takes the one channel they have
    for name in sorted(names, key=lambda n_: span(names[n_])):
        code = names[name]
        if code in seen:
            continue
        group = [code]
        partner = pair_partner(name, names) or next((o for o in names if pair_partner(o, names) == name), None)
        if partner is not None and names[partner] not in seen:
            pn, nn = (name, partner) if pair_partner(name, names) == partner else (partner, name)
            tr = r.route_pair(reg, names[pn], names[nn])
            r.pairs.append(("links", pn, nn, tr or r.pair_why))
            group = [names[pn], names[nn]]
        for c in group:
            seen.add(c)
            okp, bad = r.route_net(reg, c)
            (part if bad else done).append(("links", r.name_of[c], okp, len(reg.pads.get(c, []))))
            r.failed += ["links: %s: could not reach %s" % (r.name_of[c], b) for b in bad]
    r.flush(r.items)
    r.log.append("links: %d hub pin pairs fanned out; processor <-> hub USB nets in one piece: %d, not: %d" % (nfan, len(done), len(part)))
    print(r.log[-1], flush=True)
    return dict(done=done, part=part)


def stage_ports(board, r):
    """A second chance for the nets that go from the strip into the column and did not get to the hand-over line when
    the strip was routed (the strip stage routes them first of all)."""
    spec = next(s_ for s_ in REGIONS if s_[0] == "strip")
    cross = cross_nets(board, r, spec)
    reg = Region(*spec)
    r.regs = [reg]
    r.build()
    r.items, r.failed = [], []
    zone = r.port_zone(reg)
    names = {r.name_of[c]: c for c in cross if c in reg.pads}
    ok, bad, other = r.route_ports(reg, names, zone)
    r.failed += ["ports: %s: no way from the strip to the column" % n_ for n_ in bad]
    r.failed += ["ports: %s: could not reach %s" % f for f in other]
    r.flush(r.items)
    r.log.append("ports: %d nets reach the hand-over line to the column (y = %.2f), %d do not" % (len(ok), PORT_Y, len(bad)))
    print(r.log[-1], flush=True)
    return dict(done=ok, part=bad)


def stage_escape(board, r):
    """Under each fine-pitch BGA: a via in the pad for every ground ball, and every signal ball brought out to a point
    outside the package where the 0.05 mm grid can pick it up.  Runs on a 0.025 mm grid with 0.09 mm tracks and
    0.25 / 0.15 mm vias - the only features that fit between 0.4 mm-pitch balls."""
    r.bga = True
    rc = RCS["DDR"]
    code_of = {v: k for k, v in r.name_of.items()}
    total = {}
    for fp in board.GetFootprints():
        total_seen = set()
        for p_ in fp.Pads():
            if p_.GetNetCode() > 0 and (fp.GetReference(), p_.GetNetCode()) not in total_seen:
                total_seen.add((fp.GetReference(), p_.GetNetCode()))
                total[p_.GetNetCode()] = total.get(p_.GetNetCode(), 0) + 1       # footprints a net touches
    esc_ok, esc_bad, gnd_ok, gnd_bad, pwr_ok = [], [], 0, [], 0
    for fp in sorted((f for f in board.GetFootprints() if f.GetPadCount() >= 100), key=lambda f: f.GetReference()):
        ref = fp.GetReference()
        xs = [ToMM(p_.GetPosition().x) - OX for p_ in fp.Pads()]
        ys = [ToMM(p_.GetPosition().y) - OY for p_ in fp.Pads()]
        bx = (min(xs) - 0.15, min(ys) - 0.15, max(xs) + 0.15, max(ys) + 0.15)

        def snap(v, up):
            return (math.ceil(v * 20 - 1e-6) if up else math.floor(v * 20 + 1e-6)) / 20.0
        spec = ("bga", snap(bx[0] - 2.5, False), snap(bx[1] - 2.5, False), snap(bx[2] + 2.5, True), snap(bx[3] + 2.5, True))
        reg = Region(*spec)
        r.regs = [reg]
        r.build()
        r.items = []
        # the zone a ball is brought to: outside the package, on the 0.05 mm grid, inside the window
        step = int(round(0.05 / G))
        zone = np.zeros((3, reg.ny, reg.nx), bool)
        zone[:, ::step, ::step] = True
        ia, ib = int((bx[0] - ESCAPE_MARGIN - reg.x0) / G), ceil_((bx[2] + ESCAPE_MARGIN - reg.x0) / G)
        ja, jb = int((bx[1] - ESCAPE_MARGIN - reg.y0) / G), ceil_((bx[3] + ESCAPE_MARGIN - reg.y0) / G)
        zone[:, max(0, ja):jb + 1, max(0, ia):ib + 1] = False
        edge = ceil_(0.5 / G)
        zone[:, :edge, :] = zone[:, -edge:, :] = False
        zone[:, :, :edge] = zone[:, :, -edge:] = False
        mine = {}
        for code, pads in reg.pads.items():
            for pd in pads:
                if pd["ref"] == ref:
                    mine.setdefault(code, []).append(pd)
        # signal balls first (each has only this one ball; ground and supply have many)
        cand = []
        for code, pads in mine.items():
            name = r.name_of[code]
            if name in PLANES or name in SKIP_NETS or r.cls_of[code] in SKIP_CLASSES or is_power(name, r.cls_of[code]):
                continue
            if total.get(code, 0) < 2:
                continue                                    # a ball that goes nowhere else
            led = {reg.find(nd) for nd in reg.tree.get(code, {}).values()}
            for pd in pads:
                if reg.find(pd["node"]) in led:
                    continue                                # (already brought out by an earlier run)
                cand.append((min(pd["cx"] - bx[0], bx[2] - pd["cx"], pd["cy"] - bx[1], bx[3] - pd["cy"]), name, code, pd))
        # the differential pairs first (USB, HDMI: they have no alternative ball), then the others, outermost first
        cand.sort(key=lambda t_: (0 if r.cls_of[t_[2]] in PAIR_CLASSES else 1, t_[0], t_[1]))
        # The end of an escape must be a place the 0.05 mm grid can dock onto: nothing foreign within 0.35 mm when it
        # is made, and it stays that way - a disc around it is booked for its net, so later escapes keep off.
        room = max(k_ for k_ in KSET if k_ * G <= 0.35 + 1e-9)
        keep = ceil_(0.25 / G)
        for depth, name, code, pd in cand:
            wide = CLS.get(r.cls_of[code], CLS["Default"])["clearance"] > 0.09 + 1e-9
            end = r.route_port(reg, code, zone, rc=RCS["ESC10"] if wide else rc, pad=pd, room=room)
            if end is not None:
                reg.stamp(end[0], end[1] - keep, end[2] - keep, disc(keep), code)
            (esc_ok if end is not None else esc_bad).append("%s.%s %s" % (ref, pd["num"], name))
        # ground balls: a via in the pad, down to the planes
        for name in sorted(PLANES):
            code = code_of.get(name)
            if code in mine and "bga" in PLANES[name]:
                only = {pd["ref"] + "." + pd["num"] for pd in mine[code] if over_plane(pd["cx"], pd["cy"], 0.5)}
                okc, badl = r.fanout(reg, code, only=only, rc=rc)
                gnd_ok += okc
                gnd_bad += ["%s: %s" % (name, b) for b in badl]
        # supply balls: a via in the pad as well - the power stage joins them on the power layer
        for code in sorted(mine):
            name = r.name_of[code]
            if name in PLANES or not is_power(name, r.cls_of[code]) or STRIP:
                continue
            okc, badl = r.fanout(reg, code, only={pd["ref"] + "." + pd["num"] for pd in mine[code]}, rc=RCS["ESC10"])
            pwr_ok += okc
            gnd_bad += ["%s: %s" % (name, b) for b in badl]
        r.flush(r.items)
        r.log.append("escape %s: %d signal balls brought out, %d not; ground balls with a via %d" % (
            ref, sum(1 for e in esc_ok if e.startswith(ref + ".")), sum(1 for e in esc_bad if e.startswith(ref + ".")), gnd_ok))
        print(r.log[-1], flush=True)
    # second part: under each package, the vias of the supply balls are joined to each other and to the capacitors
    # beside them, on the POWER layer (In3 takes the place of In2 as the router's middle layer), and one end of each
    # net is brought out for the power stage.  Thin links - the pours of the last stage widen them.
    pw_ok, pw_bad = [], []
    if not STRIP:
        RLAYERS[1] = pcbnew.In3_Cu
        ball = RCS["BALL"]
        r.quick = True
        for fp in sorted((f for f in board.GetFootprints() if f.GetPadCount() >= 100), key=lambda f: f.GetReference()):
            ref = fp.GetReference()
            xs = [ToMM(p_.GetPosition().x) - OX for p_ in fp.Pads()]
            ys = [ToMM(p_.GetPosition().y) - OY for p_ in fp.Pads()]
            bx = (min(xs) - 0.15, min(ys) - 0.15, max(xs) + 0.15, max(ys) + 0.15)

            def snap(v, up):
                return (math.ceil(v * 20 - 1e-6) if up else math.floor(v * 20 + 1e-6)) / 20.0
            reg = Region("bga", snap(bx[0] - 2.5, False), snap(bx[1] - 2.5, False), snap(bx[2] + 2.5, True), snap(bx[3] + 2.5, True))
            r.regs = [reg]
            r.build()
            r.items = []
            step = int(round(0.05 / G))
            zone = np.zeros((3, reg.ny, reg.nx), bool)
            zone[1, ::step, ::step] = True                 # the end is left on the power layer
            ia, ib = int((bx[0] - ESCAPE_MARGIN - reg.x0) / G), ceil_((bx[2] + ESCAPE_MARGIN - reg.x0) / G)
            ja, jb = int((bx[1] - ESCAPE_MARGIN - reg.y0) / G), ceil_((bx[3] + ESCAPE_MARGIN - reg.y0) / G)
            zone[:, max(0, ja):jb + 1, max(0, ia):ib + 1] = False
            edge = ceil_(0.5 / G)
            zone[:, :edge, :] = zone[:, -edge:, :] = False
            zone[:, :, :edge] = zone[:, :, -edge:] = False
            nets = sorted({code for code, pads in reg.pads.items() if any(pd["ref"] == ref for pd in pads)
                           and r.name_of[code] not in PLANES and is_power(r.name_of[code], r.cls_of[code])},
                          key=lambda c: -len(reg.pads[c]))
            for code in nets:
                old = r.rc_of[code]
                r.rc_of[code] = ball
                okp, bad = r.route_net(reg, code)
                end = r.route_port(reg, code, zone, rc=ball, room=RCS["PWR"].Kt) if total.get(code, 0) >= 2 else True
                r.rc_of[code] = old
                (pw_bad if bad or end is None else pw_ok).append("%s %s" % (ref, r.name_of[code]))
                r.failed += ["escape: %s under %s: could not join %s" % (r.name_of[code], ref, b) for b in bad]
                if end is None:
                    r.failed.append("escape: %s under %s: not brought out to the power layer" % (r.name_of[code], ref))
            r.flush(r.items)
        r.log.append("escape: supply nets joined under the packages on In3: %d, only in part: %d" % (len(pw_ok), len(pw_bad)))
        print(r.log[-1], flush=True)
    r.failed += ["escape: %s: ball not brought out" % e for e in esc_bad] + ["escape: no via for %s" % e for e in gnd_bad]
    r.log.append("escape: %d supply balls given a via in the pad" % pwr_ok)
    return dict(done=esc_ok, part=esc_bad, fan_ok=gnd_ok + pwr_ok, fan_bad=gnd_bad)


def stage_power(board, r):
    """Supply nets in the column, joined with tracks that prefer the power layer (In3): here the router's middle
    layer IS In3, so the signal tracks on In2 are not in its way and it is not in theirs.  The 5 V bus plane that
    already lives on In3 is an obstacle.  The pours added at the end widen these connections."""
    global RLAYERS, STEP
    RLAYERS[1] = pcbnew.In3_Cu
    STEP = ((14, 20), (8, 11), (14, 20))                # the power layer is the cheap one
    r.quick = True
    reg = Region(*COLUMN)
    r.regs = [reg]
    r.build()
    r.items, r.failed = [], []
    plane = raster_outline(reg, PLANE_5V)
    code5 = {v: k for k, v in r.name_of.items()}.get("VCC5V_BUS", MULTI)
    k = ceil_(0.30 / G)
    reg.stamp(1, 0, 0, plane, code5)                    # (the clearance maps grow it; a little extra for the zone's own clearance)
    for D in reg.D.values():
        D[1][dilate(plane, k) & (D[1] == FREE)] = code5
    cand = []
    for net in sorted(set(reg.pads) | set(reg.tree)):
        name = r.name_of[net]
        if name in PLANES or name in SKIP_NETS or r.cls_of[net] in SKIP_CLASSES or not is_power(name, r.cls_of[net]):
            continue
        if len(r.groups(reg, net)) < 2:
            continue
        cand.append((-len(reg.pads.get(net, [])), name, net))
    done, part = [], []
    for _, name, net in sorted(cand):
        okp, bad = r.route_net(reg, net)
        (part if bad else done).append(("power", name, okp, len(reg.pads.get(net, []))))
        r.failed += ["power: %s: could not reach %s" % (name, b) for b in bad]
    r.flush(r.items)
    r.log.append("power: %d supply nets joined, %d only in part" % (len(done), len(part)))
    print(r.log[-1], flush=True)
    return dict(done=done, part=part)


def power_pours(board):
    """A pour on the power layer for every supply net with four pads or more in the core / front part of the column.
    The smaller a net's area, the higher its priority, so a small rail is not swallowed by a big one; a pour only
    keeps the copper that touches its own net's vias."""
    y0, x0, x1 = 60.6, 0.4, CFG["COL_W"] - 0.4
    boxes = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            ni = pad.GetNet()
            if ni is None or pad.GetNetCode() <= 0:
                continue
            name = pad.GetNetname()
            if name in PLANES or not is_power(name, ni.GetNetClassName()) or ni.GetNetClassName() in SKIP_CLASSES:
                continue
            x, y = ToMM(pad.GetPosition().x) - OX, ToMM(pad.GetPosition().y) - OY
            if x0 <= x <= x1 and y >= y0:
                boxes.setdefault(name, []).append((x, y))
    out = []
    for name, pts in boxes.items():
        if len(pts) < 4:
            continue
        xa, ya = max(x0, min(p_[0] for p_ in pts) - 0.6), max(y0, min(p_[1] for p_ in pts) - 0.6)
        xb, yb = min(x1, max(p_[0] for p_ in pts) + 0.6), min(CFG["COL_L"] - 0.4, max(p_[1] for p_ in pts) + 0.6)
        out.append(((xb - xa) * (yb - ya), name, [(xa, ya), (xb, ya), (xb, yb), (xa, yb)]))
    out.sort(reverse=True)
    for prio, (area, name, pts) in enumerate(out, 10):
        z = add_zone(board, name, pcbnew.In3_Cu, pts, f"{name} pour L4", prio=prio)
        z.SetLocalClearance(FromMM(0.10))       # (so that a pour can pass between the vias of a 0.65 mm-pitch ball field)
        z.SetMinThickness(FromMM(0.10))
    return [name for _, name, _ in out]


def stage_prune(board, r):
    """Dead ends go: a track with an end that touches nothing of its net (a hand-over point nobody picked up, the
    trunk of a pair whose ends could not be joined), and then the vias left with one connection.  Repeated until
    nothing is loose.  Supply and plane nets keep their vias (they meet a plane or a pour).  The items are removed
    at the very end - KiCad's Python objects are not reliable after a removal."""
    pads, tracks, vias = {}, {}, {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() > 0:
                pads.setdefault(pad.GetNetCode(), []).append(pad)
    for t in board.GetTracks():
        code = t.GetNetCode()
        if t.GetClass() == "PCB_VIA":
            try:
                d = t.GetWidth(pcbnew.F_Cu)
            except TypeError:
                d = t.GetWidth()
            vias.setdefault(code, []).append([t.GetPosition().x, t.GetPosition().y, d / 2, t, True])
        else:
            # (the hub's finger stubs, tools/hub_board.py, end at the card edge on purpose: kept, never dropped)
            keep = cpmodel.VARIANT == "hub" and min(ToMM(t.GetStart().x), ToMM(t.GetEnd().x)) < HUB_FACE
            tracks.setdefault(code, []).append([t.GetLayer(), t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth() / 2, t, True, keep])
    drop = []

    def on_seg(px, py, s_):
        ax, ay, bx, by = s_[1], s_[2], s_[3], s_[4]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        u = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        qx, qy = ax + u * dx - px, ay + u * dy - py
        return qx * qx + qy * qy <= (s_[5] + 2000) ** 2

    for code in sorted(tracks):
        name = r.name_of.get(code, "")
        if code <= 0 or name in PLANES:
            continue
        keep_vias = is_power(name, r.cls_of.get(code, ""))
        tl, vl, pl = tracks[code], vias.get(code, []), pads.get(code, [])
        changed = True
        while changed:
            changed = False
            for s_ in tl:
                if not s_[7] or s_[8]:
                    continue
                for px, py in ((s_[1], s_[2]), (s_[3], s_[4])):
                    ok = any(v[4] and (v[0] - px) ** 2 + (v[1] - py) ** 2 <= v[2] ** 2 for v in vl)
                    ok = ok or any(o is not s_ and o[7] and o[0] == s_[0] and on_seg(px, py, o) for o in tl)
                    ok = ok or any(p_.IsOnLayer(s_[0]) and p_.HitTest(VECTOR2I(px, py), 2000) for p_ in pl)
                    if not ok:
                        s_[7] = False
                        changed = True
                        break
                if s_[7] and (s_[1] - s_[3]) ** 2 + (s_[2] - s_[4]) ** 2 < 600000 ** 2:
                    for p_ in pl:
                        if p_.IsOnLayer(s_[0]) and p_.HitTest(VECTOR2I(s_[1], s_[2]), 2000) and p_.HitTest(VECTOR2I(s_[3], s_[4]), 2000):
                            others = any(o is not s_ and o[7] and o[0] == s_[0] and (on_seg(s_[1], s_[2], o) or on_seg(s_[3], s_[4], o)) for o in tl)
                            if not others and not any(v[4] and ((v[0] - s_[1]) ** 2 + (v[1] - s_[2]) ** 2 <= v[2] ** 2 or (v[0] - s_[3]) ** 2 + (v[1] - s_[4]) ** 2 <= v[2] ** 2) for v in vl):
                                s_[7] = False
                                changed = True
                            break
            if keep_vias:
                continue
            for v in vl:
                if not v[4]:
                    continue
                layers = {s_[0] for s_ in tl if s_[7] and ((s_[1] - v[0]) ** 2 + (s_[2] - v[1]) ** 2 <= v[2] ** 2
                                                         or (s_[3] - v[0]) ** 2 + (s_[4] - v[1]) ** 2 <= v[2] ** 2)}
                for p_ in pl:
                    if p_.HitTest(VECTOR2I(v[0], v[1]), 2000):
                        layers |= {l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if p_.IsOnLayer(l)}
                if len(layers) < 2:
                    v[4] = False
                    changed = True
        drop += [s_[6] for s_ in tl if not s_[7]] + [v[3] for v in vl if not v[4]]
    r.log.append("prune: %d loose tracks and vias removed" % len(drop))
    print(r.log[-1], flush=True)
    for it in drop:
        board.Remove(it)
    return dict(removed=len(drop))


def stage_finish(board, r, before):
    add_zone(board, "GND", pcbnew.In1_Cu, PLANE_GND, "GND plane L2")
    if STRIP:
        add_zone(board, "VCC5V_BUS", pcbnew.In2_Cu, PLANE_5V, "5V bus plane L3")
    else:
        add_zone(board, "GND", pcbnew.In4_Cu, PLANE_GND, "GND plane L5")
        add_zone(board, "VCC5V_BUS", pcbnew.In3_Cu, PLANE_5V, "5V bus plane L4")
    # The 5 V output path carries more than 4 A: besides the routed tracks, each of its nets gets a copper pour on
    # every outer layer where it has two pads or more, limited to the secondary side.
    pour_y0 = CFG["PRI_Y1"] + BARRIER + 0.3
    for prio, name in enumerate(("VOUT_5V", "VOUT_5V_PRE", "POE_SEC"), 2):
        if board.FindNet(name) is None:
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            boxes = []
            for fp in board.GetFootprints():
                for pad in fp.Pads():
                    if pad.GetNetname() == name and pad.IsOnLayer(layer):
                        bb = pad.GetBoundingBox()
                        bx = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
                        if bx[3] <= 60.3 and bx[0] >= -1 and bx[2] <= CFG["COL_W"] + 0.5 and bx[1] >= pour_y0:
                            boxes.append(bx)
            if len(boxes) < 2:
                continue
            xa, ya = min(b_[0] for b_ in boxes) - 0.4, max(pour_y0, min(b_[1] for b_ in boxes) - 0.4)
            xb, yb = max(b_[2] for b_ in boxes) + 0.4, max(b_[3] for b_ in boxes) + 0.4
            add_zone(board, name, layer, [(xa, ya), (xb, ya), (xb, yb), (xa, yb)],
                     f"{name} pour {board.GetLayerName(layer)}", prio=prio)
    poured = [] if STRIP else power_pours(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)

    # ---- the report: every stage's own account, then the totals from the board ----
    st = {}
    for name in STAGES:
        if os.path.exists(stage_file(name)):
            st[name] = json.load(open(stage_file(name), encoding="utf-8"))
    ntr = nvia = 0
    length = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            nvia += 1
        else:
            ntr += 1
            length[t.GetNetname()] = length.get(t.GetNetname(), 0.0) + ToMM(t.GetLength())
    failed = [f for name in STAGES for f in st.get(name, {}).get("failed", [])]
    lines = [
        cpmodel.PRJ + " - scripted routing (generated by tools/route.py)",
        "",
        "stack-up roles : " + ("F.Cu signal | In1 GND | In2 power | B.Cu signal" if STRIP else "F.Cu signal | In1 GND | In2 signal | In3 power | In4 GND | B.Cu signal"),
        "planes poured  : " + ("GND on In1, VCC5V_BUS on In2" if STRIP else "GND on In1 + In4, VCC5V_BUS on In3") + ", SELV area only",
        "supply pours   : " + (", ".join(poured) + "  (In3, core and front of the column)" if poured else "none"),
        f"tracks: {ntr}   vias: {nvia}   track length: {sum(length.values()):.0f} mm",
        f"unrouted connections (ratsnest): {before} before -> {after} after",
        "",
        "NOT routed on purpose: the memory bus (class " + ", ".join(sorted(SKIP_CLASSES)) + ").",
        "",
        "stages:",
    ]
    for name in STAGES:
        d = st.get(name)
        if d and name not in ("clean", "finish", "prune"):
            lines.append("  %-7s complete %4d   incomplete %4d   plane vias %4d (none for %d)   %4.0f s" % (
                name, len(d.get("done", [])), len(d.get("part", [])), d.get("fan_ok", 0), len(d.get("fan_bad", [])), d.get("seconds", 0)))
    pairs = [p_ for name in STAGES for p_ in st.get(name, {}).get("pairs", [])]
    if pairs:
        lines += ["", "differential pairs: coupled trunk (two parallel tracks), and the total routed length of each net",
                  "  (a pair listed twice was routed in two legs: strip, then column)"]
        for regname, pn, nn, tr in pairs:
            what = "trunk %6.1f / %6.1f mm, %d layer changes" % tuple(tr) if isinstance(tr, list) else "no trunk: " + str(tr)
            lp, ln = length.get(pn, 0.0), length.get(nn, 0.0)
            lines.append(f"  {regname:6s} {pn:20s} {what:48s} total {lp:6.1f} / {ln:6.1f} mm, difference {abs(lp - ln):5.2f}")
    lines += ["", f"FAILED ({len(failed)}):"] + ["  " + f for f in failed] + [""]
    for name in STAGES:
        lines += st.get(name, {}).get("log", [])
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    open(os.path.join(ROOT, "build", "routing_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(lines[:lines.index(f"FAILED ({len(failed)}):") + 1]))
    drop_dangling(board)        # (last: KiCad's Python objects are not reliable after items have been removed)


def run_stage(stage, path):
    t00 = time.time()
    board = pcbnew.LoadBoard(path)
    out = dict(stage=stage)
    if stage == "clean":
        board.BuildConnectivity()
        out["before"] = board.GetConnectivity().GetUnconnectedCount(True)
        roles = (((pcbnew.In1_Cu, pcbnew.LT_POWER), (pcbnew.In2_Cu, pcbnew.LT_POWER), (pcbnew.F_Cu, pcbnew.LT_SIGNAL), (pcbnew.B_Cu, pcbnew.LT_SIGNAL))
                 if STRIP else
                 ((pcbnew.In1_Cu, pcbnew.LT_POWER), (pcbnew.In3_Cu, pcbnew.LT_POWER), (pcbnew.In4_Cu, pcbnew.LT_POWER),
                  (pcbnew.F_Cu, pcbnew.LT_SIGNAL), (pcbnew.In2_Cu, pcbnew.LT_SIGNAL), (pcbnew.B_Cu, pcbnew.LT_SIGNAL)))
        for layer, kind in roles:
            board.SetLayerType(layer, kind)
        old = list(board.GetTracks()) + [z for z in board.Zones()]      # (nothing but saving after this: see the note in main)
        for it in old:
            board.Remove(it)
        pcbnew.SaveBoard(path, board)
        json.dump(out, open(stage_file(stage), "w", encoding="utf-8"))
        return
    r = Router(board)
    passes = int(os.environ.get("CP_PASSES", "4"))
    if os.environ.get("CP_PAIRS_ONLY"):         # (for trying things out: differential pairs only, no planes)
        SKIP_CLASSES.update({"Default", "PWR", "PWR_5V", "RGMII", "POE_PRIMARY"})
        PLANES.clear()
    if stage == "local":
        nets_done, nets_part, fan_ok, fan_bad = r.run(passes=passes)
        out.update(done=nets_done, part=nets_part, fan_ok=fan_ok, fan_bad=fan_bad)
        r.failed += fan_bad
    elif stage == "links":
        out.update(stage_links(board, r))
    elif stage == "ports":
        out.update(stage_ports(board, r))
    elif stage == "escape":
        out.update(stage_escape(board, r))
    elif stage == "power":
        out.update(stage_power(board, r))
    elif stage == "unzone":                 # by hand, before running stages again on a finished board
        old = [z for z in board.Zones()]
        for it in old:
            board.Remove(it)
        pcbnew.SaveBoard(path, board)
        return
    elif stage == "prune":
        r.log = []
        out.update(stage_prune(board, r))
    elif stage == "column":
        REGIONS[:] = [COLUMN]
        nets_done, nets_part, fan_ok, fan_bad = r.run(passes=min(passes, int(os.environ.get("CP_COLUMN_PASSES", "2"))))
        out.update(done=nets_done, part=nets_part, fan_ok=fan_ok, fan_bad=fan_bad)
        r.failed += fan_bad
    elif stage == "finish":
        before = json.load(open(stage_file("clean"), encoding="utf-8"))["before"] if os.path.exists(stage_file("clean")) else -1
        stage_finish(board, r, before)
    pcbnew.SaveBoard(path, board)
    out.update(failed=r.failed, log=r.log, pairs=r.pairs, seconds=time.time() - t00)
    json.dump(out, open(stage_file(stage), "w", encoding="utf-8"))


def main():
    """Runs the stages one after the other, each in a process of its own: the escape stage needs a finer grid (the
    grid is fixed when the module loads), and KiCad's Python objects do not survive the removal of many board items."""
    path = os.environ.get("CP_PCB") or os.path.join(ROOT, cpmodel.PRJ + ".kicad_pcb")
    if "--stage" in sys.argv:
        run_stage(sys.argv[sys.argv.index("--stage") + 1], path)
        return
    t00 = time.time()
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    stages = [s_ for s_ in STAGES if not (STRIP and s_ in ("escape", "links", "power"))]
    if "--from" in sys.argv:                    # resume: python route.py --from column
        stages = stages[stages.index(sys.argv[sys.argv.index("--from") + 1]):]
    for name in stages:
        if os.path.exists(stage_file(name)):
            os.remove(stage_file(name))
    for name in stages:
        env = dict(os.environ, CP_PCB=path)
        if name in STAGE_GRID:
            env["CP_GRID"] = STAGE_GRID[name]
        else:
            env.pop("CP_GRID", None)
        t0 = time.time()
        with open(stage_file(name).replace(".json", ".err"), "w", encoding="utf-8") as ferr:      # (KiCad's Python is noisy on stderr)
            rc_ = subprocess.run([sys.executable, os.path.abspath(__file__), "--stage", name], env=env, stderr=ferr).returncode
        print("stage %s: %.0f s%s" % (name, time.time() - t0, "" if rc_ == 0 else "  FAILED (exit %d)" % rc_), flush=True)
        if rc_ != 0:
            raise SystemExit("routing stage '%s' failed - run it alone to see why:  route.py --stage %s" % (name, name))
    print(f"total {time.time() - t00:.0f} s")


if __name__ == "__main__":
    main()
