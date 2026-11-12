#!/usr/bin/env python
"""Builds commander_mainboard.kicad_pcb from the design model.  Run with KiCad's own Python:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/gen_pcb.py

What it produces (revision A0, for audit):
  * the L-shaped outline with the rear I/O tab, taken from the customer drawing (see CFG)
  * every footprint, with its nets, linked to its schematic symbol
  * a first placement:
      - the RK3566 / LPDDR4 / PMIC core keeps the placement of the Radxa ZERO 3E V1.2
        (positions and package sizes recovered from Radxa's published placement drawings),
        rotated into the column
      - the Ethernet front end keeps the Radxa placement around the sunk RJ45
      - PoE, hubs, the nine bays, eMMC, microSD are packed into their zones
  * isolation barrier, zones and assumptions drawn on the user layers
The board is NOT routed.  Parts that did not fit their zone are parked below the board and
listed in build/placement_report.txt.
"""
import json
import math
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                      # noqa: E402
from gen_schematic import uid       # noqa: E402

ROOT = cpmodel.ROOT
KLIB = os.environ.get("KICAD10_FOOTPRINT_DIR", r"C:/Program Files/KiCad/10.0/share/kicad/footprints")
NL = chr(10)

# --------------------------------------------------------------------------
# geometry (mm).  Origin = top-left corner of the codec column in the customer drawing,
# +x towards the bays, +y towards the front of the device (KiCad convention, y down).
# --------------------------------------------------------------------------
CFG = dict(
    PAGE=(40.0, 70.0),      # where the origin sits on the A3 page
    COL_W=30.00,            # codec column width  (= Radxa ZERO 3E width)
    COL_L=118.66,           # codec column length (drawing)
    STRIP_Y=11.30,          # ASSUMED: offset of the bay strip below the column top (scaled from the drawing, +-0.5)
    STRIP_H=21.72,          # bay strip height (drawing)
    STRIP_L=294.73,         # bay strip length from the column edge = 246.54 + 32.45 + 15.74 (drawing)
    BAY_X0=19.39,           # first bay centre from the column edge = 246.54 - 7 * 32.45
    BAY_PITCH=32.45,        # bay pitch (drawing) - Framework expansion cards are 30 mm wide
    TAB_RJ45=14.20,         # rear tab under the RJ45: jack face lands on the rear panel plane (20.6 mm behind the column top)
    TAB_HDMI=19.60,         # rear tab under the micro HDMI
    TAB_SPLIT=12.00,        # x where the two tab depths meet
    RJ45_X=20.50,           # centre line of the RJ45
    CORE_Y0=60.0,           # where Radxa x = CORE_XR0 lands
    CORE_XR0=19.0,          # Radxa parts with x >= this are transplanted as the codec core
    BATT_X=8.0,             # centre line of the front battery-port USB-C
    # Head of the column, left to right: HDMI corridor | 2 mm barrier | PoE primary | 2 mm barrier | SELV corridor.
    # The right corridor is not optional: the bay strip joins the column on that edge.
    HDMI_COR=5.8,           # SELV on the left edge ends here (micro HDMI -> SoC)
    PRI_X0=8.0,             # PoE primary zone, centred under the RJ45
    PRI_X1=22.0,
    PRI_Y0=9.8,             # just below the Bob-Smith / chassis parts of the Ethernet front end
    PRI_Y1=39.4,            # the transformer primary pins sit right below
    SELV_COR=24.2,          # SELV on the right edge starts here (RGMII, USB, SD, 5 V to the strip)
)
OX, OY = CFG["PAGE"]
RADXA_RJ45_Y = 15.025       # centre of the RJ45 notch on the Radxa board


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY + y))


def core_xy(xr, yr):
    return yr, CFG["CORE_Y0"] + (xr - CFG["CORE_XR0"])


def eth_xy(xr, yr):
    return yr + (CFG["RJ45_X"] - RADXA_RJ45_Y), -CFG["TAB_RJ45"] + xr


def bay_x(k):
    return CFG["COL_W"] + CFG["BAY_X0"] + (k - 1) * CFG["BAY_PITCH"]


def outline_pts():
    """Board outline (design coordinates, mm), clockwise from the rear-left corner."""
    C = CFG
    s = C["RJ45_X"] - RADXA_RJ45_Y
    t = -C["TAB_RJ45"]
    sx1 = C["COL_W"] + C["STRIP_L"]
    sy = C["STRIP_Y"]
    return [
        (0, -C["TAB_HDMI"]), (C["TAB_SPLIT"], -C["TAB_HDMI"]), (C["TAB_SPLIT"], t),
        (7.57 + s, t), (7.57 + s, t + 3.66), (8.02 + s, t + 6.17), (22.03 + s, t + 6.17), (22.48 + s, t + 3.66), (22.48 + s, t),
        (C["COL_W"], t), (C["COL_W"], sy), (sx1, sy), (sx1, sy + C["STRIP_H"]),
        (C["COL_W"], sy + C["STRIP_H"]), (C["COL_W"], C["COL_L"]), (0, C["COL_L"]),
    ]


# --------------------------------------------------------------------------
def load_fp(libid):
    lib, name = libid.split(":", 1)
    path = os.path.join(ROOT, "lib", "commander.pretty") if lib == "commander" else os.path.join(KLIB, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {libid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def court(fp):
    """Courtyard bounding box (mm) of a footprint in its current pose, in design coordinates."""
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    c = fp.GetCourtyard(layer)
    bb = c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False)
    return (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)


def set_pose(fp, x, y, rot=0.0, bottom=False):
    if bottom != fp.IsFlipped():
        try:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        except (AttributeError, TypeError):
            fp.Flip(fp.GetPosition(), False)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))


def centre_on(fp, cx, cy):
    """Move so the courtyard centre (not the anchor) sits on cx, cy."""
    x0, y0, x1, y1 = court(fp)
    pos = fp.GetPosition()
    fp.SetPosition(VECTOR2I(pos.x + FromMM(cx - (x0 + x1) / 2), pos.y + FromMM(cy - (y0 + y1) / 2)))


def face_towards(fp, dx, dy):
    """Rotate a connector so that its mating face points in direction (dx, dy)."""
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        x0, y0, x1, y1 = court(fp)
        pads = [p for p in fp.Pads() if p.GetNumber() not in ("SH", "MP", "")]
        px = sum(ToMM(p.GetPosition().x) - OX for p in pads) / len(pads)
        py = sum(ToMM(p.GetPosition().y) - OY for p in pads) / len(pads)
        vx, vy = (x0 + x1) / 2 - px, (y0 + y1) / 2 - py      # contacts sit at the back of a receptacle
        score = vx * dx + vy * dy
        if best is None or score > best[0]:
            best = (score, rot)
    fp.SetOrientationDegrees(best[1])


class Packer:
    """Row packer for a rectangular zone; fills the top side first, then the bottom."""

    def __init__(self, name, x0, y0, x1, y1, sides=("F", "B"), gap=0.2, turn_wide=False):
        self.name, self.r, self.sides, self.gap = name, (x0, y0, x1, y1), list(sides), gap
        self.turn_wide = turn_wide          # stand parts on end when two of them would not fit side by side;
        self.used = {s: [] for s in sides}  # ... and, as a last resort, drop a part into any hole left between rows
        self.cur = {s: [x0, y0, 0.0] for s in sides}       # x cursor, row y, row height
        self.blocked = {s: [] for s in sides}

    def block(self, side, x0, y0, x1, y1):
        if side in self.blocked:
            self.blocked[side].append((x0, y0, x1, y1))

    def place(self, fp):
        x0, y0, x1, y1 = self.r
        for side in self.sides:
            set_pose(fp, 0, 0, 0, bottom=(side == "B"))
            c = court(fp)
            w, h = c[2] - c[0], c[3] - c[1]
            if (w > x1 - x0 and h <= x1 - x0) or (self.turn_wide and h < w and 2 * w + self.gap > x1 - x0):   # too wide: turn it
                fp.SetOrientationDegrees(90)
                c = court(fp)
                w, h = c[2] - c[0], c[3] - c[1]
            cx, ry, rh = self.cur[side]
            for _ in range(400):
                if cx + w > x1 + 1e-6:
                    cx, ry, rh = x0, ry + rh + self.gap, 0.0
                if ry + h > y1 + 1e-6:
                    break
                bx = (cx, ry, cx + w, ry + h)
                hit = [b for b in self.blocked[side] if not (bx[2] <= b[0] or bx[0] >= b[2] or bx[3] <= b[1] or bx[1] >= b[3])]
                if not hit:
                    centre_on(fp, cx + w / 2, ry + h / 2)
                    self.cur[side] = [cx + w + self.gap, ry, max(rh, h)]
                    self.used[side].append(bx)
                    return True
                cx = max(b[2] for b in hit) + self.gap
            self.cur[side] = [cx, ry, rh]
        if self.turn_wide:
            g = self.gap
            for side in self.sides:
                set_pose(fp, 0, 0, 0, bottom=(side == "B"))
                c = court(fp)
                w, h = c[2] - c[0], c[3] - c[1]
                taken = self.used[side] + self.blocked[side]
                yy = y0
                while yy + h <= y1 + 1e-6:
                    xx = x0
                    while xx + w <= x1 + 1e-6:
                        if not any(not (xx + w + g <= b[0] or xx - g >= b[2] or yy + h + g <= b[1] or yy - g >= b[3]) for b in taken):
                            centre_on(fp, xx + w / 2, yy + h / 2)
                            self.used[side].append((xx, yy, xx + w, yy + h))
                            return True
                        xx += 0.25
                    yy += 0.25
        return False


def match_pairs(refs, rpads, allowed, max_err=0.6, used=None):
    """Assign each two-terminal reference designator its pad pair in the Radxa pad drawing.

    The refdes anchors in the drawing are not always the part centre, so pairs are matched
    globally, closest first, each pad pair being used once.  'allowed(ref)' lists the pad
    separations that are plausible for that part, which keeps pads of two neighbouring
    parts (0.635 mm rows) from being mistaken for one part.  Returns
    ref -> (x, y, axis angle in degrees (Radxa frame), pad separation).
    """
    cand = []
    for ref, (side, xr, yr, _) in refs.items():
        seps = allowed(ref)
        near = [(k, p) for k, p in enumerate(rpads[side]) if abs(p[0] - xr) < 3.0 and abs(p[1] - yr) < 3.0]
        for i in range(len(near)):
            for j in range(i + 1, len(near)):
                (ka, a), (kb, b) = near[i], near[j]
                if abs(a[0] - b[0]) > 0.06 and abs(a[1] - b[1]) > 0.06:      # pads of one part are axis-aligned
                    continue
                sep = math.hypot(a[0] - b[0], a[1] - b[1])
                if not any(abs(sep - v) <= 0.07 for v in seps):
                    continue
                if abs(a[2] * a[3] - b[2] * b[3]) > 0.3 * max(a[2] * a[3], b[2] * b[3]):
                    continue
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                err = math.hypot(mx - xr, my - yr)
                if err <= max_err:
                    cand.append((err, sep, ref, side, ka, kb, mx, my, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))))
    cand.sort()
    used = set() if used is None else used
    out = {}
    for err, sep, ref, side, ka, kb, mx, my, ang in cand:
        if ref in out or (side, ka) in used or (side, kb) in used:
            continue
        used.add((side, ka))
        used.add((side, kb))
        out[ref] = (mx, my, ang, sep)
    return out, used


# --------------------------------------------------------------------------
def main():
    d = cpmodel.load()
    if d.errors:
        raise SystemExit(NL.join(d.errors))
    ref = json.load(open(os.path.join(ROOT, "src", "reference", "radxa_zero3e_placement.json")))
    rpos = {}
    for side in ("top", "bottom"):
        for r in ref[side]["refs"]:
            rpos[r[0]] = (side, r[1], r[2], r[3])
    rpads = {s: [p for p in ref[s]["pads"] if len(p) == 4] for s in ("top", "bottom")}
    two_pin = {c.ref for c in d.comps.values() if len(c.pins) == 2}

    # Pad-centre separations seen on the Radxa board: 0.50 (0201), 0.80 (0402), 1.40 (0603), 1.90 (0805 / 2520)
    def allowed(ref_):
        c = d.comps[ref_]
        v = c.value.upper()
        if c.kind == "R":
            return (1.4, 1.9, 2.9) if v.startswith("FB120R_3A") else (0.5, 0.8)
        if c.kind == "C":
            if v.startswith(("22UF", "10UF")):
                return (0.8, 1.4, 1.9)
            if v.startswith(("4.7UF", "2.2UF")):
                return (0.5, 0.8, 1.4)
            return (0.5, 0.8)
        if c.kind == "L":
            return (0.8, 1.4, 1.9, 2.1)
        if c.kind == "FB":
            return (0.5, 0.76, 0.8)
        return (0.5, 0.9, 1.3, 1.42, 1.74, 2.35)

    cands = {r: v for r, v in rpos.items() if r in two_pin}
    poses, used = match_pairs(cands, rpads, allowed)
    # second pass: whatever is still unassigned gets the nearest pair among the pads nobody claimed
    rest = {r: v for r, v in cands.items() if r not in poses}
    more, used = match_pairs(rest, rpads, lambda r_: (0.5, 0.8, 0.9, 1.4, 1.9), max_err=0.95, used=used)
    poses.update(more)

    board = pcbnew.BOARD()
    board.SetCopperLayerCount(6)
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = FromMM(0.09)
    ds.m_MinClearance = FromMM(0.09)
    ds.m_ViasMinSize = FromMM(0.40)
    ds.m_MinThroughDrill = FromMM(0.20)
    ds.m_CopperEdgeClearance = FromMM(0.25)
    ds.SetBoardThickness(FromMM(1.2))
    report = []

    # ---------------- outline ----------------
    C = CFG
    s = C["RJ45_X"] - RADXA_RJ45_Y
    t = -C["TAB_RJ45"]
    sx1 = C["COL_W"] + C["STRIP_L"]
    sy = C["STRIP_Y"]
    outline = outline_pts()
    for a, b in zip(outline, outline[1:] + outline[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(P(*a))
        seg.SetEnd(P(*b))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(FromMM(0.1))
        board.Add(seg)

    def note(txt, x, y, size=1.5, layer=pcbnew.Cmts_User, rot=0):
        tx = pcbnew.PCB_TEXT(board)
        tx.SetText(txt)
        tx.SetPosition(P(x, y))
        tx.SetLayer(layer)
        tx.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        tx.SetTextThickness(FromMM(size * 0.15))
        tx.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        tx.SetTextAngleDegrees(rot)
        board.Add(tx)

    def box(x0, y0, x1, y1, layer=pcbnew.Dwgs_User, width=0.15):
        r = pcbnew.PCB_SHAPE(board)
        r.SetShape(pcbnew.SHAPE_T_RECT)
        r.SetStart(P(x0, y0))
        r.SetEnd(P(x1, y1))
        r.SetLayer(layer)
        r.SetWidth(FromMM(width))
        board.Add(r)

    # ---------------- nets ----------------
    nets = {}
    for name in sorted(d.nets()):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni

    # ---------------- footprints ----------------
    fps = {}
    size_from_ref = 0
    chip = (cpmodel.FP_R0402, cpmodel.FP_C0402, cpmodel.FP_C0603, cpmodel.FP_C0805, cpmodel.FP_C1206)
    for c in d.comps.values():
        libid = c.fp
        # carried-over chip passives take the package size Radxa actually used
        if c.kind in ("R", "C") and c.ref in rpos and libid in chip:
            if c.ref in poses:
                sep = poses[c.ref][3]
                size = ("0201_0603Metric" if sep < 0.62 else "0402_1005Metric" if sep < 1.15 else
                        "0603_1608Metric" if sep < 1.75 else "0805_2012Metric")
                size_from_ref += 1
            else:
                # pad pair not identified: fall back to the size Radxa uses for that value class
                v = c.value.upper()
                size = ("0603_1608Metric" if v.startswith(("22UF", "10UF")) else
                        "0402_1005Metric" if v.startswith(("4.7UF", "2.2UF")) else "0201_0603Metric")
            libid = ("Resistor_SMD:R_" if c.kind == "R" else "Capacitor_SMD:C_") + size
        fp = load_fp(libid)
        fp.SetReference(c.ref)
        fp.SetValue("DNP" if c.dnp and c.kind in ("R", "C", "L", "FB", "F") else c.value)
        if c.dnp:
            fp.SetDNP(True)
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sheet', c.sheet)}/{uid('sym', (c.ref, 1))}"))
        fp.SetSheetname("/" + c.sheet + "/")
        fp.SetSheetfile(f"sheets/{c.sheet}.kicad_sch")
        if c.desc and hasattr(fp, "SetLibDescription"):
            fp.SetLibDescription(c.desc)
        fp.Reference().SetVisible(c.kind == "ic" or c.ref[0] in "JTYQ")
        padnames = {p.GetNumber() for p in fp.Pads()}
        for pin, net in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                if pad not in padnames:
                    report.append(f"PAD-MISSING {c.ref} ({libid}): schematic pin {pin} -> pad '{pad}' not on footprint")
                    continue
                if net is not None:
                    for p in fp.Pads():
                        if p.GetNumber() == pad:
                            p.SetNet(nets[net])
        board.Add(fp)
        fps[c.ref] = fp

    placed, parked = {}, []

    def put(ref_, x, y, rot=0.0, bottom=False, how="fixed"):
        set_pose(fps[ref_], x, y, rot, bottom)
        placed[ref_] = how

    def edge_mount(ref_, cx, edge_y, overhang, facing):
        """Connector centred on cx, mating face pointing along 'facing' (0,-1 = rear), courtyard overhanging the edge."""
        fp = fps[ref_]
        set_pose(fp, 0, 0)
        face_towards(fp, *facing)
        centre_on(fp, cx, 0)
        c0 = court(fp)
        if facing[1] < 0:
            dy = (edge_y - overhang) - c0[1]
        else:
            dy = (edge_y + overhang) - c0[3]
        fp.SetPosition(VECTOR2I(fp.GetPosition().x, fp.GetPosition().y + FromMM(dy)))
        placed[ref_] = "fixed"

    # ---------------- 1. rear I/O ----------------
    put("J12", C["RJ45_X"], -C["TAB_RJ45"], 0)
    edge_mount("J10", 6.0, -C["TAB_HDMI"], 0.9, (0, -1))

    # ---------------- 2. transplanted Radxa placement ----------------
    eth_extra = {}
    for i, yc in enumerate((11.76, 15.70, 19.64, 23.32)):      # one magnetics channel per row, bottom side
        eth_extra[("L15", "L23", "L25", "L27")[i]] = ("bottom", 13.3, yc, 0.0)
        eth_extra[("L22", "L24", "L26", "L28")[i]] = ("bottom", 18.0, yc, 0.0)
    transplanted = []
    for c in d.comps.values():
        if c.ref in placed:
            continue
        src = rpos.get(c.ref) or eth_extra.get(c.ref)
        if not src:
            continue
        if c.sheet == "ethernet":
            xf = eth_xy
        elif c.sheet in ("hdmi", "storage", "poe", "usb3_hub", "usb2_hub", "battery") or src[1] < C["CORE_XR0"]:
            continue
        else:
            xf = core_xy
        side, xr, yr, rr = src
        pose = poses.get(c.ref)
        if pose:
            xr, yr, rot = pose[0], pose[1], pose[2] - 90.0
        else:
            rot = rr - 90.0
        x, y = xf(xr, yr)
        how = "radxa (pads)" if pose else ("radxa (anchor)" if c.ref in rpos else "radxa (estimated)")
        put(c.ref, x, y, rot if side == "top" else -rot, bottom=(side == "bottom"), how=how)
        transplanted.append(c.ref)
    put("U1", *core_xy(28.194, 12.7), 180.0, how="radxa (anchor)")       # orientation solved from the ball map

    # ---------------- 3. zones ----------------
    VG = 0.6        # courtyard gap in the zones that get routed: leaves room for a via between neighbours
    Z = {
        "HDMI": Packer("HDMI", 0.6, -10.5, 11.6, 8.8),
        "POE_PRI": Packer("POE_PRI", C["PRI_X0"], C["PRI_Y0"], C["PRI_X1"], C["PRI_Y1"], turn_wide=True),
        "POE_SEC": Packer("POE_SEC", 23.5, 43.5, 29.4, 59.4),          # secondary side, right of the transformer
        "POE_SEC2": Packer("POE_SEC2", 0.8, 55.6, 23.0, 59.5),         # ... below it
        "POE_SEC3": Packer("POE_SEC3", 0.8, 41.5, C["HDMI_COR"], 55.2), # ... and left of it (HDMI passes underneath on B.Cu)
        "HUB3": Packer("HUB3", 30.8, sy + 0.8, 40.2, sy + 21.2, gap=VG),
        "MID12": Packer("MID12", 54.6, sy + 8.6, 77.0, sy + 21.2, gap=VG),
        "HUB2": Packer("HUB2", bay_x(5) + 9.5, sy + 1.0, bay_x(6) - 9.5, sy + 21.2, gap=VG),
        "EMMC": Packer("EMMC", 2.0, 86.0, 28.0, 105.6, sides=("B",)),
        "FRONT": Packer("FRONT", 0.8, 106.9, 29.2, 118.0, sides=("F", "B"), gap=0.45),
        "CHAS": Packer("CHAS", 12.2, 4.9, 22.0, 9.7),          # chassis bleed network, next to the RJ45 shield
    }
    for k in range(1, 10):
        Z[f"BAY{k}"] = Packer(f"BAY{k}", bay_x(k) - 9.0, sy + 9.4, bay_x(k) + 9.0, sy + 21.2, gap=VG)

    for k in range(1, 10):
        edge_mount(f"J3{k}", bay_x(k), sy, 0.8, (0, -1))
    put("T1", (C["PRI_X0"] + C["PRI_X1"]) / 2, 47.0, 180, bottom=True)   # bottom face (tallest part, about 12.7 mm); 180 deg keeps the primary pins towards the rear
    put("U31", (C["PRI_X1"] + C["SELV_COR"]) / 2, 35.5, 180)      # optocoupler and Y capacitor straddle the right barrier
    put("C518", (C["PRI_X1"] + C["SELV_COR"]) / 2, 31.6, 0)
    put("U20", 15.0, 96.0, 0, bottom=True)
    put("J21", 19.0, 116.6, 90)
    put("U40", 35.4, sy + 5.6, 0)
    put("U50", (bay_x(5) + bay_x(6)) / 2, sy + 11.0, 0)
    edge_mount("J6", 66.0, sy + C["STRIP_H"], 0.3, (0, 1))
    edge_mount("J40", C["BATT_X"], C["COL_L"], 0.9, (0, 1))      # front "TO BATT" USB-C
    for name in ("HUB3", "MID12", "HUB2", "EMMC", "POE_PRI", "POE_SEC", "POE_SEC2", "POE_SEC3", "CHAS", "FRONT"):
        for r_ in ("U40", "U50", "J6", "U20", "U31", "C518", "T1", "J21", "J40"):
            fp = fps[r_]
            Z[name].block("B" if fp.IsFlipped() else "F", *court(fp))
    for r_ in ("J40", "J21"):               # through-hole legs of the front connectors also occupy the bottom side
        for p in fps[r_].Pads():
            if p.HasHole():
                px_, py_ = ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY
                hw, hh = ToMM(p.GetSize().x) / 2 + 0.4, ToMM(p.GetSize().y) / 2 + 0.4
                hw = hh = max(hw, hh)
                Z["FRONT"].block("B", px_ - hw, py_ - hh, px_ + hw, py_ + hh)
    for k in range(1, 10):
        Z[f"BAY{k}"].block("F", *court(fps[f"J3{k}"]))
    for r_ in transplanted:                # keep the eMMC zone off the transplanted bottom-side parts
        fp = fps[r_]
        if fp.IsFlipped():
            Z["EMMC"].block("B", *court(fp))
        for zn in ("CHAS", "POE_PRI"):
            Z[zn].block("B" if fp.IsFlipped() else "F", *court(fp))

    sec_nets = ("VOUT_5V", "VOUT_5V_PRE", "FB_K", "FB_REF", "FB_COMP", "FB_LED_A", "POE_SNUB")

    def zone_of(c):
        m = re.match(r"^\d?[A-Z]+(\d+)$", c.ref)
        n = int(m.group(1)) if m else 0
        if c.ref in ("R400", "C400"):
            return "CHAS"
        if c.sheet == "hdmi":
            return "HDMI"
        if c.sheet == "poe":
            if c.ref in ("D41", "R510", "C510", "C511", "C512", "C513"):
                return "POE_SEC2"
            pri = any((net or "").startswith(("POE_", "TR")) for net in c.pins.values())
            sec = any(net in sec_nets for net in c.pins.values())
            return "POE_SEC" if sec or not pri else "POE_PRI"
        if c.sheet == "usb3_hub":
            return f"BAY{(n - 630) // 10}" if 640 <= n < 680 else "HUB3"
        if c.sheet == "battery":
            # the source selector sits at the PoE output; the port, its CC controller and charge switch at the front
            return "POE_SEC" if c.ref in ("U81", "TP7") or 811 <= n <= 818 else "FRONT"
        if c.sheet == "usb2_hub":
            if c.ref in ("J20", "F1", "C713", "U51"):
                return "MID12"
            return f"BAY{(n - 700) // 10}" if 750 <= n < 800 else "HUB2"
        if c.sheet == "storage":
            if c.ref in ("R137", "R90723", "C227") or re.match(r"^D1[3-9]$", c.ref):
                return "MID12"
            if c.ref in ("R401", "R402", "R403", "R404", "C401", "C402", "C403", "C404", "C405", "TP3"):
                return "EMMC"
        return "FRONT"

    overflow = {"HUB3": ["MID12"], "POE_SEC": ["POE_SEC2", "POE_SEC3"], "POE_SEC2": ["POE_SEC", "POE_SEC3"]}

    def area(c):
        b = court(fps[c.ref])
        return (b[2] - b[0]) * (b[3] - b[1])

    todo = sorted([c for c in d.comps.values() if c.ref not in placed], key=lambda c: -area(c))
    for c in todo:
        z = zone_of(c)
        ok = Z[z].place(fps[c.ref])
        for z2 in overflow.get(z, ()):
            if ok:
                break
            ok = Z[z2].place(fps[c.ref])
            if ok:
                z = z2
        if ok:
            placed[c.ref] = "zone " + z
        else:
            parked.append((c.ref, z))
    px, py, rowh = 40.0, 45.0, 0.0          # park what did not fit, in rows below the strip
    for r_, z in parked:
        fp = fps[r_]
        set_pose(fp, 0, 0, 0, False)
        c0 = court(fp)
        w, h = c0[2] - c0[0], c0[3] - c0[1]
        if px + w > 300:
            px, py, rowh = 40.0, py + rowh + 0.5, 0.0
        centre_on(fp, px + w / 2, py + h / 2)
        px += w + 0.5
        rowh = max(rowh, h)
        placed[r_] = "PARKED"

    # ---------------- 4. orientation refinement by net proximity ----------------
    def pad_pts(fp):
        return [(ToMM(p.GetPosition().x), ToMM(p.GetPosition().y), p.GetNetname()) for p in fp.Pads() if p.GetNetname()]

    big = {n for n, pins in d.nets().items() if len(pins) > 30}

    def net_index(skip):
        idx = {}
        for r_, fp in fps.items():
            if r_ == skip:
                continue
            for x, y, n in pad_pts(fp):
                if n not in big:
                    idx.setdefault(n, []).append((x, y))
        return idx

    def cost(fp, idx):
        tot = 0.0
        for x, y, n in pad_pts(fp):
            pts = idx.get(n)
            if pts:
                tot += min(math.hypot(x - a, y - b) for a, b in pts)
        return tot

    order = sorted(transplanted, key=lambda r_: -len(d.comps[r_].pins))
    for _ in range(2):
        for r_ in order:
            if r_ == "U1":
                continue
            fp = fps[r_]
            idx = net_index(r_)
            base = fp.GetOrientationDegrees()
            cands = (0, 180) if len(d.comps[r_].pins) == 2 else (0, 90, 180, 270)
            centre = fp.GetPosition()
            best = None
            for dr in cands:
                fp.SetOrientationDegrees(base + dr)
                fp.SetPosition(centre)
                cst = cost(fp, idx)
                if best is None or cst < best[0] - 1e-6:
                    best = (cst, base + dr)
            fp.SetOrientationDegrees(best[1])
            fp.SetPosition(centre)

    # the service USB-C must open onto the outer (left) edge of the column, whatever the net cost says
    fp = fps["J2"]
    face_towards(fp, -1, 0)
    c0 = court(fp)
    fp.SetPosition(VECTOR2I(fp.GetPosition().x + FromMM(-0.8 - c0[0]), fp.GetPosition().y))

    # ---------------- 5. mounting holes (provisional) ----------------
    holes = [core_xy(60.0, 3.433), core_xy(60.0, 26.333), (sx1 - 4.0, sy + 17.5)]
    holes += [((bay_x(k) + bay_x(k + 1)) / 2, sy + 4.0) for k in (2, 4, 6, 8)]
    for i, (hx, hy) in enumerate(holes, 1):
        fp = load_fp("MountingHole:MountingHole_2.7mm_M2.5")
        fp.SetReference(f"H{i}")
        fp.SetValue("M2.5 (position TBD by chassis)")
        fp.Reference().SetVisible(False)
        set_pose(fp, hx, hy)
        board.Add(fp)

    # ---------------- 6. documentation layers ----------------
    box(C["PRI_X0"], C["PRI_Y0"], C["PRI_X1"], C["PRI_Y1"])
    note("PoE PRIMARY (57 V)", C["PRI_X0"] + 0.2, C["PRI_Y0"] + 1.0, 0.8)
    for bx in (C["HDMI_COR"], C["SELV_COR"]):                 # the two barrier lines
        box(bx, C["PRI_Y0"] - 2.0, bx, 46.0, width=0.1)
    note("ISOLATION BARRIER: keep 2.0 mm clear on ALL layers around the primary zone." + NL +
         "Only T1, U31 and C518 may bridge it.", 32.0, 40.0, 1.2)
    note("SELV corridor: RGMII, USB, SD, 5 V", 29.4, 58.0, 0.8, rot=90)
    note("HDMI corridor", 2.0, 40.0, 0.8, rot=90)
    box(0.0, C["CORE_Y0"], C["COL_W"], C["CORE_Y0"] + 65.0 - C["CORE_XR0"])
    note("CODEC CORE - placement transplanted from Radxa ZERO 3E V1.2 (rotated 90 deg)", -1.0, 106.0, 1.0, rot=90)
    for k in range(1, 10):
        note(f"BAY {k} " + ("USB 3.2 Gen 1" if k <= 4 else "USB 2.0"), bay_x(k) - 8.0, sy + 23.3, 1.0)
        box(bay_x(k) - 15.0, sy - 32.0, bay_x(k) + 15.0, sy, width=0.1)
    note("Framework expansion card envelope (30 x 32 mm) - rear panel plane at the top edge of these boxes", bay_x(1) - 15.0, sy - 34.0, 1.2)
    note("COMMANDER MAINBOARD rev A0 - PLACED, NOT ROUTED - for audit." + NL +
         "Outline from the customer drawing: column 30 x 118.66, strip 294.73 x 21.72, bays at 19.39 + n x 32.45." + NL +
         "ASSUMED: strip offset 11.30 below column top; rear tab depths 14.2 (RJ45) / 19.6 (HDMI); mounting holes." + NL +
         "6-layer, 1.2 mm.  See DESIGN_NOTES.md.", 60.0, 62.0, 2.0)

    # ---------------- save + report ----------------
    out = os.path.join(ROOT, "commander_mainboard.kicad_pcb")
    pcbnew.SaveBoard(out, board)
    txt = open(out, encoding="utf-8").read().replace('(paper "A4")', '(paper "A3")', 1)
    open(out, "w", encoding="utf-8", newline=NL).write(txt)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    hows = {}
    for r_, h in placed.items():
        hows[h] = hows.get(h, 0) + 1
    lines = [f"footprints: {len(fps)}   nets: {len(nets)}",
             f"chip passives sized from the Radxa pad drawing: {size_from_ref}",
             f"two-terminal parts positioned from Radxa pad pairs: {len([r for r in transplanted if r in poses])}"]
    lines += [f"  {hows[k]:4d}  {k}" for k in sorted(hows)]
    lines += ["", f"PARKED outside the board ({len(parked)}):"] + [f"  {r_:8s} wanted zone {z}" for r_, z in parked]
    lines += ["", f"footprint / symbol mismatches ({len(report)}):"] + ["  " + l for l in report]
    open(os.path.join(ROOT, "build", "placement_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    json.dump(placed, open(os.path.join(ROOT, "build", "placement.json"), "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("saved", out)
    print(NL.join(lines[:3 + len(hows)]))
    print("parked:", " ".join(r_ for r_, z in parked))
    print("pad mismatches:", len(report))


if __name__ == "__main__":
    main()
