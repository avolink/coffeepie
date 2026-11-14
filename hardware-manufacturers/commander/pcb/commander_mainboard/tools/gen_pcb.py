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
    HUB_HALO=dict(U40=4.0, U50=3.0),    # mm kept free of parts around each USB hub, both faces (room for the pairs to change layer)
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
    PRI_Y1=41.4,            # the transformer primary pins sit right below
    SELV_COR=24.2,          # SELV on the right edge starts here (RGMII, USB, SD, 5 V to the strip)
    # The transformer (Bourns PLN060, bottom face) has its primary / auxiliary pad row 17.8 mm wide - wider than the
    # primary zone - so at that row the two SELV corridors step back to keep 2 mm from it.
    T1_Y=47.0,              # transformer centre; primary row at T1_Y - 11.2, secondary row at T1_Y + 10.0
    NOTCH_XL=4.1,           # SELV limit on the left while passing the primary pad row
    NOTCH_XR=25.9,          # ... and on the right
)
STRIP = cpmodel.VARIANT == "strip"      # strip test board: PoE + hubs + bays + battery port, no codec core
# The case is sealed and fanless, with the heatsink in the bottom of the chassis: the codec core is built as the
# MIRROR IMAGE of Radxa's placement, so the RK3566, the LPDDR4 and the RK817 face down onto the aluminium
# and their decoupling ends up on the top face.  Set to False to get Radxa's own orientation back.
CORE_ON_BOTTOM = os.environ.get("CP_CORE_TOP") != "1"     # CP_CORE_TOP=1 rebuilds the un-mirrored reference for checking
CFG["FRONT_Y0"] = 106.9                 # where the front (battery-port) zone starts
# Clearances of the case, from the prototype (2026-11-13): about 3 mm above the board, about 10 mm below it.
# The heatsink plate carries a 6 mm pedestal that meets the chips (1.0 - 1.2 mm tall), so over the plate the
# free height under the board is about 7 mm.
CFG["NOTCH_Y0"] = CFG["T1_Y"] - 11.225 - 1.125 - 2.0     # the stretch of the column where the corridors step back
CFG["NOTCH_Y1"] = CFG["T1_Y"] - 11.225 + 1.125 + 2.0
CFG["CLEAR_TOP"] = 3.0
CFG["CLEAR_BOTTOM"] = 10.0
CFG["PEDESTAL"] = 6.0
CFG["CLEAR_OVER_PLATE"] = 7.0           # pedestal + chip
# The two USB-C ports on the inner (right) edge of the column, side by side, starting just in front of the SoC.
# Their shield legs go through the board, so they may not stand over a chip on the other face: with the core on
# the bottom the LPDDR4 ends at x 22.8 and the PMIC at x 18.5, which leaves the legs (x 24.7 and beyond) clear.
# Beside the SoC itself (y 61.7 - 76.7, out to x 25.3) there is no room for them.
CFG["SVC_Y"] = 83.0                     # service (flashing) USB-C
CFG["KB_Y"] = 94.0                      # keyboard USB-C
CFG["PWR_BTN_Y"] = 8.0                  # power button on the left edge, beside the PoE block (where the user marked it)
CFG["EMMC_X"] = 14.0                    # eMMC centre: 1 mm left of Radxa's microSD position, to clear the keyboard port
if STRIP:
    CFG.update(COL_L=72.0, TAB_RJ45=0.0, TAB_HDMI=0.0, FRONT_Y0=60.6)
SVC_REFS = ("J2", "L9", "D3", "D4", "D5", "D30", "R909", "R910", "C149", "R108", "R109", "R111", "R33", "R110", "R112", "TP2")   # service-port parts follow the connector
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


# Corner radii (mm).  JLCPCB's guidance for rounded outlines: outer corners R3 - R5 on boards over 100 mm;
# an inside corner can never be sharper than the router bit, so it is drawn with an explicit radius.
R_OUT = 3.0         # free outer corners
R_TAB = 1.0         # outer corners that have an edge-mounted connector right next to them (rear tab)
R_IN = 1.0          # inside corners (the two where the strip meets the column): fits a 2 mm router bit
R_NOTCH = 0.5       # the RJ45 notch: smallest radius a 1 mm bit can cut


def outline_corners():
    """Board outline as (x, y, corner radius), clockwise from the rear-left corner (design mm)."""
    C = CFG
    s = C["RJ45_X"] - RADXA_RJ45_Y
    t = -C["TAB_RJ45"]
    w, sx1, sy, h, cl = C["COL_W"], C["COL_W"] + C["STRIP_L"], C["STRIP_Y"], C["STRIP_H"], C["COL_L"]
    if STRIP:
        return [(0, 0, R_OUT), (w, 0, R_OUT), (w, sy, R_IN), (sx1, sy, R_OUT), (sx1, sy + h, R_OUT),
                (w, sy + h, R_IN), (w, cl, R_OUT), (0, cl, R_OUT)]
    return [
        (0, -C["TAB_HDMI"], R_TAB), (C["TAB_SPLIT"], -C["TAB_HDMI"], R_TAB), (C["TAB_SPLIT"], t, R_NOTCH),
        (7.57 + s, t, R_NOTCH), (7.57 + s, t + 3.66, R_NOTCH), (8.02 + s, t + 6.17, R_NOTCH),
        (22.03 + s, t + 6.17, R_NOTCH), (22.48 + s, t + 3.66, R_NOTCH), (22.48 + s, t, R_NOTCH),
        (w, t, R_TAB), (w, sy, R_IN), (sx1, sy, R_OUT), (sx1, sy + h, R_OUT),
        (w, sy + h, R_IN), (w, cl, R_OUT), (0, cl, R_OUT),
    ]


def outline_shapes():
    """The rounded outline as drawing primitives: ("arc", start, mid, end, centre, radius) and ("seg", a, b)."""
    c = outline_corners()
    n = len(c)
    arcs = []
    for i, (x, y, r) in enumerate(c):
        px, py, _ = c[i - 1]
        qx, qy, _ = c[(i + 1) % n]
        l1, l2 = math.hypot(px - x, py - y), math.hypot(qx - x, qy - y)
        u1, u2 = ((px - x) / l1, (py - y) / l1), ((qx - x) / l2, (qy - y) / l2)
        phi = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
        d = r / math.tan(phi / 2)                       # corner to tangent point
        bl = math.hypot(u1[0] + u2[0], u1[1] + u2[1])
        bis = ((u1[0] + u2[0]) / bl, (u1[1] + u2[1]) / bl)
        cc = r / math.sin(phi / 2)                      # corner to arc centre
        centre = (x + bis[0] * cc, y + bis[1] * cc)
        arcs.append(((x + u1[0] * d, y + u1[1] * d), (centre[0] - bis[0] * r, centre[1] - bis[1] * r),
                     (x + u2[0] * d, y + u2[1] * d), centre, r))
    out = []
    for i in range(n):
        out.append(("arc",) + arcs[i])
        out.append(("seg", arcs[i][2], arcs[(i + 1) % n][0]))
    return out


def outline_pts(nseg=8):
    """The rounded outline as a polygon (arcs approximated), for rasterising and area tests."""
    pts = []
    for sh in outline_shapes():
        if sh[0] != "arc":
            continue
        _, a, _, b, c, r = sh
        a1, a2 = math.atan2(a[1] - c[1], a[0] - c[0]), math.atan2(b[1] - c[1], b[0] - c[0])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        pts += [(c[0] + r * math.cos(a1 + da * k / nseg), c[1] + r * math.sin(a1 + da * k / nseg)) for k in range(nseg + 1)]
    return pts


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


FINE_BAND = 0.0     # mm kept free round a fine-pitch chip that the packer places (its pins' way out).  1.0-1.4 frees the
                    # TPS23754's pins, but the PoE primary area is then too small for the rest (C516, D42 left over): off


def fine_pitch(fp):
    """A chip with pads 0.65 mm apart or closer (QFN, TSSOP...)."""
    pts = [(p.GetPosition().x, p.GetPosition().y) for p in fp.Pads() if p.GetNumber() not in ("", "EP") and not p.HasHole()]
    if len(pts) < 8:
        return False
    best = min(math.hypot(a[0] - b[0], a[1] - b[1]) for k, a in enumerate(pts) for b in pts[k + 1:])
    return 0 < ToMM(best) <= 0.66


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

    def place(self, fp, first=None):
        """first: the face to try first (e.g. "B" for a part that is too tall for the top face)."""
        ok = self._place(fp, first)
        if ok and fine_pitch(fp):           # a fine-pitch chip: its pins need a free band to leave by, on each side that has pins
            side = "B" if fp.IsFlipped() else "F"
            c = court(fp)
            m = FINE_BAND
            pins = [p for p in fp.Pads() if not p.HasHole() and ToMM(p.GetSize().x) * ToMM(p.GetSize().y) < 1.0]
            for edge in range(4):
                near = [p for p in pins if abs((ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY)[edge % 2] - c[edge]) < 1.2]
                if len(near) >= 3:
                    bx = list(c)
                    bx[edge] = c[edge] + (m if edge >= 2 else -m)
                    bx[(edge + 2) % 4] = c[edge]
                    self.blocked[side].append(tuple(min(bx[k], bx[k + 2]) if k < 2 else max(bx[k - 2], bx[k]) for k in range(4)))
        return ok

    def _place(self, fp, first=None):
        x0, y0, x1, y1 = self.r
        order_ = self.sides if first not in self.sides else [first] + [s_ for s_ in self.sides if s_ != first]
        for side in order_:
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
                            self.blocked[side].append((xx - g, yy - g, xx + w + g, yy + h + g))      # the rows that follow must go round it
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
    if STRIP:
        ref = {s: {"refs": [], "pads": []} for s in ("top", "bottom")}
    else:
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
    board.SetCopperLayerCount(4 if STRIP else 6)
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
    for sh in outline_shapes():
        seg = pcbnew.PCB_SHAPE(board)
        if sh[0] == "arc":
            seg.SetShape(pcbnew.SHAPE_T_ARC)
            seg.SetArcGeometry(P(*sh[1]), P(*sh[2]), P(*sh[3]))
        else:
            if math.hypot(sh[1][0] - sh[2][0], sh[1][1] - sh[2][1]) < 1e-6:
                continue
            seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
            seg.SetStart(P(*sh[1]))
            seg.SetEnd(P(*sh[2]))
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
        if facing[0]:                       # left / right edge: cx is the position along the edge (y), edge_y the edge x
            centre_on(fp, 0, cx)
            c0 = court(fp)
            dx = (edge_y - overhang) - c0[0] if facing[0] < 0 else (edge_y + overhang) - c0[2]
            fp.SetPosition(VECTOR2I(fp.GetPosition().x + FromMM(dx), fp.GetPosition().y))
            placed[ref_] = "fixed"
            return
        centre_on(fp, cx, 0)
        c0 = court(fp)
        if facing[1] < 0:
            dy = (edge_y - overhang) - c0[1]
        else:
            dy = (edge_y + overhang) - c0[3]
        fp.SetPosition(VECTOR2I(fp.GetPosition().x, fp.GetPosition().y + FromMM(dy)))
        placed[ref_] = "fixed"

    # ---------------- 1. rear I/O ----------------
    def put_c(ref_, cx, cy, rot=0.0):
        """Fixed part with its courtyard centre (not its anchor) on cx, cy."""
        put(ref_, 0, 0, rot)
        centre_on(fps[ref_], cx, cy)

    if not STRIP:
        put("J12", C["RJ45_X"], -C["TAB_RJ45"], 0)
        edge_mount("J10", 6.0, -C["TAB_HDMI"], 0.9, (0, -1))
        # both USB-C ports that a technician or the keyboard plug into open onto the inner (right) edge
        edge_mount("J2", C["SVC_Y"], C["COL_W"], 0.9, (1, 0))
        edge_mount("J20", C["KB_Y"], C["COL_W"], 0.9, (1, 0))
        if "SW3" in fps:                    # power button: body 0.1 mm inside the left edge, the actuator stands out 0.55 mm
            edge_mount("SW3", C["PWR_BTN_Y"], 0.0, 0.8, (-1, 0))      # (0.8: its ground pads keep 0.25 mm from the edge)

    # ---------------- 2. transplanted Radxa placement ----------------
    eth_extra = {}
    for i, yc in enumerate((11.76, 15.70, 19.64, 23.32)):      # one magnetics channel per row, bottom side
        eth_extra[("L15", "L23", "L25", "L27")[i]] = ("bottom", 13.3, yc, 0.0)
        eth_extra[("L22", "L24", "L26", "L28")[i]] = ("bottom", 18.0, yc, 0.0)
    transplanted = []
    core_refs = []
    for c in d.comps.values():
        if c.ref in placed or c.ref in SVC_REFS:
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
        if xf is core_xy:
            core_refs.append(c.ref)
    if not STRIP:
        put("U1", *core_xy(28.194, 12.7), 180.0, how="radxa (anchor)")   # orientation solved from the ball map
        if "U1" not in core_refs:
            core_refs.append("U1")
    if CORE_ON_BOTTOM:
        # flip every core part about the centre line of the column: x -> COL_W - x, side swapped, pads mirrored.
        # The block keeps its internal geometry exactly; only its handedness changes.
        axis = FromMM(OX + C["COL_W"] / 2)
        for r_ in core_refs:
            fp = fps[r_]
            fp.Flip(VECTOR2I(axis, fp.GetPosition().y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

    # ---------------- 3. zones ----------------
    VG = 0.6        # courtyard gap in the zones that get routed: leaves room for a via between neighbours
    Z = {
        "HDMI": Packer("HDMI", 0.6, -10.5, 11.6, 8.8),
        # (57 V between neighbours here: the gap leaves room for a 0.4 mm track with 0.3 mm either side)
        "POE_PRI": Packer("POE_PRI", C["PRI_X0"], C["PRI_Y0"], C["PRI_X1"], C["PRI_Y1"], turn_wide=True, gap=0.45),
        "POE_SEC": Packer("POE_SEC", 23.5, 43.5, 29.4, 59.4),          # secondary side, right of the transformer
        "POE_SEC2": Packer("POE_SEC2", 0.8, 55.6, 23.0, 59.5),         # ... below it
        "POE_SEC3": Packer("POE_SEC3", 0.8, 41.5, C["HDMI_COR"], 55.2), # ... and left of it (HDMI passes underneath on B.Cu)
        "POE_SEC4": Packer("POE_SEC4", 6.2, 46.5, 23.3, 55.4, sides=("F",)),   # ... and on the top face over the transformer's secondary half
        "HUB3": Packer("HUB3", 30.8, sy + 0.8, 40.2, sy + 21.2, gap=VG),
        "MID12": Packer("MID12", 58.9, sy + 8.6, 72.3, sy + 21.2, gap=VG),          # between bay 1 and bay 2
        "MID23": Packer("MID23", 91.2, sy + 8.6, 104.8, sy + 21.2, gap=VG),
        "SVC": Packer("SVC", 23.2, C["SVC_Y"] - 5.3, 29.4, C["SVC_Y"] + 5.3, sides=("B",), turn_wide=True),   # under the service port, beside the LPDDR4
        "KBZ": Packer("KBZ", 21.2, C["KB_Y"] - 5.3, 29.4, C["KB_Y"] + 5.3, sides=("B",), turn_wide=True),     # under the keyboard port
        "CORE_T": Packer("CORE_T", 0.8, 62.2, 9.2, 76.4, sides=("F",)),     # free top-side area beside the SoC's decoupling: overflow only
        "HUB2": Packer("HUB2", bay_x(5) + 9.5, sy + 1.0, bay_x(6) - 9.5, sy + 21.2, gap=VG),
        # eMMC passives: on the eMMC's own face.  With the core mirrored that face is crowded with the core's
        # decoupling, and the free strip is along the outer edge just behind the eMMC.
        "EMMC": (Packer("EMMC", 0.8, 77.0, 5.8, 87.8, sides=("F",)) if CORE_ON_BOTTOM else
                 Packer("EMMC", 2.0, 86.0, 28.0, 105.6, sides=("B",))),
        "FRONT": Packer("FRONT", 0.8, C["FRONT_Y0"], 29.2, C["COL_L"] - 0.66, sides=("F", "B"), gap=0.45),
        "CHAS": Packer("CHAS", 12.2, 4.9, 22.0, 9.7),          # chassis bleed network, next to the RJ45 shield
    }
    for k in range(1, 10):
        Z[f"BAY{k}"] = Packer(f"BAY{k}", bay_x(k) - 9.0, sy + 9.4, bay_x(k) + 9.0, sy + 21.2, gap=VG)

    for k in range(1, 10):
        edge_mount(f"J3{k}", bay_x(k), sy, 0.8, (0, -1))
    put("T1", (C["PRI_X0"] + C["PRI_X1"]) / 2, C["T1_Y"], 180, bottom=True)   # bottom face (tallest part, about 12.7 mm); 180 deg keeps the primary pins towards the rear
    put("U31", (C["PRI_X1"] + C["SELV_COR"]) / 2, 29.6, 180)      # optocoupler and Y capacitor straddle the right barrier
    put("C518", (C["PRI_X1"] + C["SELV_COR"]) / 2, 25.6, 0)
    put("U40", 35.4, sy + 5.6, 0)
    put("U50", (bay_x(5) + bay_x(6)) / 2, sy + 11.0, 0)
    edge_mount("J40", C["BATT_X"], C["COL_L"], 0.9, (0, 1))      # front "TO BATT" USB-C
    if STRIP:
        edge_mount("J50", 65.6, sy + C["STRIP_H"], 0.9, (0, 1))  # upstream A: USB 3 from the ZERO 3E
        edge_mount("J51", 98.0, sy + C["STRIP_H"], 0.9, (0, 1))  # upstream B: 5 V to the ZERO 3E + USB 2
        put_c("J52", (C["PRI_X0"] + C["PRI_X1"]) / 2, 4.0, 90)   # PoE centre taps (primary side)
        put_c("J53", 2.9, 19.6, 0)                               # control header, in the left SELV corridor
        put_c("J54", 2.9, 36.9, 0)
    else:
        put("U20", C["EMMC_X"] if CORE_ON_BOTTOM else 15.0, 96.0, 0, bottom=not CORE_ON_BOTTOM)     # the eMMC sits opposite the PMIC, where Radxa has the microSD
        edge_mount("J21", 22.5, C["COL_L"], -0.6, (0, 1))        # debug UART, low-profile JST-SH, opening towards the front
        edge_mount("J6", 66.0, sy + C["STRIP_H"], 0.3, (0, 1))
    fixed = [r_ for r_ in ("U40", "U50", "J6", "U20", "U31", "C518", "T1", "J21", "J40", "J2", "J20", "J50", "J51", "J52", "J53", "J54", "SW3") if r_ in fps]
    for name in ("HUB3", "MID12", "MID23", "HUB2", "EMMC", "POE_PRI", "POE_SEC", "POE_SEC2", "POE_SEC3", "POE_SEC4", "CHAS", "FRONT", "BAY1", "BAY2", "BAY3", "SVC", "KBZ"):
        for r_ in fixed:
            fp = fps[r_]
            Z[name].block("B" if fp.IsFlipped() else "F", *court(fp))
    # The two hubs: a ring around each stays free of parts on BOTH faces.  Their differential pairs leave the pins,
    # change layer there (two vias per pair, which need clear copper on every layer) and run on.  The area under the
    # middle of the package stays available on the bottom face.
    for r_ in ("U40", "U50"):
        if r_ not in fps:
            continue
        c_ = court(fps[r_])
        h_ = C["HUB_HALO"][r_]
        ring = [(c_[0] - h_, c_[1] - h_, c_[2] + h_, c_[1] + 1.2), (c_[0] - h_, c_[3] - 1.2, c_[2] + h_, c_[3] + h_),
                (c_[0] - h_, c_[1], c_[0] + 1.2, c_[3]), (c_[2] - 1.2, c_[1], c_[2] + h_, c_[3])]
        for name in ("HUB3", "MID12", "MID23", "HUB2"):
            for side in ("F", "B"):
                for bx_ in ring:
                    Z[name].block(side, *bx_)
    # through-hole legs of top-side connectors also occupy the bottom side
    for r_, zn in (("J40", "FRONT"), ("J21", "FRONT"), ("J2", "SVC"), ("J20", "KBZ"), ("J20", "EMMC"), ("J50", "MID12"), ("J51", "MID23")):
        if r_ not in fps:
            continue
        for p in fps[r_].Pads():
            if p.HasHole():
                px_, py_ = ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY
                bb_ = p.GetBoundingBox()
                Z[zn].block("B", ToMM(bb_.GetLeft()) - OX - 0.3, ToMM(bb_.GetTop()) - OY - 0.3, ToMM(bb_.GetRight()) - OX + 0.3, ToMM(bb_.GetBottom()) - OY + 0.3)
    for k in range(1, 10):
        Z[f"BAY{k}"].block("F", *court(fps[f"J3{k}"]))
    for r_ in transplanted:                # keep the eMMC zone off the transplanted bottom-side parts
        fp = fps[r_]
        Z["EMMC"].block("B" if fp.IsFlipped() else "F", *court(fp))
        for zn in ("CHAS", "POE_PRI", "SVC", "KBZ", "CORE_T"):
            Z[zn].block("B" if fp.IsFlipped() else "F", *court(fp))

    sec_nets = ("VOUT_5V", "VOUT_5V_PRE", "FB_K", "FB_REF", "FB_COMP", "FB_LED_A", "POE_SNUB")

    def zone_of(c):
        m = re.match(r"^\d?[A-Z]+(\d+)$", c.ref)
        n = int(m.group(1)) if m else 0
        if c.ref in ("R400", "C400"):
            return "CHAS"
        if c.ref in SVC_REFS:
            return "SVC"                    # bottom side, under the connector they belong to
        if c.ref in ("F1", "C713", "U51", "R706", "R707"):
            return "KBZ"
        if c.sheet == "testif":
            return "MID12"
        if c.sheet == "hdmi":
            return "HDMI"
        if c.sheet == "poe":
            if c.ref in ("D41", "R510", "C510", "C511", "C512", "C513"):
                return "POE_SEC2"
            pri = any((net or "").startswith(("POE_", "TR")) for net in c.pins.values())
            sec = any(net in sec_nets for net in c.pins.values())
            return "POE_SEC" if sec or not pri else "POE_PRI"
        if c.sheet == "usb3_hub":
            if 1010 <= n < 1050:                # Type-C controller / mux block of bays 1-4
                return f"BAY{(n - 1000) // 10}"
            return f"BAY{(n - 630) // 10}" if 640 <= n < 680 else "HUB3"
        if c.sheet == "battery":
            # the source selector sits at the PoE output; the port, its CC controller and charge switch at the front
            return "POE_SEC" if c.ref in ("U81", "TP7") or 811 <= n <= 818 else "FRONT"
        if c.sheet == "usb2_hub":
            return f"BAY{(n - 700) // 10}" if 750 <= n < 800 else "HUB2"
        if c.sheet == "storage":
            if c.ref in ("R137", "R90723", "C227") or re.match(r"^D1[3-9]$", c.ref):
                return "MID12"
            if c.ref in ("R401", "R402", "R403", "R404", "C401", "C402", "C403", "C404", "C405", "TP3"):
                return "EMMC"
        return "FRONT"

    overflow = {"HUB3": ["MID12", "MID23"], "MID12": ["MID23"], "SVC": ["KBZ", "CORE_T"], "KBZ": ["SVC", "CORE_T"], "EMMC": ["CORE_T"],
                "POE_SEC": ["POE_SEC2", "POE_SEC4", "POE_SEC3"], "POE_SEC2": ["POE_SEC4", "POE_SEC", "POE_SEC3"]}

    def area(c):
        b = court(fps[c.ref])
        return (b[2] - b[0]) * (b[3] - b[1])

    todo = sorted([c for c in d.comps.values() if c.ref not in placed], key=lambda c: -area(c))
    for c in todo:
        z = zone_of(c)
        # nothing on the top face may stand taller than the bay connectors (3.3 mm): the one part without a
        # low-profile equivalent, the 100 V electrolytic of the PoE input, goes underneath
        tall = "CP_Elec" in str(fps[c.ref].GetFPID().GetLibItemName())
        ok = Z[z].place(fps[c.ref], first="B" if tall else None)
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

    core_set = set(core_refs)

    def net_index(skip):
        # a core part is oriented by its connections to other CORE parts only: that evidence is Radxa's own
        # geometry and is the same whichever face the core is on
        idx = {}
        for r_, fp in fps.items():
            if r_ == skip or (skip in core_set and r_ not in core_set):
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

    orient_notes = []
    order = sorted(transplanted, key=lambda r_: -len(d.comps[r_].pins))
    for _ in range(2):
        for r_ in order:
            if r_ == "U1":
                continue
            fp = fps[r_]
            idx = net_index(r_)
            base = fp.GetOrientationDegrees()
            # mirrored core: try the quarter turns in mirrored order, so ties resolve to the mirror image of Radxa's layout
            cands = (0, 180) if len(d.comps[r_].pins) == 2 else ((0, 270, 180, 90) if CORE_ON_BOTTOM and r_ in core_refs else (0, 90, 180, 270))
            centre = fp.GetPosition()
            best = None
            costs = []
            for dr in cands:
                fp.SetOrientationDegrees(base + dr)
                fp.SetPosition(centre)
                cst = cost(fp, idx)
                costs.append(cst)
                if best is None or cst < best[0] - 1e-6:
                    best = (cst, base + dr)
            fp.SetOrientationDegrees(best[1])
            fp.SetPosition(centre)
            if r_ in ("U9", "U10") and _ == 1:
                orient_notes.append("orientation of %s: net-distance cost per quarter turn %s (lowest wins)" % (r_, " ".join("%.1f" % c_ for c_ in costs)))

    # ---------------- 4b. clear the chips, the connectors and each other ----------------
    # Positions taken from a reference designator's text anchor are only approximate, and the ports and the
    # eMMC are new.  A small part that ends up on another part's pads is moved to the nearest spot that is free
    # on its own face (and clear of through-hole pads from the other face).  Parts whose position was
    # recovered from their own pad pair are trusted and stay, unless they sit on a chip or a connector.
    def pad_box(fp, m=0.0):
        xs, ys = [], []
        for p in fp.Pads():
            bb_ = p.GetBoundingBox()
            xs += [ToMM(bb_.GetLeft()) - OX, ToMM(bb_.GetRight()) - OX]
            ys += [ToMM(bb_.GetTop()) - OY, ToMM(bb_.GetBottom()) - OY]
        return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)

    def hit(a_, b_, eps=0.01):
        return a_[0] < b_[2] - eps and b_[0] < a_[2] - eps and a_[1] < b_[3] - eps and b_[1] < a_[3] - eps

    def fab_box(fp):
        """Outline of the package itself (fabrication layer), which for a BGA or a connector is larger than its pads."""
        layer = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
        xs, ys = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() == layer and g.GetClass() == "PCB_SHAPE":
                bb_ = g.GetBoundingBox()
                xs += [ToMM(bb_.GetLeft()) - OX, ToMM(bb_.GetRight()) - OX]
                ys += [ToMM(bb_.GetTop()) - OY, ToMM(bb_.GetBottom()) - OY]
        b0 = pad_box(fp)
        return (min(xs + [b0[0]]), min(ys + [b0[1]]), max(xs + [b0[2]]), max(ys + [b0[3]]))

    mount_holes = [(27.0, 5.0)] if STRIP else [core_xy(60.0, 3.433), (26.333, C["KB_Y"] + 8.7)]     # the second one makes way for the keyboard port
    mount_holes += [(sx1 - 4.0, sy + 17.5)]
    mount_holes += [((bay_x(k) + bay_x(k + 1)) / 2, sy + 4.0) for k in (2, 4, 6, 8)]
    nudged, stuck = [], []
    if not STRIP:
        large = {r_ for r_, fp in fps.items() if fp.GetPadCount() >= 20 or r_[0] == "J" or r_ == "T1"}
        bodies = {r_: (fab_box(fp) if r_ in large else pad_box(fp)) for r_, fp in fps.items()}
        drills = {r_: [pad_box_p for pad_box_p in
                       [(ToMM(p.GetBoundingBox().GetLeft()) - OX, ToMM(p.GetBoundingBox().GetTop()) - OY,
                         ToMM(p.GetBoundingBox().GetRight()) - OX, ToMM(p.GetBoundingBox().GetBottom()) - OY)
                        for p in fp.Pads() if p.HasHole()]] for r_, fp in fps.items()}
        drills = {r_: v for r_, v in drills.items() if v}
        offs = sorted(((dx * 0.1, dy * 0.1) for dx in range(-90, 91) for dy in range(-90, 91)), key=lambda o: o[0] ** 2 + o[1] ** 2)
        offs = [o for o in offs if o[0] ** 2 + o[1] ** 2 <= 81.0]

        def obstacles(r_, reach):
            me, side = bodies[r_], fps[r_].IsFlipped()
            zone_ = (me[0] - reach, me[1] - reach, me[2] + reach, me[3] + reach)
            out = []
            for r2, b2 in bodies.items():
                if r2 == r_ or not hit(zone_, b2):
                    continue
                if fps[r2].IsFlipped() == side:
                    out.append((r2, b2 if r2 in large else b2))
            for r2, boxes in drills.items():
                if r2 != r_:
                    out += [(r2, bx) for bx in boxes if hit(zone_, bx)]
            return out

        movable = [r_ for r_ in transplanted if r_ not in large and fps[r_].GetPadCount() <= 6]
        # first the parts that sit on something large, then the anchor-placed ones
        def on_large(r_):
            return any(r2 in large for r2, bx in obstacles(r_, 0.0) if hit(bodies[r_], bx))
        todo_ = [r_ for r_ in movable if on_large(r_)]
        todo_ += [r_ for r_ in movable if r_ not in todo_ and placed.get(r_, "") != "radxa (pads)"]
        for r_ in todo_:
            me = bodies[r_]
            obs = obstacles(r_, 9.5)
            margin = 0.12
            grown = (me[0] - margin, me[1] - margin, me[2] + margin, me[3] + margin)
            if not any(hit(grown if r2 in large else me, bx) for r2, bx in obs):
                continue
            ylo, yhi = (-13.5, 12.0) if d.comps[r_].sheet == "ethernet" else (56.0, C["COL_L"] - 0.6)
            for dx, dy in offs:
                cand = (grown[0] + dx, grown[1] + dy, grown[2] + dx, grown[3] + dy)
                if cand[0] < 0.4 or cand[2] > C["COL_W"] - 0.4 or cand[1] < ylo or cand[3] > yhi:
                    continue
                if any(hit(cand, bx) for r2, bx in obs):
                    continue
                fp = fps[r_]
                fp.SetPosition(VECTOR2I(fp.GetPosition().x + FromMM(dx), fp.GetPosition().y + FromMM(dy)))
                bodies[r_] = pad_box(fp)
                nudged.append((r_, math.hypot(dx, dy)))
                placed[r_] = placed.get(r_, "") + ", moved clear"
                break
            else:
                # no room on its own face: try the other face at the same place
                fp = fps[r_]
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                bodies[r_] = pad_box(fp)
                me = bodies[r_]
                grown = (me[0] - margin, me[1] - margin, me[2] + margin, me[3] + margin)
                obs = obstacles(r_, 9.5)
                for dx, dy in offs:
                    cand = (grown[0] + dx, grown[1] + dy, grown[2] + dx, grown[3] + dy)
                    if cand[0] < 0.4 or cand[2] > C["COL_W"] - 0.4 or cand[1] < ylo or cand[3] > yhi:
                        continue
                    if any(hit(cand, bx) for r2, bx in obs):
                        continue
                    fp.SetPosition(VECTOR2I(fp.GetPosition().x + FromMM(dx), fp.GetPosition().y + FromMM(dy)))
                    bodies[r_] = pad_box(fp)
                    nudged.append((r_, math.hypot(dx, dy)))
                    placed[r_] = placed.get(r_, "") + ", moved clear to the other face"
                    break
                else:
                    stuck.append(r_)

        # second round: two parts that were each placed from their own pads can still sit on each other (their real
        # footprints are smaller than the ones used here), and a new part can sit on a transplanted one.  Pads that
        # touch are a short circuit, so the smaller part of each such pair is moved, whatever its position came from.
        for i_, (hx, hy) in enumerate(mount_holes, 1):          # the mounting holes are obstacles on both faces
            drills["H%d" % i_] = [(hx - 2.3, hy - 2.3, hx + 2.3, hy + 2.3)]
        # The balls of the differential pairs (USB, HDMI) leave the RK3566 through a via in the ball itself; a part
        # on the opposite face exactly there would make that via impossible.  These spots are obstacles on both faces.
        import fnmatch
        import gen_project
        pair_pat = [pat for pat, cname in gen_project.PATTERNS if cname in ("USB2", "USB3_SS", "HDMI")]
        if "U1" in fps:
            spots = []
            for p in fps["U1"].Pads():
                if any(fnmatch.fnmatch(p.GetNetname(), pat) for pat in pair_pat):
                    px_, py_ = ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY
                    spots.append((px_ - 0.32, py_ - 0.32, px_ + 0.32, py_ + 0.32))
            if spots:
                drills["U1 pair balls"] = spots
        small = [r_ for r_, fp in fps.items() if r_ not in large and fp.GetPadCount() <= 6 and r_[0] not in "HJ"
                 and 0.0 <= bodies[r_][0] and bodies[r_][2] <= C["COL_W"] and bodies[r_][1] >= -13.5]
        for r_ in sorted(small, key=lambda q: (bodies[q][2] - bodies[q][0]) * (bodies[q][3] - bodies[q][1])):
            me = bodies[r_]
            if d.comps[r_].sheet in ("poe",) or 8.6 < me[1] < 56.0:
                continue                        # (the PoE block is packed with its own spacing)
            obs = obstacles(r_, 9.5)
            margin = 0.12
            grown = (me[0] - margin, me[1] - margin, me[2] + margin, me[3] + margin)
            if not any(hit(grown, bx) for r2, bx in obs):
                continue
            ylo, yhi = (-13.5, 8.0) if me[3] < 8.6 else (56.0, C["COL_L"] - 0.6)
            for dx, dy in offs:
                cand = (grown[0] + dx, grown[1] + dy, grown[2] + dx, grown[3] + dy)
                if cand[0] < 0.4 or cand[2] > C["COL_W"] - 0.4 or cand[1] < ylo or cand[3] > yhi:
                    continue
                if any(hit(cand, bx) for r2, bx in obs):
                    continue
                fp = fps[r_]
                fp.SetPosition(VECTOR2I(fp.GetPosition().x + FromMM(dx), fp.GetPosition().y + FromMM(dy)))
                bodies[r_] = pad_box(fp)
                nudged.append((r_, math.hypot(dx, dy)))
                placed[r_] = placed.get(r_, "") + ", moved off another part's pads"
                break
            else:
                if r_ not in stuck:
                    stuck.append(r_)

    # ---------------- 5. mounting holes (provisional) ----------------
    holes = mount_holes
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
    if not STRIP:
        note("HDMI corridor", 2.0, 40.0, 0.8, rot=90)
        box(0.0, C["CORE_Y0"], C["COL_W"], C["CORE_Y0"] + 65.0 - C["CORE_XR0"])
        note("CODEC CORE - placement transplanted from Radxa ZERO 3E V1.2 (rotated 90 deg)", -1.0, 106.0, 1.0, rot=90)
    for k in range(1, 10):
        note(f"BAY {k} " + ("USB 3.2 Gen 1" if k <= 4 else "USB 2.0"), bay_x(k) - 8.0, sy + 23.3, 1.0)
        box(bay_x(k) - 15.0, sy - 32.0, bay_x(k) + 15.0, sy, width=0.1)
    note("Framework expansion card envelope (30 x 32 mm) - rear panel plane at the top edge of these boxes", bay_x(1) - 15.0, sy - 34.0, 1.2)
    if STRIP:
        note("COMMANDER STRIP TEST BOARD rev T0 - PoE, hubs, nine bays, battery port; no codec core." + NL +
             "J50 / J51 connect to a stock Radxa ZERO 3E.  Same strip geometry as the mainboard." + NL +
             "4-layer, 1.2 mm.  Differential pairs and the PoE converter are NOT routed.  See README.md.", 60.0, 62.0, 2.0)
        for txt, x, y in (("J50  USB3 <- ZERO 3E", 60.0, sy + 24.6), ("J51  5V -> ZERO 3E + USB2", 92.0, sy + 24.6)):
            note(txt, x, y, 1.0, layer=pcbnew.F_SilkS)
    else:
        note("COMMANDER MAINBOARD rev A1 - PARTLY ROUTED - for audit, NOT for fabrication." + NL +
             "Outline from the customer drawing: column 30 x 118.66, strip 294.73 x 21.72, bays at 19.39 + n x 32.45." + NL +
             "ASSUMED: strip offset 11.30 below column top; rear tab depths 14.2 (RJ45) / 19.6 (HDMI); mounting holes." + NL +
             "6-layer, 1.2 mm.  See DESIGN_NOTES.md.", 60.0, 62.0, 2.0)

    # ---------------- save + report ----------------
    out = os.environ.get("CP_PCB") or os.path.join(ROOT, cpmodel.PRJ + ".kicad_pcb")
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
    lines += ["", f"small parts moved clear of a chip, a connector or another part: {len(nudged)}"
              + (f" (largest move {max(m for _, m in nudged):.1f} mm, average {sum(m for _, m in nudged) / len(nudged):.1f} mm)" if nudged else "")]
    lines += ["  " + " ".join(f"{r_}:{m:.1f}" for r_, m in sorted(nudged, key=lambda t: -t[1])[:60])] if nudged else []
    lines += [f"could not find a free spot within 9 mm for: {' '.join(stuck) or 'none'}"]
    lines += [""] + orient_notes + ["codec core face: " + ("BOTTOM (mirror image of Radxa's placement)" if CORE_ON_BOTTOM else "top (Radxa's orientation)")]
    open(os.path.join(ROOT, "build", "placement_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    json.dump(placed, open(os.path.join(ROOT, "build", "placement.json"), "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("saved", out)
    print(NL.join(lines[:3 + len(hows)]))
    print("parked:", " ".join(r_ for r_, z in parked))
    print("pad mismatches:", len(report))


if __name__ == "__main__":
    main()
