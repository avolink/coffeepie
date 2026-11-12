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
import heapq
import math
import os
import sys
import time

import numpy as np
import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402
import gen_project                              # noqa: E402
from gen_pcb import CFG, OX, OY, outline_pts    # noqa: E402

ROOT = cpmodel.ROOT
NL = chr(10)
G = 0.05                    # routing grid, mm
TOL = G / 2                 # copper never extends more than this beyond a marked cell centre
FREE, MULTI = -1, -2
RLAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
SKIP_CLASSES = {"DDR", "USB3_SS", "USB2", "HDMI", "ETH_MDI", "RGMII", "POE_PRIMARY"}
SKIP_NETS = {"CHASSIS"}
SY = CFG["STRIP_Y"]
REGIONS = [   # name, x0, y0, x1, y1 (design mm); each window overlaps the real board edge by 1 mm
    ("strip", CFG["COL_W"], SY - 1.0, CFG["COL_W"] + CFG["STRIP_L"] + 1.0, SY + CFG["STRIP_H"] + 1.0),
    ("front", -1.0, 106.9, CFG["COL_W"] + 1.0, CFG["COL_L"] + 1.0),
]
# SELV plane outlines (design mm); the board edge clips them
# right corridor + strip + lower column + left (HDMI) corridor and tab; the PoE primary block in the middle and the
# RJ45 / magnetics head stay bare
XL, XR = CFG["HDMI_COR"], CFG["SELV_COR"]
PLANE_GND = [(XR, SY - 1.0), (326.0, SY - 1.0), (326.0, SY + 22.8), (31.0, SY + 22.8), (31.0, 120.0), (-1.0, 120.0),
             (-1.0, -21.0), (10.0, -21.0), (10.0, 7.0), (XL, 7.0), (XL, 46.0), (XR, 46.0)]
PLANE_5V = [(XR, SY - 1.0), (326.0, SY - 1.0), (326.0, SY + 22.8), (31.0, SY + 22.8), (31.0, 60.0), (XR, 60.0)]
PLANES = {"GND": ("strip", "front"), "VCC5V_BUS": ("strip",)}       # net -> regions where a plane is under the pads

CLS = {c["name"]: c for c in gen_project.CLASSES}


def ceil_(v):
    return int(math.ceil(v - 1e-9))


class RC:
    """Routing parameters of a net class, in grid cells."""

    def __init__(self, name, w, cl, via_d, via_drill):
        self.name, self.w, self.cl, self.via_d, self.via_drill = name, w, cl, via_d, via_drill
        self.extra = ceil_((cl - 0.10) / G) if cl > 0.10 else 0          # extra growth so other classes keep cl
        self.Kt = ceil_((cl + w / 2 + TOL) / G) - 1                       # track centre: no foreign copper within Kt cells
        self.mt = max(0, ceil_((w / 2 - TOL) / G)) + self.extra           # how far a track's copper is marked
        self.Kv = ceil_((cl + via_d / 2 + TOL) / G) - 1
        self.mv = max(0, ceil_((via_d / 2 - TOL) / G)) + self.extra


RCS = {
    "Default": RC("Default", 0.15, CLS["Default"]["clearance"], 0.45, 0.20),
    "PWR": RC("PWR", CLS["PWR"]["track_width"], CLS["PWR"]["clearance"], 0.60, 0.30),
    "PWR_5V": RC("PWR_5V", CLS["PWR_5V"]["track_width"], CLS["PWR_5V"]["clearance"], 0.60, 0.30),
}
# neck-down used where the class width cannot enter a fine-pitch pad
THIN = {n: RC(n + "_thin", 0.15, RCS[n].cl, RCS[n].via_d, RCS[n].via_drill) for n in ("PWR", "PWR_5V")}
KSET = sorted({rc.Kt for rc in list(RCS.values()) + list(THIN.values())} | {rc.Kv for rc in RCS.values()})
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
        self.novia = np.zeros((self.ny, self.nx), bool)
        self.soft = np.full((3, self.ny, self.nx), FREE, np.int16)      # whose exit zone a cell is in
        self.pads = {}          # netcode -> [dict(pad=, cells=[(l,i,j)], cx=, cy=, layers=)]
        self.tree = {}          # netcode -> set of (l,i,j) centre-line cells already routed

    def xy(self, i, j):
        return self.x0 + i * G, self.y0 + j * G

    def stamp(self, l, i0, j0, mask, net):
        """Mark copper cells (mask anchored at i0, j0) of 'net' on routing layer l in every clearance map."""
        h, w = mask.shape
        for k, D in self.D.items():
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
                        grow = ceil_((cl - 0.10) / G) if cl > 0.10 else 0
                    mm = m
                    if grow:
                        big = np.zeros((m.shape[0] + 2 * grow, m.shape[1] + 2 * grow), bool)
                        big[grow:-grow, grow:-grow] = m
                        mm = dilate(big, grow)
                    for l in layers:
                        reg.stamp(l, i0 - grow, j0 - grow, mm, net)
                    k = K_NOVIA
                    big = np.zeros((m.shape[0] + 2 * k, m.shape[1] + 2 * k), bool)
                    big[k:-k, k:-k] = m
                    big = dilate(big, k)
                    ia, ja = max(i0 - k, 0), max(j0 - k, 0)
                    ib, jb = min(i0 - k + big.shape[1], reg.nx), min(j0 - k + big.shape[0], reg.ny)
                    reg.novia[ja:jb, ia:ib] |= big[ja - (j0 - k):jb - (j0 - k), ia - (i0 - k):ib - (i0 - k)]
                    npads += 1
                    if code > 0 and len(sig) >= 5 and len(layers) == 1:
                        bb = pad.GetBoundingBox()
                        xa, ya, xb, yb = (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)
                        w_, h_ = xb - xa, yb - ya
                        if h_ >= 1.4 * w_ and abs(cy - fy) > 0.3 and w_ <= 0.9:
                            lanes.append((layers[0], code, xa, yb if cy > fy else ya - LANE, xb, yb + LANE if cy > fy else ya, 0, 1 if cy > fy else -1))
                        elif w_ >= 1.4 * h_ and abs(cx - fx) > 0.3 and h_ <= 0.9:
                            lanes.append((layers[0], code, xb if cx > fx else xa - LANE, ya, xb + LANE if cx > fx else xa, yb, 1 if cx > fx else -1, 0))
                    inside = reg.x0 + 0.2 <= cx <= reg.x1 - 0.2 and reg.y0 + 0.2 <= cy <= reg.y1 - 0.2
                    if code > 0 and inside:
                        js, is_ = np.nonzero(m)
                        cells = [(l, i0 + int(i), j0 + int(j)) for l in layers for i, j in zip(is_, js)]
                        reg.pads.setdefault(code, []).append(dict(
                            pad=pad, ref=fp.GetReference(), num=pad.GetNumber(), cells=cells, cx=cx, cy=cy, layers=layers,
                            tht=pad.HasHole(), area=ToMM(pad.GetSize().x) * ToMM(pad.GetSize().y)))
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
            self.log.append(f"region {reg.name}: {reg.nx} x {reg.ny} cells, {npads} pads rasterised, {len(boxes)} exit lanes, in {time.time() - t0:.1f} s")
            print(self.log[-1], flush=True)

    # ---- output ----
    def add_track(self, reg, net, l, a, b, w):
        if a == b:
            return
        self.items.append(("t", net, l, a, b, w))

    def add_via(self, reg, net, i, j, rc):
        self.items.append(("v", net, reg.xy(i, j), rc.via_d, rc.via_drill))
        for l in range(3):
            reg.stamp(l, i - rc.mv, j - rc.mv, disc(rc.mv), net)
        k = K_VIAVIA
        ia, ja, ib, jb = max(i - k, 0), max(j - k, 0), min(i + k + 1, reg.nx), min(j + k + 1, reg.ny)
        reg.novia[ja:jb, ia:ib] = True          # no second via on top of / touching this one

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
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
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
        tree = reg.tree.setdefault(net, set())
        run = [cells[0]]
        runs = []
        for c in cells[1:]:
            if c[0] != run[-1][0]:
                runs.append(run)
                self.add_via(reg, net, c[1], c[2], rc)
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
            tree.update(run)
        if via_at_end:
            l, i, j = cells[-1]
            self.add_via(reg, net, i, j, rc)
        return cells

    def stub(self, reg, net, rc, cell, pd):
        """Short segment from a path end inside a pad to the pad centre, so the connection is unambiguous."""
        l, i, j = cell
        self.add_track(reg, net, l, reg.xy(i, j), (pd["cx"], pd["cy"]), min(rc.w, 0.15) if pd["area"] < 0.12 else rc.w)

    def window(self, reg, net, rc, box, margin):
        i0 = max(0, int((box[0] - reg.x0) / G) - margin)
        j0 = max(0, int((box[1] - reg.y0) / G) - margin)
        i1 = min(reg.nx - 1, int((box[2] - reg.x0) / G) + margin)
        j1 = min(reg.ny - 1, int((box[3] - reg.y0) / G) + margin)
        W, H = i1 - i0 + 1, j1 - j0 + 1
        Dk = reg.D[rc.Kt][:, j0:j1 + 1, i0:i1 + 1]
        ok = (Dk == FREE) | (Dk == net)
        Dv = reg.D[rc.Kv][:, j0:j1 + 1, i0:i1 + 1]
        vok = ((Dv == FREE) | (Dv == net)).all(axis=0) & ~reg.novia[j0:j1 + 1, i0:i1 + 1] & ok.all(axis=0)
        S = reg.soft[:, j0:j1 + 1, i0:i1 + 1]
        self.pen = [((S[l] != FREE) & (S[l] != net)).tobytes() for l in range(3)]
        return i0, j0, W, H, ok, vok

    # ---- a signal / power net: connect the pads that sit in this region ----
    def route_net(self, reg, net):
        rc = self.rc_of[net]
        pads = reg.pads[net]
        order = sorted(range(len(pads)), key=lambda n: (pads[n]["cx"], pads[n]["cy"]))
        done = [order[len(order) // 2]]
        todo = [n for n in order if n != done[0]]
        ok_pads, bad = 1, []
        cellpad = {}
        for n, pd in enumerate(pads):
            for c in pd["cells"]:
                cellpad[c] = n
        while todo:
            best = min(((math.hypot(pads[a]["cx"] - pads[b]["cx"], pads[a]["cy"] - pads[b]["cy"]), a, b) for a in todo for b in done))
            _, a, b = best
            todo.remove(a)
            res = None
            why = "no free cell on the pad"
            tries = [(rc0, m_, e_) for m_, e_ in ((60, 40000), (300, 200000))
                     for rc0 in ([rc] + ([THIN[rc.name]] if rc.name in THIN else []))]
            for rc_use, margin, max_exp in tries:
                box = (min(pads[a]["cx"], pads[b]["cx"]), min(pads[a]["cy"], pads[b]["cy"]),
                       max(pads[a]["cx"], pads[b]["cx"]), max(pads[a]["cy"], pads[b]["cy"]))
                i0, j0, W, H, ok, vok = self.window(reg, net, rc_use, box, margin)
                goal = np.zeros((3, H, W), bool)
                tree = reg.tree.get(net, ())
                for c in tree:
                    if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                        goal[c[0], c[2] - j0, c[1] - i0] = True
                for n in done:
                    for c in pads[n]["cells"]:
                        if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H:
                            goal[c[0], c[2] - j0, c[1] - i0] = True
                goal &= ok
                starts = [(c[0] * H + (c[2] - j0)) * W + (c[1] - i0) for c in pads[a]["cells"]
                          if i0 <= c[1] < i0 + W and j0 <= c[2] < j0 + H and ok[c[0], c[2] - j0, c[1] - i0]]
                if not starts or not goal.any():
                    why = "pad hemmed in by neighbouring copper" if not starts else "target copper hemmed in"
                    continue
                gl, gy, gx = np.nonzero(goal)
                gbox = (int(gx.min()), int(gy.min()), int(gx.max()), int(gy.max()))
                okb = [ok[l].tobytes() for l in range(3)]
                res, _ = search(okb, vok.tobytes(), [goal[l].tobytes() for l in range(3)], W, H, starts, gbox, max_exp=max_exp, penb=self.pen)
                if res:
                    break
                why = "no path found"
            if not res:
                bad.append((a, why))
                continue
            cells = self.commit(reg, net, rc_use, res, W, H, i0, j0)
            self.stub(reg, net, rc_use, cells[0], pads[a])
            n_end = cellpad.get(cells[-1])
            if n_end is not None:
                self.stub(reg, net, rc_use, cells[-1], pads[n_end])
            done.append(a)
            ok_pads += 1
        return ok_pads, [f'{pads[n]["ref"]}.{pads[n]["num"]} ({why})' for n, why in bad]

    # ---- plane nets: one via per SMD pad (or a shared one close by), a via array in exposed pads ----
    def fanout(self, reg, net, only=None):
        rc = self.rc_of[net] if self.cls_of[net] in RCS else RCS["Default"]
        okc = bad = 0
        badl = []
        for pd in sorted(reg.pads[net], key=lambda p: (p["cx"], p["cy"])):
            if pd["tht"] or pd.get("fanned"):
                continue                                        # through-hole pads meet the planes directly
            if only is not None and (pd["ref"] + "." + pd["num"]) not in only:
                continue
            pd["fanned"] = True
            if pd["area"] >= 6.0:
                n = self.ep_vias(reg, net, rc, pd)
                okc += 1 if n else 0
                if not n:
                    bad += 1
                    badl.append(f'{pd["ref"]}.{pd["num"]}')
                continue
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
                if all(Dv[l, j, i] in (FREE, net) for l in range(3)):
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
        for net, pads in reg.pads.items():
            name = self.name_of[net]
            if name in PLANES and reg.name in PLANES[name]:
                continue
            if self.cls_of[net] in SKIP_CLASSES or name in SKIP_NETS or len(pads) < 2:
                continue
            xs, ys = [p["cx"] for p in pads], [p["cy"] for p in pads]
            if name in prio_nets:
                cand.append((-1, prio_nets.index(name), name, net))
            else:
                rank = {"PWR_5V": 0, "PWR": 1}.get(self.cls_of[net], 2)      # wide tracks first, while there is room
                cand.append((rank, max(xs) - min(xs) + max(ys) - min(ys), name, net))
        cand.sort()
        for rank, hp, name, net in cand:
            okp, bad = self.route_net(reg, net)
            (nets_part if bad else nets_done).append((reg.name, name, okp, len(reg.pads[net])))
            for b in bad:
                self.failed.append((reg.name, name, b))
        for net in planes:
            okc, bad = self.fanout(reg, net)
            fan_ok += okc
            fan_bad += [(reg.name, self.name_of[net], b) for b in bad]
        return nets_done, nets_part, fan_ok, fan_bad

    def run(self, passes=4):
        """Every region is routed up to 'passes' times; what failed goes first next time; the best pass is kept."""
        nets_done, nets_part, fan_ok, fan_bad, failed = [], [], 0, [], []
        for spec in REGIONS:
            best = None
            prio_nets, prio_fan = [], set()
            for n in range(passes):
                t0 = time.time()
                self.regs = [Region(*spec)]
                self.build()
                self.items, self.failed = [], []
                res = self.run_region(self.regs[0], prio_nets, prio_fan)
                nfail = len(self.failed) + len(res[3])
                self.log.append("region %s, pass %d: %d connections open, %.0f s" % (spec[0], n + 1, nfail, time.time() - t0))
                print(self.log[-1], flush=True)
                if best is None or nfail < best[0]:
                    best = (nfail, self.items, list(self.failed), res)
                if nfail == 0:
                    break
                for _, name, _ in self.failed:
                    if name not in prio_nets:
                        prio_nets.append(name)
                prio_fan |= {b for _, _, b in res[3]}
            self.flush(best[1])
            failed += best[2]
            nets_done += best[3][0]
            nets_part += best[3][1]
            fan_ok += best[3][2]
            fan_bad += best[3][3]
        self.failed = ["%s: %s: could not reach %s" % f for f in failed]
        return nets_done, nets_part, fan_ok, ["%s: %s: no via for %s" % f for f in fan_bad]


def add_zone(board, net, layer, pts, name, prio=0):
    z = pcbnew.ZONE(board)
    z.SetNet(board.FindNet(net))
    z.SetLayer(layer)
    z.SetZoneName(name)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(FromMM(0.20))
    z.SetMinThickness(FromMM(0.15))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
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


def main():
    t00 = time.time()
    path = os.path.join(ROOT, "commander_mainboard.kicad_pcb")
    board = pcbnew.LoadBoard(path)
    for t in list(board.GetTracks()):
        board.Remove(t)
    for z in list(board.Zones()):
        board.Remove(z)
    board.BuildConnectivity()
    before = board.GetConnectivity().GetUnconnectedCount(True)
    for layer, kind in ((pcbnew.In1_Cu, pcbnew.LT_POWER), (pcbnew.In3_Cu, pcbnew.LT_POWER), (pcbnew.In4_Cu, pcbnew.LT_POWER),
                        (pcbnew.F_Cu, pcbnew.LT_SIGNAL), (pcbnew.In2_Cu, pcbnew.LT_SIGNAL), (pcbnew.B_Cu, pcbnew.LT_SIGNAL)):
        board.SetLayerType(layer, kind)

    r = Router(board)
    nets_done, nets_part, fan_ok, fan_bad = r.run()

    add_zone(board, "GND", pcbnew.In1_Cu, PLANE_GND, "GND plane L2")
    add_zone(board, "GND", pcbnew.In4_Cu, PLANE_GND, "GND plane L5")
    add_zone(board, "VCC5V_BUS", pcbnew.In3_Cu, PLANE_5V, "5V bus plane L4")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    after = board.GetConnectivity().GetUnconnectedCount(True)
    drop_dangling(board)
    pcbnew.SaveBoard(path, board)

    lines = [
        "COMMANDER MAINBOARD - routing tranche 1 (generated by tools/route.py)",
        "",
        "stack-up roles : F.Cu signal | In1 GND | In2 signal | In3 power | In4 GND | B.Cu signal",
        "planes poured  : GND on In1 + In4, VCC5V_BUS on In3, SELV area only (strip, corridor, lower column)",
        f"tracks: {r.stats['tracks']}   vias: {r.stats['vias']}   track length: {r.stats['length']:.0f} mm",
        f"unrouted connections (ratsnest): {before} before -> {after} after",
        f"nets with every pad of the region connected: {len(nets_done)}",
        f"nets partly connected: {len(nets_part)}",
        f"plane pads given a via: {fan_ok}   without: {len(fan_bad)}",
        "",
        "NOT routed on purpose: codec core, Ethernet, PoE, HDMI areas; all differential / length-matched classes",
        "(" + ", ".join(sorted(SKIP_CLASSES)) + ").",
        "",
        f"FAILED ({len(r.failed) + len(fan_bad)}):",
    ] + ["  " + f for f in r.failed + fan_bad] + ["", "routed nets:"]
    for regname, name, okp, total in sorted(nets_done + nets_part):
        lines.append(f"  {regname:6s} {name:28s} {okp}/{total} pads")
    lines += [""] + r.log
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    open(os.path.join(ROOT, "build", "routing_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(lines[:14 + len(r.failed) + len(fan_bad)]))
    print(f"total {time.time() - t00:.0f} s")


if __name__ == "__main__":
    main()
