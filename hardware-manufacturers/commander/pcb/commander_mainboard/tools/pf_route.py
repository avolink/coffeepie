"""pf_route.py SRC DST CONFIG.json   (KiCad's Python)

Finishes the open connections of ANY board file with the negotiating (PathFinder) search core of the cpu_ram board
(cr_astar.c).  Unlike cpu_ram_board.py it knows nothing about a particular board:

  - every net it is asked to route is taken as the ISLANDS KiCad's connectivity sees (pads, tracks, vias and the zone
    fills that join them); a job joins those islands, starting anywhere on one's copper and ending anywhere on
    another's (a ground pad may simply end on its plane);
  - everything on the board is an obstacle with its real shape and the clearance of its net class; the board's edge
    (any shape, cut-outs too), keep-out rule areas and holes as well;
  - layers that are not in "layers" are plane layers: no tracks there, a via may land on its own net's fill;
  - "mode": "rip" takes copper off first (its own process: KiCad's Python objects do not survive removals).

CONFIG (JSON):
  "pro"      project file with the net classes and rules (default: beside SRC)
  "window"   [x0, y0, x1, y1] in board mm (default: the board's bounding box)
  "grid"     mm (default 0.05)
  "layers"   routing layers by name, "lcost" their cost factors
  "nets"     regular expressions (full match) of the nets to route, "exclude" likewise
  "w", "via" [diameter, hole], "cl"   the class of this pass
  "classes"  several track classes negotiating together: [{"name", "nets": [...], "w", "via", "cl", "primary": bool}, ...]
             (first match wins; replaces "w" / "via" / "cl"); a class may have "novia" / "notrack" boxes of its own
  "soft"     file written by a rip with "save": those nets' copper comes back as each net's present solution and is
             only given up where it is in someone's way ("soft_weight": how strongly it is avoided, default 8)
  "isolation" {"nets": [...], "gap": mm}: nets beyond an isolation barrier; the class that routes them has "primary"
  "iters", "repair", "via_cost", "via_in_pad", "novia" [[x0, y0, x1, y1], ...], "notrack" [[layer, x0, y0, x1, y1], ...]
  "mode": "rip" with "rip": {"nets": [...], "box": [x0, y0, x1, y1]}   tracks / vias of those nets inside the box go
          (a track that crosses the border is cut there)
"""
import ctypes
import fnmatch
import glob
import json
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
FREE, MULTI = -1, -2
EPS = 0.002
NL = chr(10)


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
            raise SystemExit("pf_route.py needs a C compiler for its search core (set CP_GCC to gcc)")
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


# ================================================================================================ rules
class Rules:
    def __init__(self, pro):
        d = json.load(open(pro, encoding="utf-8"))
        r = d["board"]["design_settings"]["rules"]
        self.hcl = r.get("min_hole_clearance", 0.2)
        self.h2h = r.get("min_hole_to_hole", 0.25)
        self.edge = r.get("min_copper_edge_clearance", 0.25)
        self.min_cl = r.get("min_clearance", 0.1)
        self.classes = {c["name"]: c for c in d["net_settings"]["classes"]}
        self.pats = [(q["pattern"], q["netclass"]) for q in (d["net_settings"].get("netclass_patterns") or [])]
        self._cache = {}
        self.iso_pats, self.iso_gap, self._iso = [], 0.0, {}

    def set_isolation(self, pats, gap):
        """Nets on the far side of an isolation barrier (PoE primary, the Ethernet line side): gap mm to everything else."""
        self.iso_pats, self.iso_gap = [re.compile(q) for q in pats], gap

    def primary(self, net):
        if not net or not self.iso_pats:
            return False
        if net not in self._iso:
            self._iso[net] = any(r.fullmatch(net) for r in self.iso_pats)
        return self._iso[net]

    def class_of(self, net):
        if net not in self._cache:
            self._cache[net] = next((c for p, c in self.pats if fnmatch.fnmatchcase(net, p)), "Default")
        return self._cache[net]

    def cl_of(self, net):
        if not net:
            return self.min_cl
        return self.classes.get(self.class_of(net), self.classes["Default"]).get("clearance", self.min_cl)


# ================================================================================================ the grid
class Grid:
    def __init__(self, win, G, layer_ids, route_idx, lcost, cls, rules):
        self.x0, self.y0, self.x1, self.y1 = win
        self.G = G
        self.W = int(round((self.x1 - self.x0) / G)) + 1
        self.H = int(round((self.y1 - self.y0) / G)) + 1
        self.N = self.W * self.H
        self.layer_ids = layer_ids
        self.L = L = len(layer_ids)
        self.route_idx = route_idx
        self.rules = rules
        self.w, self.vd, self.vh, self.cl = cls
        self.r_tt = self.w + self.cl + EPS
        self.r_tv = max(self.vd / 2 + self.cl + self.w / 2, self.vh / 2 + rules.hcl + self.w / 2) + EPS
        self.r_vv = max(self.vd + self.cl, self.vh + rules.h2h, self.vh / 2 + rules.hcl + self.vd / 2) + EPS
        self.tho = np.full((L, self.H, self.W), FREE, np.int16)
        self.vho = np.full((self.H, self.W), FREE, np.int16)
        self.occt = np.zeros((L, self.H, self.W), np.uint16)
        self.occv = np.zeros((self.H, self.W), np.uint16)
        self.trk = np.zeros((L, self.H, self.W), np.uint8)      # how many NEW routes of this class run through the cell
        self.viac = np.zeros((self.H, self.W), np.uint8)        # ... have a via there (a kept net looks these up)
        self.hist = np.zeros((L, self.H, self.W), np.float32)
        self.histv = np.zeros((self.H, self.W), np.float32)
        self.goal = np.zeros(L * self.N, np.uint8)
        self.mark = np.zeros(self.N, np.int32)
        self.epoch = 0
        lc = [8.0] * L
        for k, l in enumerate(route_idx):
            lc[l] = lcost[k]
        self.lcost = np.array(lc, np.float32)
        self.netid = {}
        self.all = [self]                       # every class's grid of this run (one per track class; see build_grid)
        self.primary = False                    # this class's nets are on the far side of the isolation barrier
        for l in range(L):                      # plane layers: nothing but a net's own fill (stamped later)
            if l not in route_idx:
                self.tho[l] = MULTI

    def nid(self, name):
        if name not in self.netid:
            self.netid[name] = len(self.netid)
        return self.netid[name]

    def cell(self, x, y):
        return int(round((x - self.x0) / self.G)), int(round((y - self.y0) / self.G))

    def xy(self, i, j):
        return self.x0 + i * self.G, self.y0 + j * self.G

    def cl_with(self, net):
        cl = max(self.cl, self.rules.cl_of(net))
        if net and self.rules.iso_pats and self.rules.primary(net) != self.primary:
            cl = max(cl, self.rules.iso_gap)        # across the isolation barrier
        return cl

    @staticmethod
    def _merge(sub, m, net):
        conflict = m & (sub != FREE) & (sub != net)
        free = m & (sub == FREE)
        sub[free] = net
        sub[conflict] = MULTI

    def _box(self, xa, ya, xb, yb):
        G = self.G
        i0, j0 = max(0, int(math.floor((xa - self.x0) / G)) - 1), max(0, int(math.floor((ya - self.y0) / G)) - 1)
        i1, j1 = min(self.W, int(math.ceil((xb - self.x0) / G)) + 2), min(self.H, int(math.ceil((yb - self.y0) / G)) + 2)
        return i0, j0, max(i0, i1), max(j0, j1)

    def dist(self, shape, ext, rounded=False):
        """Signed distance (mm, negative inside) from a pad shape (kind, cx, cy, a, b, rot, rr) for the cells of its
        bounding box grown by ext.  rounded: a round-rect's real corners (for 'is this point on the pad')."""
        kind, cx, cy, a, b, rot, rr = shape
        reach = (a if kind == "circle" else math.hypot(a, b)) + max(ext, 0) + self.G
        i0, j0, i1, j1 = self._box(cx - reach, cy - reach, cx + reach, cy + reach)
        if i1 <= i0 or j1 <= j0:
            return i0, j0, i1, j1, np.zeros((0, 0))
        dx = (self.x0 + np.arange(i0, i1) * self.G - cx)[None, :]
        dy = (self.y0 + np.arange(j0, j1) * self.G - cy)[:, None]
        if kind == "circle":
            return i0, j0, i1, j1, np.hypot(dx, dy) - a
        if rot % 180 == 0:
            u, v = np.abs(dx), np.abs(dy)
        elif rot % 180 == 90:
            u, v = np.abs(dy), np.abs(dx)
        else:
            c_, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            u, v = np.abs(dx * c_ - dy * s_), np.abs(dx * s_ + dy * c_)
        u, v = np.broadcast_arrays(u, v)
        if kind == "oval":
            r = min(a, b)
            if a >= b:
                d = np.hypot(np.maximum(u - (a - b), 0), v) - r
            else:
                d = np.hypot(u, np.maximum(v - (b - a), 0)) - r
            return i0, j0, i1, j1, d
        r = rr if rounded else 0.0
        qx, qy = u - (a - r), v - (b - r)
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
        return i0, j0, i1, j1, d

    def hard_shape(self, layers, shape, net, off_t, off_v):
        nid = self.nid(net) if net else MULTI
        if layers:
            i0, j0, i1, j1, d = self.dist(shape, off_t)
            if d.size:
                m = d < off_t - 1e-9
                for l in layers:
                    self._merge(self.tho[l, j0:j1, i0:i1], m, nid)
        i0, j0, i1, j1, d = self.dist(shape, off_v)
        if d.size:
            self._merge(self.vho[j0:j1, i0:i1], d < off_v - 1e-9, nid)

    def seg_d2(self, a, b, r):
        i0, j0, i1, j1 = self._box(min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r)
        if i1 <= i0 or j1 <= j0:
            return i0, j0, i1, j1, np.zeros((0, 0))
        xs = (self.x0 + np.arange(i0, i1) * self.G)[None, :]
        ys = (self.y0 + np.arange(j0, j1) * self.G)[:, None]
        vx, vy = b[0] - a[0], b[1] - a[1]
        ll = vx * vx + vy * vy
        t = np.clip(((xs - a[0]) * vx + (ys - a[1]) * vy) / ll, 0, 1) if ll > 0 else 0.0
        return i0, j0, i1, j1, (xs - a[0] - t * vx) ** 2 + (ys - a[1] - t * vy) ** 2

    def hard_segment(self, layers, a, b, net, w):
        nid = self.nid(net) if net else MULTI
        cl = self.cl_with(net)
        rt = w / 2 + cl + self.w / 2 + EPS
        rv = max(w / 2 + cl + self.vd / 2, w / 2 + self.rules.hcl + self.vh / 2) + EPS
        i0, j0, i1, j1, d2 = self.seg_d2(a, b, rt)
        if d2.size:
            for l in layers:
                self._merge(self.tho[l, j0:j1, i0:i1], d2 < rt * rt - 1e-9, nid)
        i0, j0, i1, j1, d2 = self.seg_d2(a, b, rv)
        if d2.size:
            self._merge(self.vho[j0:j1, i0:i1], d2 < rv * rv - 1e-9, nid)

    def hard_via(self, x, y, net, d, h, layers):
        nid = self.nid(net) if net else MULTI
        cl = self.cl_with(net)
        hcl, h2h = self.rules.hcl, self.rules.h2h
        rt = max(d / 2 + cl + self.w / 2, h / 2 + hcl + self.w / 2) + EPS
        rv = max(d / 2 + self.vd / 2 + cl, h / 2 + self.vh / 2 + h2h, h / 2 + hcl + self.vd / 2, self.vh / 2 + hcl + d / 2) + EPS
        sh = ("circle", x, y, 0.0, 0.0, 0, 0)
        i0, j0, i1, j1, dd = self.dist(sh, rt)
        if dd.size:
            for l in layers:
                self._merge(self.tho[l, j0:j1, i0:i1], dd < rt - 1e-9, nid)
        i0, j0, i1, j1, dd = self.dist(sh, rv)
        if dd.size:
            self._merge(self.vho[j0:j1, i0:i1], dd < rv - 1e-9, MULTI)     # hole to hole holds within a net too

    def wall(self, a, b, rt, rv, layers=None):
        """A line nothing may come near (board edge): tracks rt, vias rv."""
        for arr, r, ls in ((self.tho, rt, layers if layers is not None else range(self.L)), (None, rv, None)):
            i0, j0, i1, j1, d2 = self.seg_d2(a, b, r)
            if not d2.size:
                continue
            m = d2 < r * r - 1e-9
            if arr is None:
                self.vho[j0:j1, i0:i1][m] = MULTI
            else:
                for l in ls:
                    self.tho[l, j0:j1, i0:i1][m] = MULTI

    def poly_mask(self, rings):
        """Even-odd fill of polygon rings (lists of (x, y) mm) -> (i0, j0, i1, j1, bool mask), clipped to the window."""
        G = self.G
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        i0, j0, i1, j1 = self._box(min(xs), min(ys), max(xs), max(ys))
        w, h = i1 - i0, j1 - j0
        if w <= 0 or h <= 0:
            return i0, j0, i1, j1, np.zeros((0, 0), bool)
        acc = np.zeros((h, w + 1), np.int32)
        for r in rings:
            p = np.array(r, float)
            q = np.roll(p, -1, 0)
            xa, ya = (p[:, 0] - self.x0) / G - i0, (p[:, 1] - self.y0) / G - j0
            xb, yb = (q[:, 0] - self.x0) / G - i0, (q[:, 1] - self.y0) / G - j0
            sw = ya > yb
            xa, xb = np.where(sw, xb, xa), np.where(sw, xa, xb)
            ya, yb = np.where(sw, yb, ya), np.where(sw, ya, yb)
            ra, rb = np.ceil(ya).astype(np.int64), np.ceil(yb).astype(np.int64)     # rows ya <= j < yb
            ra, rb = np.clip(ra, 0, h), np.clip(rb, 0, h)
            cnt = rb - ra
            keep = cnt > 0
            if not keep.any():
                continue
            xa, ya, xb, yb, ra, cnt = xa[keep], ya[keep], xb[keep], yb[keep], ra[keep], cnt[keep]
            idx = np.repeat(np.arange(len(cnt)), cnt)
            first = np.cumsum(cnt) - cnt
            rows = ra[idx] + (np.arange(len(idx)) - first[idx])
            xi = xa[idx] + (rows - ya[idx]) * (xb[idx] - xa[idx]) / (yb[idx] - ya[idx])
            col = np.clip(np.ceil(xi).astype(np.int64), 0, w)
            np.add.at(acc, (rows, col), 1)
        return i0, j0, i1, j1, (np.cumsum(acc, 1)[:, :w] & 1).astype(bool)

    @staticmethod
    def erode(m, k):
        out = m.copy()
        for _ in range(k):
            e = out.copy()
            e[1:, :] &= out[:-1, :]
            e[:-1, :] &= out[1:, :]
            e[:, 1:] &= out[:, :-1]
            e[:, :-1] &= out[:, 1:]
            e[0, :] = e[-1, :] = False
            e[:, 0] = e[:, -1] = False
            out = e
        return out

    def reserve(self, l, rings, grow):
        i0, j0, i1, j1, m = self.poly_mask(rings)
        if not m.size:
            return
        # the margin grows OUT of the area's own box (a mask of the box alone would lose it at the edges); square
        # growth: a little more than needed at the corners, never less
        k = int(math.ceil(grow / self.G))
        a0, b0, a1, b1 = max(0, i0 - k), max(0, j0 - k), min(self.W, i1 + k), min(self.H, j1 + k)
        g = np.zeros((b1 - b0, a1 - a0), bool)
        g[j0 - b0:j1 - b0, i0 - a0:i1 - a0] = m
        for _ in range(k):
            e = g.copy()
            e[1:, :] |= g[:-1, :]
            e[:-1, :] |= g[1:, :]
            g = e
            e = g.copy()
            e[:, 1:] |= g[:, :-1]
            e[:, :-1] |= g[:, 1:]
            g = e
        (self.vho[b0:b1, a0:a1] if l is None else self.tho[l, b0:b1, a0:a1])[g] = MULTI

    # ---- soft zones of a routed job ----
    def stamp_job(self, job, delta):
        """Add (+1) or take away (-1) a routed job's keep-out zones, in every class's grid: each class sees the job's
        copper grown by its own track / via size."""
        for g in self.all:
            g._stamp_view(job, delta)

    def _stamp_view(self, job, delta):
        lib = core()
        G = self.G
        if job.pre is not None:                 # a kept net: the exact cells its real copper keeps this class out of
            idx_t, idx_v = job.pre["views"][id(self)]
            k = np.uint16(job.pre["weight"] * job.wmul)
            for l, idx in idx_t.items():
                flat = self.occt[l].reshape(-1)
                if delta > 0:
                    flat[idx] += k
                else:
                    flat[idx] -= k
            if len(idx_v):
                flat = self.occv.reshape(-1)
                if delta > 0:
                    flat[idx_v] += k
                else:
                    flat[idx_v] -= k
        if not job.pts and not job.vias:
            return
        if job.g is self:                       # where this class's new routes run (the kept nets' conflict test)
            one = np.uint8(1)
            for l, (pi, pj) in job.pts.items():
                if delta > 0:
                    self.trk[l, pj, pi] += one
                else:
                    self.trk[l, pj, pi] -= one
            for (vi_, vj_) in job.vias:
                if delta > 0:
                    self.viac[vj_, vi_] += one
                else:
                    self.viac[vj_, vi_] -= one
        delta *= job.wmul
        o = job.g                               # the job's own class
        cl, hcl, h2h = max(o.cl, self.cl), self.rules.hcl, self.rules.h2h
        if o.primary != self.primary:
            cl = max(cl, self.rules.iso_gap)
        r_tt = o.w / 2 + cl + self.w / 2 + EPS
        r_tv = max(o.vd / 2 + cl + self.w / 2, o.vh / 2 + hcl + self.w / 2) + EPS          # its via, seen by a track here
        r_vt = max(o.w / 2 + cl + self.vd / 2, o.w / 2 + hcl + self.vh / 2) + EPS                                            # its track, seen by a via here
        r_vv = max(o.vd / 2 + self.vd / 2 + cl, o.vh / 2 + self.vh / 2 + h2h, o.vh / 2 + hcl + self.vd / 2, self.vh / 2 + hcl + o.vd / 2) + EPS
        r2tt, r2tv, r2vt, r2vv = (r_tt / G) ** 2, (r_tv / G) ** 2, (r_vt / G) ** 2, (r_vv / G) ** 2
        vi = np.array([v[0] for v in job.vias], np.int32)
        vj = np.array([v[1] for v in job.vias], np.int32)
        allv_i, allv_j, allv_r = [vi], [vj], [np.full(len(vi), r2vv, np.float32)]
        for l in range(self.L):
            p = job.pts.get(l)
            pi = p[0] if p is not None else np.zeros(0, np.int32)
            pj = p[1] if p is not None else np.zeros(0, np.int32)
            if len(pi) == 0 and len(vi) == 0:
                continue
            ci = np.ascontiguousarray(np.concatenate([pi, vi]), np.int32)
            cj = np.ascontiguousarray(np.concatenate([pj, vj]), np.int32)
            cr = np.ascontiguousarray(np.concatenate([np.full(len(pi), r2tt, np.float32), np.full(len(vi), r2tv, np.float32)]))
            self.epoch += 1
            lib.stamp(ptr(self.occt[l]), self.W, self.H, ptr(ci), ptr(cj), ptr(cr), len(ci), delta, ptr(self.mark), self.epoch)
            if len(pi):
                allv_i.append(pi)
                allv_j.append(pj)
                allv_r.append(np.full(len(pi), r2vt, np.float32))
        ci = np.ascontiguousarray(np.concatenate(allv_i), np.int32)
        cj = np.ascontiguousarray(np.concatenate(allv_j), np.int32)
        cr = np.ascontiguousarray(np.concatenate(allv_r), np.float32)
        self.epoch += 1
        lib.stamp(ptr(self.occv), self.W, self.H, ptr(ci), ptr(cj), ptr(cr), len(ci), delta, ptr(self.mark), self.epoch)

    def search(self, net, starts, goals, box, pres, viacost, maxexp=6000000):
        lib = core()
        i0, j0, i1, j1 = box
        st = np.ascontiguousarray(starts, np.int64)
        gs = np.ascontiguousarray(goals, np.int64)
        gc = gs % self.N
        gi, gj = gc % self.W, gc // self.W
        sel = (gi >= i0) & (gi < i1) & (gj >= j0) & (gj < j1)
        if not sel.any():
            return 0
        gs, gi, gj = gs[sel], gi[sel], gj[sel]
        self.goal[gs] = 1
        la = np.ones(self.L, np.uint8)
        out = np.zeros(400000, np.int64)
        n = lib.astar(self.W, self.H, self.L, ptr(self.tho), ptr(self.vho), ptr(self.occt), ptr(self.occv), ptr(self.hist),
                      ptr(self.histv), ptr(self.lcost), ptr(la), self.nid(net), pres, viacost, i0, j0, i1, j1,
                      ptr(st), len(st), ptr(self.goal), 0, int(gi.min()), int(gj.min()), int(gi.max()), int(gj.max()),
                      1.25, maxexp, ptr(out), len(out))
        self.goal[gs] = 0
        return out[:n].copy() if n > 0 else n


# ================================================================================================ board -> grid
def pad_shape(p):
    x, y = ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)
    try:
        sz = p.GetSize()
    except TypeError:
        sz = p.GetSize(pcbnew.F_Cu)
    sx, sy = ToMM(sz.x) / 2, ToMM(sz.y) / 2
    try:
        shp = p.GetShape()
    except TypeError:
        shp = p.GetShape(pcbnew.F_Cu)
    rot = p.GetOrientationDegrees() % 360
    if abs(rot - round(rot)) < 1e-6:
        rot = int(round(rot))
    if shp == pcbnew.PAD_SHAPE_CIRCLE:
        return ("circle", x, y, sx, sx, 0, 0.0)
    if shp == pcbnew.PAD_SHAPE_OVAL:
        return ("oval", x, y, sx, sy, rot, 0.0)
    if shp == pcbnew.PAD_SHAPE_CUSTOM:
        bb = p.GetBoundingBox()
        return ("rect", ToMM(bb.GetCenter().x), ToMM(bb.GetCenter().y), ToMM(bb.GetWidth()) / 2, ToMM(bb.GetHeight()) / 2, 0, 0.0)
    rr = 0.0
    if shp == pcbnew.PAD_SHAPE_ROUNDRECT:
        try:
            rr = ToMM(p.GetRoundRectCornerRadius())
        except TypeError:
            rr = ToMM(p.GetRoundRectCornerRadius(pcbnew.F_Cu))
    return ("rect", x, y, sx, sy, rot, rr)


class Ctx:
    """The board's stack and the handful of helpers that need it."""

    def __init__(self, board):
        self.board = board
        self.layer_ids = [int(l) for l in board.GetEnabledLayers().CuStack()]
        self.lidx = {l: k for k, l in enumerate(self.layer_ids)}
        self.F, self.B = self.lidx[pcbnew.F_Cu], self.lidx[pcbnew.B_Cu]
        self.names = [str(board.GetStandardLayerName(l)) for l in self.layer_ids]       # "F.Cu", "In1.Cu", ... "B.Cu"

    def pad_layers(self, p):
        if p.HasHole():
            return list(range(len(self.layer_ids)))
        out = []
        if p.IsOnLayer(pcbnew.F_Cu):
            out.append(self.F)
        if p.IsOnLayer(pcbnew.B_Cu):
            out.append(self.B)
        return out

    def via_layers(self, v):
        try:
            a, b = self.lidx[int(v.TopLayer())], self.lidx[int(v.BottomLayer())]
        except Exception:
            a, b = 0, len(self.layer_ids) - 1
        return list(range(min(a, b), max(a, b) + 1))


def via_size(v):
    try:
        return ToMM(v.GetWidth(pcbnew.F_Cu)), ToMM(v.GetDrill())
    except TypeError:
        return ToMM(v.GetWidth()), ToMM(v.GetDrill())


def arc_points(a, m, b, step=0.1):
    """Polyline along the arc through a, m, b (mm)."""
    ax, ay, bx, by, cx, cy = a[0], a[1], m[0], m[1], b[0], b[1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [a, b]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a0, a1, a2 = math.atan2(ay - uy, ax - ux), math.atan2(by - uy, bx - ux), math.atan2(cy - uy, cx - ux)

    def norm(t):
        return t % (2 * math.pi)
    sweep = norm(a2 - a0)
    if norm(a1 - a0) > sweep:                   # the middle is on the other way round
        sweep -= 2 * math.pi
    n = max(2, int(abs(sweep) * r / step) + 1)
    return [(ux + r * math.cos(a0 + sweep * k / n), uy + r * math.sin(a0 + sweep * k / n)) for k in range(n + 1)]


def track_points(t):
    a = (ToMM(t.GetStart().x), ToMM(t.GetStart().y))
    b = (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
    if t.GetClass() == "PCB_ARC":
        m = (ToMM(t.GetMid().x), ToMM(t.GetMid().y))
        return arc_points(a, m, b)
    return [a, b]


def edge_lines(board):
    """Every Edge.Cuts line of the board and of its footprints as straight pieces [(a, b)]."""
    out = []

    def chain(pts, closed=False):
        for k in range(len(pts) - 1):
            out.append((pts[k], pts[k + 1]))
        if closed and len(pts) > 2:
            out.append((pts[-1], pts[0]))

    def mm(v):
        return (ToMM(v.x), ToMM(v.y))
    items = list(board.GetDrawings())
    for fp in board.GetFootprints():
        items += list(fp.GraphicalItems())
    for d in items:
        if d.GetLayer() != pcbnew.Edge_Cuts or d.GetClass() != "PCB_SHAPE":
            continue
        s = d.GetShape()
        if s == pcbnew.SHAPE_T_SEGMENT:
            chain([mm(d.GetStart()), mm(d.GetEnd())])
        elif s == pcbnew.SHAPE_T_ARC:
            chain(arc_points(mm(d.GetStart()), mm(d.GetArcMid()), mm(d.GetEnd()), 0.05))
        elif s == pcbnew.SHAPE_T_CIRCLE:
            c = mm(d.GetCenter())
            r = ToMM(d.GetRadius())
            n = max(12, int(2 * math.pi * r / 0.05))
            chain([(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)) for k in range(n)], True)
        elif s == pcbnew.SHAPE_T_RECT:
            a, b = mm(d.GetStart()), mm(d.GetEnd())
            chain([a, (b[0], a[1]), b, (a[0], b[1])], True)
        elif s == pcbnew.SHAPE_T_POLY:
            ps = d.GetPolyShape()
            for oi in range(ps.OutlineCount()):
                ch = ps.Outline(oi)
                chain([mm(ch.CPoint(k)) for k in range(ch.PointCount())], True)
        elif s == pcbnew.SHAPE_T_BEZIER:
            try:
                d.RebuildBezierToSegmentsPointsList(FromMM(0.02))
            except Exception:
                pass
            chain([mm(q) for q in d.GetBezierPoints()])
    return out


def chain_rings(sps, oi):
    rings = []
    for ch in [sps.Outline(oi)] + [sps.Hole(oi, h) for h in range(sps.HoleCount(oi))]:
        rings.append([(ToMM(ch.CPoint(k).x), ToMM(ch.CPoint(k).y)) for k in range(ch.PointCount())])
    return [r for r in rings if len(r) >= 3]


def build_grids(board, ctx, cfg, rules):
    """One grid per track class of the run (cfg "classes", or the single class w / via / cl): the same board seen by a
    track and a via of that size.  They share the history costs and the net numbers."""
    classes = cfg.get("classes") or [{"nets": [".*"], "w": cfg["w"], "via": cfg["via"], "cl": cfg["cl"]}]
    # a class none of whose nets has a pad in the window needs no grid (each one costs memory and set-up time)
    x0, y0, x1, y1 = cfg["window"]
    present = {p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads()
               if p.GetNetname() and x0 <= ToMM(p.GetPosition().x) <= x1 and y0 <= ToMM(p.GetPosition().y) <= y1}
    # ... and a class whose nets belong to KiCad net classes with different clearances gets one grid per clearance
    # (two nets keep the larger of their two net-class clearances: each grid's nets all ask for the same)
    used, taken = [], set()
    for c in classes:
        mine = {n for n in present - taken if any(re.fullmatch(q, n) for q in c["nets"])}
        taken |= mine
        cls = sorted({round(max(c["cl"], rules.cl_of(n)), 4) for n in mine}) or ([c["cl"]] if c is classes[-1] else [])
        for k in cls:
            used.append((c, k))
    grids = []
    for c, k in used:
        g = build_grid(board, ctx, cfg, rules, (c["w"], c["via"][0], c["via"][1], k), grids[0] if grids else None,
                       bool(c.get("primary")))
        g.pats = [re.compile(p) for p in c["nets"]]
        # a class may carry keep-outs of its own ("novia" / "notrack" as in the run's): e.g. the through traffic stays
        # off the outer layers of a connector's break-out area, which is left to that connector's own nets
        for bx in c.get("novia") or []:
            i0, j0, i1, j1 = g._box(*bx)
            g.vho[j0:j1, i0:i1] = MULTI
        for nt in c.get("notrack") or []:
            i0, j0, i1, j1 = g._box(*nt[1:])
            g.tho[ctx.names.index(nt[0]), j0:j1, i0:i1] = MULTI
        g.cname = c.get("name", "%.2f" % c["w"])
        g.base_cl = c["cl"]
        g.name = g.cname if sum(1 for c2, _ in used if c2 is c) == 1 else "%s/%.3g" % (g.cname, k)
        grids.append(g)
    for g in grids:
        g.all = grids
        g.tight = bool(cfg.get("tight", True))
    return grids


def build_grid(board, ctx, cfg, rules, cls, first, primary=False):
    win = cfg["window"]
    route_idx = [ctx.names.index(n) for n in cfg["layers"]]
    grid = Grid(win, cfg.get("grid", 0.05), ctx.layer_ids, route_idx, cfg.get("lcost") or [1.0] * len(route_idx), cls, rules)
    grid.primary = primary
    if first is not None:
        grid.hist, grid.histv, grid.netid = first.hist, first.histv, first.netid
    w, vd, vh = grid.w, grid.vd, grid.vh
    reach = 2.0
    x0, y0, x1, y1 = win

    def near(x, y, r=0.0):
        return x0 - reach - r <= x <= x1 + reach + r and y0 - reach - r <= y <= y1 + reach + r
    vip_refs = set(cfg.get("via_in_pad_refs") or [])       # e.g. the BGAs: a via may stand in these parts' pads
    for fp in board.GetFootprints():
        via_in_pad = bool(cfg.get("via_in_pad")) or fp.GetReference() in vip_refs
        for p in fp.Pads():
            ls = ctx.pad_layers(p)
            if not ls:
                continue
            sh = pad_shape(p)
            if not near(sh[1], sh[2], max(sh[3], sh[4])):
                continue
            npth = p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
            net = None if npth else (p.GetNetname() or None)
            cl = grid.cl_with(net)
            if p.HasHole():
                hx, hy = ToMM(p.GetDrillSize().x) / 2, ToMM(p.GetDrillSize().y) / 2
                hole = ("oval", sh[1], sh[2], hx, hy, sh[5], 0.0)
                if npth:                        # a non-plated hole is a piece of board edge
                    grid.hard_shape(ls, hole, net, max(rules.hcl, rules.edge) + w / 2 + EPS,
                                    max(rules.h2h + vh / 2, max(rules.hcl, rules.edge) + vd / 2) + EPS)
                    continue
                grid.hard_shape(ls, hole, net, rules.hcl + w / 2 + EPS, max(rules.h2h + vh / 2, rules.hcl + vd / 2) + EPS)
            grid.hard_shape(ls, sh, net, cl + w / 2 + EPS, max(cl + vd / 2, rules.hcl + vh / 2) + EPS)
            if not via_in_pad and not p.HasHole():      # no via whose hole would sit in a soldered pad, its own net's either
                i0, j0, i1, j1, d = grid.dist(sh, vh / 2 + 0.05)
                if d.size:
                    grid.vho[j0:j1, i0:i1][d < vh / 2 + 0.05] = MULTI
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
            if near(x, y):
                d, h = via_size(t)
                grid.hard_via(x, y, t.GetNetname(), d, h, ctx.via_layers(t))
        elif int(t.GetLayer()) in ctx.lidx:
            pts = track_points(t)
            l = ctx.lidx[int(t.GetLayer())]
            for a, b in zip(pts[:-1], pts[1:]):
                if max(a[0], b[0]) < x0 - reach or min(a[0], b[0]) > x1 + reach or max(a[1], b[1]) < y0 - reach or min(a[1], b[1]) > y1 + reach:
                    continue
                grid.hard_segment([l], a, b, t.GetNetname(), ToMM(t.GetWidth()))
    for a, b in edge_lines(board):
        if max(a[0], b[0]) < x0 - reach or min(a[0], b[0]) > x1 + reach or max(a[1], b[1]) < y0 - reach or min(a[1], b[1]) > y1 + reach:
            continue
        grid.wall(a, b, rules.edge + w / 2 + EPS, rules.edge + vd / 2 + EPS)
    # keep-out rule areas of the board and of its footprints
    zones = list(board.Zones())
    for fp in board.GetFootprints():
        zones += list(fp.Zones())
    for z in zones:
        if not z.GetIsRuleArea():
            continue
        lset = z.GetLayerSet()
        ls = [k for k, lay in enumerate(ctx.layer_ids) if lset.Contains(lay)] if z.GetDoNotAllowTracks() else []
        ol = z.Outline()
        for oi in range(ol.OutlineCount()):
            rings = chain_rings(ol, oi)[:1]
            if not rings:
                continue
            for l in ls:
                grid.reserve(l, rings, w / 2 + EPS)
            if z.GetDoNotAllowVias():
                grid.reserve(None, rings, vd / 2 + EPS)
    for bx in cfg.get("novia") or []:
        i0, j0, i1, j1 = grid._box(*bx)
        grid.vho[j0:j1, i0:i1] = MULTI
    for nt in cfg.get("notrack") or []:
        i0, j0, i1, j1 = grid._box(*nt[1:])
        grid.tho[ctx.names.index(nt[0]), j0:j1, i0:i1] = MULTI
    return grid


# ================================================================================================ jobs
class Cluster:
    def __init__(self):
        self.cells = []         # arrays of global states: the island's copper
        self.zone = []          # arrays of global states: its zone fills (targets only)
        self.names = []
        self.probes = []        # (layer index, x, y, accuracy mm)
        self.zuids = set()


class Job:
    def __init__(self, k, net, clusters, own):
        self.k, self.net = k, net
        self.cl, self.own = clusters, own       # the islands being joined now; the cells of the net's fixed copper
        self.scratch = None                     # a soft net: (islands, own) without its kept copper
        self.paths, self.vias, self.pts = [], [], {}
        self.segs = []          # the straightened tracks [(layer, (i, j), (i, j))] the cells of pts come from
        self.ok = False
        self.fails = 0
        self.why = ""
        self.open = []          # islands no way was found for (the rest of the net is routed)
        self.pre = None         # a soft net's own copper as it was on the board: kept unless it is in the way
        self.giveup = False     # ... and now it is: next time the net is routed from its pads
        self.kept0 = None       # (pre, islands, own) as the net came: what the safety net puts back
        self.wmul = 1           # > 1 for a while in the repair step: this job's copper is then all but a wall
        self.bad_rounds = 0
        self.kept_hits = 0

    def clear(self):
        """Nothing routed; a soft net gives up its kept copper and starts again from its pads."""
        self.paths, self.vias, self.pts, self.ok, self.open = [], [], {}, False, []
        self.segs = []
        if self.pre is not None:
            self.pre = None
            self.cl, self.own = self.scratch

    def clear_new(self):
        """A soft net in kept mode: only the links added to its kept copper go."""
        self.paths, self.vias, self.pts, self.open = [], [], {}, []
        self.segs = []

    def set_geometry(self, grid):
        per, vias = {}, []
        # tight: the route is pulled straight right away (against the others' present zones), so that it takes the room
        # of a straight track and not of the grid's staircase - in a narrow pocket that decides whether two nets fit
        tight = getattr(grid, "tight", False)
        keep = ({int(p[0]) for p in self.paths} | {int(p[-1]) for p in self.paths}) if tight else None
        self.segs = []
        for path in self.paths:
            ls = path // grid.N
            cs = path % grid.N
            if tight:
                for (l, a, b) in smooth(grid, self.net, path, keep):
                    self.segs.append((int(l), a, b))
                    n = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))))
                    t = np.linspace(0, 1, n + 1)
                    xi = np.rint(a[0] + (b[0] - a[0]) * t).astype(np.int64)
                    yj = np.rint(a[1] + (b[1] - a[1]) * t).astype(np.int64)
                    per.setdefault(int(l), []).append(yj * grid.W + xi)
            else:
                for l in np.unique(ls):
                    per.setdefault(int(l), []).append(cs[ls == l])
            ch = np.nonzero(ls[1:] != ls[:-1])[0]
            for c_ in cs[ch]:
                vias.append((int(c_ % grid.W), int(c_ // grid.W)))
        self.vias = sorted(set(vias))
        self.pts = self.off_own(grid, {l: np.unique(np.concatenate(parts)) for l, parts in per.items()})

    def off_own(self, grid, per):
        """{layer: cells} -> {layer: (i, j)} without the cells on the net's own fixed copper: a route's first and last
        steps run on its pad or on the track it joins, where the fixed copper's own clearance already holds - they
        are no new copper, and must not count as being in a neighbour's way."""
        own = getattr(self, "own", None)
        out = {}
        for l, cells in per.items():
            if own is not None and len(own) and len(cells):
                st = l * grid.N + cells
                k = np.searchsorted(own, st)
                k[k >= len(own)] = len(own) - 1
                cells = cells[own[k] != st]
            if len(cells):
                out[l] = ((cells % grid.W).astype(np.int32), (cells // grid.W).astype(np.int32))
        return out


def states_of(grid, layers, i0, j0, m):
    if not m.size or not m.any():
        return np.zeros(0, np.int64)
    jj, ii = np.nonzero(m)
    c = (jj + j0).astype(np.int64) * grid.W + (ii + i0)
    return np.concatenate([l * grid.N + c for l in layers])


def kept_views(ctx, grid, net, items):
    """A soft net's own copper as it was on the board, for every class's grid: the exact cells where a track centre /
    a via centre of that class would be too close to it."""
    W = grid.W
    hcl, h2h = grid.rules.hcl, grid.rules.h2h
    views = {}
    for g in grid.all:
        cl = g.cl_with(net)
        per_t, per_v = {}, []
        for it in items:
            if it[0] == "trk":
                _, ax, ay, bx, by, w, lname = it
                l = ctx.names.index(lname)
                for r, dst in ((w / 2 + cl + g.w / 2 + EPS, per_t.setdefault(l, [])),
                               (max(w / 2 + cl + g.vd / 2, w / 2 + hcl + g.vh / 2) + EPS, per_v)):
                    i0, j0, i1, j1, d2 = g.seg_d2((ax, ay), (bx, by), r)
                    if d2.size:
                        jj, ii = np.nonzero(d2 < r * r - 1e-9)
                        dst.append((jj + j0).astype(np.int64) * W + (ii + i0))
            else:
                _, x, y, d, h, top, bot = it
                la, lb = ctx.names.index(top), ctx.names.index(bot)
                sh = ("circle", x, y, 0.0, 0.0, 0, 0.0)
                rt = max(d / 2 + cl + g.w / 2, h / 2 + hcl + g.w / 2) + EPS
                i0, j0, i1, j1, dd = g.dist(sh, rt)
                if dd.size:
                    jj, ii = np.nonzero(dd < rt - 1e-9)
                    c_ = (jj + j0).astype(np.int64) * W + (ii + i0)
                    for l in range(min(la, lb), max(la, lb) + 1):
                        per_t.setdefault(l, []).append(c_)
                rv = max(d / 2 + g.vd / 2 + cl, h / 2 + g.vh / 2 + h2h, h / 2 + hcl + g.vd / 2, g.vh / 2 + hcl + d / 2) + EPS
                i0, j0, i1, j1, dd = g.dist(sh, rv)
                if dd.size:
                    jj, ii = np.nonzero(dd < rv - 1e-9)
                    per_v.append((jj + j0).astype(np.int64) * W + (ii + i0))
        views[id(g)] = ({l: np.unique(np.concatenate(v)) for l, v in per_t.items() if v},
                        np.unique(np.concatenate(per_v)) if per_v else np.zeros(0, np.int64))
    return views


class Side:
    """One board file's view of the nets: their pads / tracks / vias, their zones, KiCad's connectivity."""

    def __init__(self, board, ctx):
        self.board = board
        self.items = {}
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            for p in fp.Pads():
                n = p.GetNetname()
                if n and ctx.pad_layers(p):
                    self.items.setdefault(n, []).append(("pad", p, ref + "." + p.GetNumber()))
        for t in board.GetTracks():
            n = t.GetNetname()
            if n:
                self.items.setdefault(n, []).append(("via" if t.GetClass() == "PCB_VIA" else "trk", t, ""))
        self.zones = {}
        for z in board.Zones():
            if not z.GetIsRuleArea() and z.GetNetname():
                self.zones.setdefault(z.GetNetname(), []).append(z)
        board.BuildConnectivity()
        self.conn = board.GetConnectivity()


def net_islands(side, ctx, grids, g_net, n, win):
    """The islands of net n inside the window: [Cluster] with their start / goal cells."""
    grid = grids[0]
    x0, y0, x1, y1 = win
    margin = 0.02
    its = side.items.get(n, [])
    byuid = {o.m_Uuid.AsString(): (kind, o, name) for kind, o, name in its}
    seen = set()
    clusters = []
    for kind, o, name in its:
        u = o.m_Uuid.AsString()
        if u in seen:
            continue
        group = [u]
        zu = set()
        for q in side.conn.GetConnectedItems(o, 0):
            qu = q.m_Uuid.AsString()
            if qu in byuid:
                group.append(qu)
            elif q.GetClass() == "ZONE":
                zu.add(qu)
        c = Cluster()
        c.zuids = zu
        for qu in set(group):
            seen.add(qu)
            k2, o2, name2 = byuid[qu]
            if k2 == "pad":
                sh = pad_shape(o2)
                ls = ctx.pad_layers(o2)
                i0, j0, i1, j1, d = grid.dist(sh, 0.0, rounded=True)
                st = states_of(grid, ls, i0, j0, d < -margin) if d.size else np.zeros(0, np.int64)
                if not len(st) and x0 <= sh[1] <= x1 and y0 <= sh[2] <= y1:     # a pad smaller than the grid: its centre
                    ci, cj = grid.cell(sh[1], sh[2])
                    st = np.array([l * grid.N + cj * grid.W + ci for l in ls], np.int64)
                c.cells.append(st)
                c.names.append(name2)
                for l in ls:
                    c.probes.append((l, sh[1], sh[2], max(sh[3], sh[4])))
            elif k2 == "via":
                x, y = ToMM(o2.GetPosition().x), ToMM(o2.GetPosition().y)
                d_, _h = via_size(o2)
                ls = ctx.via_layers(o2)
                i0, j0, i1, j1, d = grid.dist(("circle", x, y, d_ / 2, 0, 0, 0), 0.0)
                if d.size:
                    c.cells.append(states_of(grid, ls, i0, j0, d < -margin))
                for l in ls:
                    c.probes.append((l, x, y, d_ / 2))
            else:
                if int(o2.GetLayer()) not in ctx.lidx:
                    continue
                l = ctx.lidx[int(o2.GetLayer())]
                pts = track_points(o2)
                r = max(ToMM(o2.GetWidth()) / 2 - 0.005, 0.6 * grid.G)
                for a, b in zip(pts[:-1], pts[1:]):
                    i0, j0, i1, j1, d2 = grid.seg_d2(a, b, r)
                    if d2.size:
                        c.cells.append(states_of(grid, [l], i0, j0, d2 < r * r))
                for q in (pts[0], pts[-1]):
                    c.probes.append((l, q[0], q[1], ToMM(o2.GetWidth()) / 2))
        c.cells = np.unique(np.concatenate(c.cells)) if c.cells else np.zeros(0, np.int64)
        clusters.append(c)
    # zone fills: every island of a fill belongs to the cluster one of whose items sits on it
    taken = set()
    for c in sorted(clusters, key=lambda c_: -len(c_.probes)):
        for z in side.zones.get(n, []):
            zu = z.m_Uuid.AsString()
            if c.zuids and zu not in c.zuids:
                continue
            for lay in z.GetLayerSet().CuStack():
                lay = int(lay)
                if lay not in ctx.lidx:
                    continue
                l = ctx.lidx[lay]
                fill = z.GetFilledPolysList(lay)
                pr = [q for q in c.probes if q[0] == l]
                if not pr:
                    continue
                for oi in range(fill.OutlineCount()):
                    if (zu, lay, oi) in taken:
                        continue
                    bb = fill.Outline(oi).BBox()
                    bx0, by0, bx1, by1 = ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())
                    if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
                        continue
                    hit = False
                    for (_, px, py, acc) in pr[:400]:
                        if bx0 - acc <= px <= bx1 + acc and by0 - acc <= py <= by1 + acc and \
                                fill.Contains(VECTOR2I(FromMM(px), FromMM(py)), oi, FromMM(acc)):
                            hit = True
                            break
                    if not hit:
                        continue
                    taken.add((zu, lay, oi))
                    i0, j0, i1, j1, m = grid.poly_mask(chain_rings(fill, oi))
                    if m.size:
                        m = grid.erode(m, int(math.ceil((0.12 + g_net.vd / 2) / grid.G)))
                        st = states_of(grid, [l], i0, j0, m)
                        c.zone.append(st)
                        if l not in grid.route_idx and len(st):     # a plane layer: this net may land on its fill
                            jj, ii = np.nonzero(m)
                            for g in grids:
                                g.tho[l, jj + j0, ii + i0] = grid.nid(n)
        c.zone = np.unique(np.concatenate(c.zone)) if c.zone else np.zeros(0, np.int64)
    live = [c for c in clusters if len(c.cells)]
    nid = grid.nid(n)
    for c in live:
        own = g_net.tho.reshape(-1)[c.cells]
        okc = c.cells[(own == FREE) | (own == nid)]
        c.starts = okc if len(okc) else c.cells
        c.goals = np.unique(np.concatenate([c.cells, c.zone]))
        cc = c.cells % grid.N
        ci, cj = cc % grid.W, cc // grid.W
        c.bbox = (int(ci.min()), int(cj.min()), int(ci.max()), int(cj.max()))
    return live


def make_jobs(board, orig, ctx, grids, cfg, soft=None):
    """board: the file being routed (soft nets' copper already taken out).  orig: the same board with that copper
    still in place (None when there are no soft nets): a soft net's islands WITH its copper are what is still to join."""
    soft = soft or {}
    grid = grids[0]                             # (geometry is the same in all of them)

    def pick(net):
        first = next((g for g in grids if any(r.fullmatch(net) for r in g.pats)), grids[-1])
        need = max(first.base_cl, grid.rules.cl_of(net))
        same = [g for g in grids if g.cname == first.cname]
        return min(same, key=lambda g: (g.cl < need - 1e-9, abs(g.cl - need)))
    want = [re.compile(p) for p in cfg["nets"]]
    skip = [re.compile(p) for p in cfg.get("exclude") or []]
    win = cfg["window"]
    side = Side(board, ctx)
    side_o = Side(orig, ctx) if orig is not None else None
    weight = int(cfg.get("soft_weight", 8))
    jobs = []
    readd = []

    def own_of(live):
        return np.unique(np.concatenate([c.cells for c in live])) if live else np.zeros(0, np.int64)

    for n in sorted(side.items):
        is_soft = bool(n in soft and soft[n]["items"]) and side_o is not None
        if not is_soft and (not any(r.fullmatch(n) for r in want) or any(r.fullmatch(n) for r in skip)):
            continue
        g = pick(n)
        # a net that is not soft but has a pour (a plane net kept as it is): its islands are counted on the board WITH
        # the soft copper - tracks of others on its plane layer may have cut pockets out of the fill
        cut_side = side_o if (side_o is not None and not is_soft and n in side_o.zones) else side
        live_b = net_islands(cut_side, ctx, grids, g, n, win)
        if is_soft:
            items = soft[n]["items"]
            live_a = net_islands(side_o, ctx, grids, g, n, win)
            if len(live_b) >= 2 and live_a:
                j = Job(len(jobs), n, live_a, None)
                j.g = g
                j.scratch = (live_b, own_of(live_b))
                views = kept_views(ctx, grid, n, items)
                idx_t, idx_v = views[id(g)]
                j.own = own_of(live_a)
                j.pre = {"items": items, "views": views, "weight": weight, "own_t": idx_t, "own_v": idx_v}
                j.kept0 = (j.pre, j.cl, j.own)
                j.ok = True
                grid.stamp_job(j, +1)
                jobs.append(j)
                continue
            # it cannot be routed from its pads here (its copper leaves the window): the copper stays, fixed
            for it in items:
                for gg in grids:
                    if it[0] == "trk":
                        gg.hard_segment([ctx.names.index(it[6])], (it[1], it[2]), (it[3], it[4]), n, it[5])
                    else:
                        la, lb = ctx.names.index(it[5]), ctx.names.index(it[6])
                        gg.hard_via(it[1], it[2], n, it[3], it[4], list(range(min(la, lb), max(la, lb) + 1)))
            readd.append((n, items))
            if len(live_a) >= 2:
                jobs.append(Job(len(jobs), n, live_a, own_of(live_a)))
                jobs[-1].g = g
            continue
        if len(live_b) < 2:
            continue
        jobs.append(Job(len(jobs), n, live_b, own_of(live_b)))
        jobs[-1].g = g
    grid.readd = readd
    # pairs: each half is drawn towards the other's route
    byname = {j.net: j for j in jobs}
    for j in jobs:
        j.partner = None
        cand = set()
        for k, ch in enumerate(j.net):
            for a, b in (("P", "N"), ("N", "P"), ("P", "M"), ("M", "P")):
                if ch == a:
                    o = j.net[:k] + b + j.net[k + 1:]
                    if o in byname:
                        cand.add(o)
        if len(cand) == 1 and cfg.get("pairs", True):
            j.partner = byname[cand.pop()]
    return jobs


ATTRACT = 0.55


def attract(grid, other, band):
    lib = core()
    out = []
    scratch = np.zeros((grid.H, grid.W), np.uint16)
    for l, (pi, pj) in other.pts.items():
        scratch[:] = 0
        n = len(pi)
        pi_, pj_ = np.ascontiguousarray(pi, np.int32), np.ascontiguousarray(pj, np.int32)
        for r in (band, grid.r_tt):
            grid.epoch += 1
            r2 = np.full(n, (r / grid.G) ** 2, np.float32)
            lib.stamp(ptr(scratch), grid.W, grid.H, ptr(pi_), ptr(pj_), ptr(r2), n, 1, ptr(grid.mark), grid.epoch)
        idx = np.flatnonzero(scratch == 1)
        grid.hist[l].reshape(-1)[idx] -= ATTRACT
        out.append((l, idx))
    return out


def release(grid, band):
    for l, idx in band:
        grid.hist[l].reshape(-1)[idx] += ATTRACT


# ================================================================================================ routing
def route_job(grid, job, pres, via_cost, margins=(3.0, 8.0), far=(4.0, 12.0)):
    if job.ok:
        grid.stamp_job(job, -1)
    if job.pre is not None and not job.giveup:
        job.clear_new()                         # kept mode: only the missing links are routed
    else:
        job.clear()
    N, W, G = grid.N, grid.W, grid.G
    nc = len(job.cl)
    par = list(range(nc))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    extra = {k: [] for k in range(nc)}
    partner = getattr(job, "partner", None)
    band = attract(grid, partner, grid.r_tt + 0.12) if partner is not None and partner.ok and partner.pts else None
    stuck = set()
    try:
        while True:
            roots = {}
            for k in range(nc):
                roots.setdefault(find(k), []).append(k)
            live = [q for q in roots if q not in stuck]
            if len(roots) == 1 or not live or (len(live) == 1 and len(roots) > 1 and all(q in stuck for q in roots if q != live[0])):
                break
            # (the last live island is not searched from when all the others are stuck: the same ways, backwards)
            r = min(live, key=lambda r_: sum(len(job.cl[k].starts) for k in roots[r_]) + len(extra[r_]))
            starts = np.concatenate([job.cl[k].starts for k in roots[r]] + [np.array(extra[r], np.int64)])
            others = [q for q in roots if q != r]
            goals = np.concatenate([job.cl[k].goals for q in others for k in roots[q]] + [np.array(extra[q], np.int64) for q in others])
            bb = [job.cl[k].bbox for k in roots[r]]
            b0 = (min(b[0] for b in bb), min(b[1] for b in bb), max(b[2] for b in bb), max(b[3] for b in bb))

            def gap(b):
                return max(b[0] - b0[2], b0[0] - b[2], 0) + max(b[1] - b0[3], b0[1] - b[3], 0)
            nb = min((job.cl[k].bbox for q in others for k in roots[q]), key=gap)
            u = (min(b0[0], nb[0]), min(b0[1], nb[1]), max(b0[2], nb[2]), max(b0[3], nb[3]))
            boxes = []
            for base, ms in ((b0, margins), (u, far)):
                for mg in ms:
                    m = int(mg / G)
                    bx = (max(0, base[0] - m), max(0, base[1] - m), min(grid.W, base[2] + m + 1), min(grid.H, base[3] + m + 1))
                    if bx not in boxes:
                        boxes.append(bx)
            res = 0
            for bx in boxes:
                size = (bx[2] - bx[0]) * (bx[3] - bx[1]) * grid.L
                res = grid.search(job.net, starts, goals, bx, pres, via_cost, maxexp=min(size, 60000000))
                if not isinstance(res, int):
                    break
            if isinstance(res, int):
                stuck.add(r)
                continue
            job.paths.append(res)
            end = int(res[-1])
            hit = None
            for q in others:
                for k in roots[q]:
                    g = job.cl[k].goals
                    p = np.searchsorted(g, end)
                    if p < len(g) and g[p] == end:
                        hit = q
                        break
                if hit is None and end in extra[q]:
                    hit = q
                if hit is not None:
                    break
            if hit is None:
                hit = others[0]
            cs = res % N
            ls = res // N
            add = [int(s) for s in res]
            for c_ in cs[np.nonzero(ls[1:] != ls[:-1])[0]]:
                add += [l2 * N + int(c_) for l2 in range(grid.L)]
            par[hit] = r
            stuck.discard(hit)
            extra[r] = extra[r] + extra[hit] + add
    finally:
        if band:
            release(grid, band)
    roots = {}
    for k in range(nc):
        roots.setdefault(find(k), []).append(k)
    job.open = sorted(" ".join(nm for k in roots[q] for nm in job.cl[k].names[:2]) or "(copper)" for q in roots if q in stuck)
    job.why = "; ".join(job.open)
    if job.open:
        job.fails += 1
    if not job.paths and job.pre is None:
        return False
    job.set_geometry(grid)
    job.ok = True
    grid.stamp_job(job, +1)
    return not job.open


def _in(sorted_arr, vals):
    """Which of vals are in the sorted array."""
    if not len(sorted_arr) or not len(vals):
        return np.zeros(len(vals), bool)
    k = np.searchsorted(sorted_arr, vals)
    k[k >= len(sorted_arr)] = len(sorted_arr) - 1
    return sorted_arr[k] == vals


def conflicts(grid, job):
    """How many cells of the job are in someone's way -> (n, track cells, via cells).  A kept net's copper is in
    conflict where a NEW route's track or via of any class stands inside its keep-out cells: the mirror of the
    newcomer's own test (kept nets are never judged against each other - they were so on the board).  The links a
    kept net has added are judged like any new route, except that the net's own kept zone does not count against
    them (and they do not count against it)."""
    bad_t, bad_v = [], []
    n = 0
    job.kept_hits = 0
    W = grid.W
    pre = job.pre
    if pre is not None:
        mine_v = np.array(sorted(vj * W + vi for (vi, vj) in job.vias), np.int64)
        for g in grid.all:
            idx_t, idx_v = pre["views"][id(g)]
            for l, idx in idx_t.items():
                cnt = g.trk[l].reshape(-1)[idx].astype(np.int32)
                if g is job.g and l in job.pts:
                    pi, pj = job.pts[l]
                    cnt -= _in(np.sort(pj.astype(np.int64) * W + pi), idx)
                hit = idx[cnt > 0]
                if len(hit):
                    bad_t.append((l, (hit % W).astype(np.int32), (hit // W).astype(np.int32)))
                    n += len(hit)
            if len(idx_v):
                cnt = g.viac.reshape(-1)[idx_v].astype(np.int32)
                if g is job.g:
                    cnt -= _in(mine_v, idx_v)
                hit = idx_v[cnt > 0]
                bad_v += [(int(c_ % W), int(c_ // W)) for c_ in hit]
                n += len(hit)
        job.kept_hits = n
    k = pre["weight"] if pre is not None else 0
    for l, (pi, pj) in job.pts.items():
        occ = grid.occt[l, pj, pi].astype(np.int32)
        if pre is not None and l in pre["own_t"]:
            occ -= k * _in(pre["own_t"][l], pj.astype(np.int64) * W + pi)
        sel = occ > 1
        if sel.any():
            bad_t.append((l, pi[sel], pj[sel]))
            n += int(sel.sum())
    for (i, j) in job.vias:
        occ = int(grid.occv[j, i])
        if pre is not None and _in(pre["own_v"], np.array([j * W + i], np.int64))[0]:
            occ -= k
        if occ > 1:
            bad_v.append((i, j))
            n += 1
    return n, bad_t, bad_v


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


def smooth(grid, net, path, keep):
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
        cut = [k] + [x for x in range(k + 1, e) if int(path[x]) in keep] + [e]
        for s0, s1 in zip(cut[:-1], cut[1:]):
            segs += _pull(grid, net, ls[k], pts[s0:s1 + 1])
        k = e + 1 if e > k else k + 1
    return segs


def _pull(grid, net, l, run):
    segs = []
    a = 0
    while a < len(run) - 1:
        best, step = a + 1, 1
        while a + step < len(run) and clear_line(grid, net, l, run[a], run[a + step]):
            best = a + step
            step *= 2
        hi, lo = min(len(run) - 1, a + step), best
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


def save(board, dst, pro):
    pcbnew.SaveBoard(dst, board)
    stem = os.path.splitext(dst)[0]
    psrc = os.path.splitext(pro)[0]
    for ext in (".kicad_pro", ".kicad_dru"):
        if os.path.exists(psrc + ext) and os.path.abspath(psrc + ext) != os.path.abspath(stem + ext):
            shutil.copyfile(psrc + ext, stem + ext)
        elif ext == ".kicad_pro" and os.path.exists(psrc + ext):
            pass


def run_route(src, dst, cfg):
    t0 = time.time()
    pro = cfg.get("pro") or os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read()
    rules = Rules(pro)
    # the margin on every distance: tracks are straightened to any angle, between the grid's cell centres, and a
    # straightened track can come nearer to its neighbour than the cells it was checked on by a fraction of a cell
    global EPS
    EPS = 0.002 + 0.2 * float(cfg.get("grid", 0.05))
    if cfg.get("isolation"):
        rules.set_isolation(cfg["isolation"]["nets"], cfg["isolation"]["gap"])
    board = pcbnew.LoadBoard(src)
    ctx = Ctx(board)
    if not cfg.get("window"):
        bb = board.GetBoardEdgesBoundingBox()
        cfg["window"] = [ToMM(bb.GetLeft()) - 0.5, ToMM(bb.GetTop()) - 0.5, ToMM(bb.GetRight()) + 0.5, ToMM(bb.GetBottom()) + 0.5]
    if not cfg.get("layers"):
        cfg["layers"] = [ctx.names[0], ctx.names[-1]]
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    grids = build_grids(board, ctx, cfg, rules)
    grid = grids[0]
    soft = json.load(open(cfg["soft"], encoding="utf-8")) if cfg.get("soft") else {}
    orig = None
    if soft:                                    # the board with the soft nets' copper still in place
        orig = pcbnew.LoadBoard(cfg["orig"])
        pcbnew.ZONE_FILLER(orig).Fill(orig.Zones())
    jobs = make_jobs(board, orig, ctx, grids, cfg, soft)
    via_cost = cfg.get("via_cost", 0.6) / grid.G
    print("  %d nets to join (%d islands), %d more keep their copper unless it is in the way; classes %s; "
          "grid %d x %d x %d layers (%.3f mm), set up in %.0f s"
          % (sum(1 for j in jobs if len(j.cl) > 1), sum(len(j.cl) for j in jobs if len(j.cl) > 1), sum(1 for j in jobs if j.pre is not None),
             ", ".join("%s: %.2f mm, via %.2f / %.2f, cl %.2f, %d nets" % (g.name, g.w, g.vd, g.vh, g.cl, sum(1 for j in jobs if j.g is g))
                       for g in grids), grid.W, grid.H, grid.L, grid.G, time.time() - t0), flush=True)
    log = []

    def snapshot(o):
        return (o.paths, o.vias, o.pts, o.pre, o.open, o.ok, o.cl, o.own, o.giveup, o.segs)

    def restore(o, s):
        o.paths, o.vias, o.pts, o.pre, o.open, o.ok, o.cl, o.own, o.giveup, o.segs = s
        if o.ok:
            grid.stamp_job(o, +1)

    def unstamp(o):
        if o.ok:
            grid.stamp_job(o, -1)
        o.clear()

    def bad(o):
        return (not o.ok) or bool(o.open)

    if jobs:
        iters = int(cfg.get("iters", 40))
        # kept copper is given up during the negotiation only if "soft_patience" says so (rounds in someone's way);
        # by default never: a net that gives its copper up there may end with none at all when the board is full.
        # The repair step below does it instead, all or nothing.
        patience = int(cfg.get("soft_patience", 10 ** 9))
        pres, pf, hinc = 0.6, float(cfg.get("pres_growth", 1.35)), float(cfg.get("hist_inc", 0.4))
        order0 = sorted(jobs, key=lambda j: (-len(j.cl), j.net))
        for it in range(iters):
            full = it < 3 or it % 6 == 0
            # the order rotates: with a fixed order the same nets come last every round and never get their turn
            k0 = (it * 37) % len(order0) if it >= 3 else 0
            order = order0[k0:] + order0[:k0]
            todo = []
            for j in order:
                n = conflicts(j.g, j)[0] if j.ok else 0
                if j.pre is not None:
                    if j.bad_rounds >= patience:        # kept copper that stays in someone's way (or cannot be completed)
                        j.giveup = True
                        todo.append(j)
                    elif len(j.cl) > 1 and (full or n > j.kept_hits or j.open):
                        todo.append(j)
                elif full or not j.ok or n or (j.open and it % 3 == 0):
                    todo.append(j)
            for j in todo:
                route_job(j.g, j, pres, via_cost)
            total, nbad, unrouted = 0, 0, 0
            for j in jobs:
                if bad(j):
                    unrouted += 1
                if not j.ok:
                    continue
                n, bt, bv = conflicts(j.g, j)
                if j.pre is not None:
                    j.bad_rounds = j.bad_rounds + 1 if (j.kept_hits or j.open) else 0
                if n:
                    nbad += 1
                    total += n
                    for l, pi, pj in bt:
                        grid.hist[l, pj, pi] += hinc
                    for (i, jj) in bv:
                        grid.histv[jj, i] += hinc
            log.append("iteration %2d: pressure %7.2f, rerouted %3d, in conflict %3d (%5d cells), with no way %d, copper still kept %d  [%4.0f s]"
                       % (it + 1, pres, len(todo), nbad, total, unrouted, sum(1 for j in jobs if j.pre is not None), time.time() - t0))
            print("  " + log[-1], flush=True)
            if nbad == 0 and unrouted == 0:
                break
            if nbad == 0 and it >= 3:
                break                           # only islands with no way at all are left: more rounds change nothing
            pres = min(pres * pf, 400.0)
        # what is still contested after the last round, and where (for the log: the hot spots of the board)
        hot = []
        for j in jobs:
            if j.ok:
                n, bt, bv = conflicts(j.g, j)
                if n:
                    xs = [grid.x0 + float(v) * grid.G for (_l, pi, _pj) in bt for v in (pi.min(), pi.max())] + [grid.x0 + i * grid.G for (i, _j) in bv]
                    ys = [grid.y0 + float(v) * grid.G for (_l, _pi, pj) in bt for v in (pj.min(), pj.max())] + [grid.y0 + jj * grid.G for (_i, jj) in bv]
                    hot.append((n, "%s%s %d cells x %.1f-%.1f y %.1f-%.1f" % (j.net, " (kept)" if j.pre is not None else "", n,
                                                                             min(xs), max(xs), min(ys), max(ys))))
        if hot:
            log.append("still contested: " + "; ".join(h[1] for h in sorted(hot, reverse=True)[:40]))
            print("  " + log[-1], flush=True)
        # clean-up.  First the links added to kept copper that are still in someone's way: once more, the others as walls.
        for j in jobs:
            if j.ok and j.pre is not None and j.pts:
                n = conflicts(j.g, j)[0]
                if n > j.kept_hits:
                    route_job(j.g, j, -1.0, via_cost, far=(6.0, 16.0))
        # Then drop new routes until nothing is in conflict (kept copper is never dropped here: what stands in its way
        # is always a new route), and route each dropped one again with the others as walls.
        dropped = []
        while True:
            worst = None
            for j in jobs:
                if j.ok and (j.pre is None or j.pts or j.vias):
                    n = conflicts(j.g, j)[0]
                    if j.pre is not None:
                        n -= j.kept_hits
                    if n > 0 and (worst is None or n > worst[0]):
                        worst = (n, j)
            if worst is None:
                break
            j = worst[1]
            grid.stamp_job(j, -1)
            if j.pre is not None:
                j.clear_new()
                grid.stamp_job(j, +1)
            else:
                j.clear()
            dropped.append(j)
        dropped += [j for j in jobs if not j.ok and j not in dropped]
        recovered = 0
        for j in sorted(dropped, key=lambda j_: j_.net):
            if route_job(j.g, j, -1.0, via_cost, margins=(3.0, 8.0), far=(6.0, 16.0)) and conflicts(j.g, j)[0] == 0:
                recovered += 1
            elif j.ok and conflicts(j.g, j)[0] == 0:
                pass                            # partly routed, nothing in conflict: keep what there is
            else:
                grid.stamp_job(j, -1) if j.ok else None
                if j.pre is not None:
                    j.clear_new()
                    grid.stamp_job(j, +1)
                else:
                    j.clear()
        # repair: an open net takes its way through the others; those are routed again around it, or all is undone
        tried = {}
        avoid = {}                              # job -> the jobs that found no new way when it pushed them aside

        def harden(js, mul):
            for o in js:
                if o.ok:
                    grid.stamp_job(o, -1)
                    o.wmul = mul
                    grid.stamp_job(o, +1)
                else:
                    o.wmul = mul
        for rnd in range(int(cfg.get("repair", 40))):
            failed = [j for j in jobs if bad(j) and tried.get(j.k, 0) < int(cfg.get("repair_tries", 6))]
            if not failed:
                break
            j = min(failed, key=lambda j_: tried.get(j_.k, 0))
            tried[j.k] = tried.get(j.k, 0) + 1
            before = snapshot(j)
            n_open = len(j.open) if j.ok else 10 ** 6
            if j.pre is not None and tried[j.k] % 3 == 0:
                j.giveup = True                 # every third try: from the pads
            # (first try: others' copper is dear, second: cheaper - a shorter way through more of them)
            hard_ones = [o for o in avoid.get(j.k, []) if o is not j]
            harden(hard_ones, 60)
            route_job(j.g, j, 30.0 if tried[j.k] % 2 else 4.0, via_cost, far=(6.0, 16.0))
            harden(hard_ones, 1)
            if not j.ok or len(j.open) >= n_open:
                unstamp(j)
                restore(j, before)
                continue
            victims = [o for o in jobs if o is not j and o.ok and conflicts(o.g, o)[0]]
            snap = {o.k: snapshot(o) for o in victims}
            for o in victims:
                unstamp(o)
            good = conflicts(j.g, j)[0] == 0
            culprit = []                        # the pushed-aside nets that found no new way: walls on the next try
            if good:
                for o in sorted(victims, key=lambda o_: -len(o_.cl)):
                    if not (route_job(o.g, o, -1.0, via_cost, far=(6.0, 16.0)) and conflicts(o.g, o)[0] == 0):
                        good = False
                        culprit = [o]
                        break
            if not good and victims and len(victims) <= int(cfg.get("repair_group", 8)):
                # the net and the ones it pushed aside negotiate among themselves, the rest of the board being as good
                # as walls (growing pressure); it counts only if all of them end complete and in nobody's way
                group = [j] + victims
                pk = 3.0
                for rr in range(int(cfg.get("repair_rounds", 12))):
                    for o in group:
                        route_job(o.g, o, pk, via_cost, far=(6.0, 16.0))
                    if all(o.ok and conflicts(o.g, o)[0] == 0 for o in group) and all(len(o.open) <= len(snap[o.k][4]) for o in victims) \
                            and len(j.open) < n_open:
                        good = True
                        break
                    pk = min(pk * 2.2, 400.0)
                if not good:
                    culprit = [o for o in victims if not o.ok or conflicts(o.g, o)[0] or len(o.open) > len(snap[o.k][4])] or culprit
            if not good:
                # (a net with many islands - a supply - then joins what it can without them: partial progress counts)
                avoid.setdefault(j.k, []).extend([o for o in (culprit or victims[:1]) if o not in avoid.get(j.k, [])])
            if good:
                log.append("repair %d: %s routed, %d nets in its way routed again around it" % (rnd + 1, j.net, len(victims)))
            else:
                for o in victims + [j]:
                    unstamp(o)
                for o in victims:
                    restore(o, snap[o.k])
                restore(j, before)
                log.append("repair %d: %s - no way found (%d nets in its way), undone" % (rnd + 1, j.net, len(victims)))
            print("  " + log[-1], flush=True)
        # safety net: a soft net that gave its copper up and then found no complete way gets the old copper back where
        # nothing new stands in its place, and its missing links are tried once more from there; it is kept if that
        # leaves fewer islands open than the attempt from the pads did
        back = 0
        for j in sorted(jobs, key=lambda j_: j_.net):
            if j.kept0 is None or j.pre is not None or not bad(j):
                continue
            before = snapshot(j)
            n_open = len(j.open) if j.ok else len(j.cl) - 1
            if j.ok:
                grid.stamp_job(j, -1)
            j.paths, j.vias, j.pts, j.open, j.segs = [], [], {}, [], []
            j.pre, j.cl, j.own = j.kept0
            j.giveup, j.ok = False, True
            grid.stamp_job(j, +1)
            good = conflicts(j.g, j)[0] == 0
            if good and len(j.cl) > 1:
                route_job(j.g, j, -1.0, via_cost, far=(6.0, 16.0))
                if conflicts(j.g, j)[0]:
                    grid.stamp_job(j, -1)
                    j.clear_new()
                    j.open = ["(links not added)"] * (len(j.cl) - 1)
                    grid.stamp_job(j, +1)
            if good and len(j.open) < max(n_open, 1) + (0 if before[5] else 10 ** 6):
                back += 1
                j.why = "; ".join(j.open)
            else:
                grid.stamp_job(j, -1)
                j.pre = None
                j.ok = False
                restore(j, before)
        if back:
            log.append("safety net: %d nets took their old copper back" % back)
            print("  " + log[-1], flush=True)
        failed = [j for j in jobs if bad(j)]
        log.append("clean-up: %d jobs dropped from conflicts, %d of them routed again with the others as walls; %d nets still open: %s"
                   % (len(dropped), recovered, len(failed), " ".join(sorted("%s(%s)" % (j.net, j.why or "all") for j in failed))))
        print("  " + log[-1], flush=True)
    # smooth and write
    nets = board.GetNetsByName()
    ntr = nvia = 0
    G = grid.G

    def put_back(n, items):
        for it in items:
            if it[0] == "trk":
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(VECTOR2I(FromMM(it[1]), FromMM(it[2])))
                t.SetEnd(VECTOR2I(FromMM(it[3]), FromMM(it[4])))
                t.SetWidth(FromMM(it[5]))
                t.SetLayer(ctx.layer_ids[ctx.names.index(it[6])])
                t.SetNet(nets[n])
                board.Add(t)
            else:
                v = pcbnew.PCB_VIA(board)
                top, bot = ctx.layer_ids[ctx.names.index(it[5])], ctx.layer_ids[ctx.names.index(it[6])]
                v.SetViaType(pcbnew.VIATYPE_THROUGH if (top, bot) == (pcbnew.F_Cu, pcbnew.B_Cu) else pcbnew.VIATYPE_BLIND_BURIED)
                v.SetLayerPair(top, bot)
                v.SetPosition(VECTOR2I(FromMM(it[1]), FromMM(it[2])))
                v.SetDrill(FromMM(it[4]))
                try:
                    v.SetWidth(pcbnew.F_Cu, FromMM(it[3]))
                except TypeError:
                    v.SetWidth(FromMM(it[3]))
                v.SetNet(nets[n])
                board.Add(v)
    nkept = 0
    for n, items in getattr(grid, "readd", []):
        put_back(n, items)
    for j in jobs:
        if j.ok and j.pre is not None:
            put_back(j.net, j.pre["items"])
            nkept += 1
    for j in sorted(jobs, key=lambda j_: j_.k):
        if not j.ok or not j.paths:
            continue
        if grid.tight:
            segs = list(j.segs)                 # exactly what was stamped and negotiated: nothing is straightened again
        else:
            grid.stamp_job(j, -1)
            keep = {int(p[0]) for p in j.paths} | {int(p[-1]) for p in j.paths}
            segs = []
            for path in j.paths:
                segs += smooth(j.g, j.net, path, keep)
            j.pts = j.off_own(grid, {l: pj.astype(np.int64) * grid.W + pi for l, (pi, pj) in raster_segments(grid, segs).items()})
            grid.stamp_job(j, +1)
        net = nets[j.net]
        kept, moved = [], {}
        rv2 = (j.g.r_vv / G) ** 2
        for v in j.vias:
            near = next((k for k in kept if (k[0] - v[0]) ** 2 + (k[1] - v[1]) ** 2 < rv2), None)
            if near is None:
                kept.append(v)
            else:
                moved[v] = near

        def track(a, b, l):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(VECTOR2I(FromMM(grid.x0 + a[0] * G), FromMM(grid.y0 + a[1] * G)))
            t.SetEnd(VECTOR2I(FromMM(grid.x0 + b[0] * G), FromMM(grid.y0 + b[1] * G)))
            t.SetWidth(FromMM(j.g.w))
            t.SetLayer(grid.layer_ids[l])
            t.SetNet(net)
            board.Add(t)
        for (l, a, b) in segs:
            if l not in grid.route_idx:
                continue                        # (a step on a plane layer is the plane itself)
            track(a, b, l)
            ntr += 1
            for e in (a, b):
                if tuple(e) in moved:
                    track(e, moved[tuple(e)], l)
        for (i, jj) in kept:
            v = pcbnew.PCB_VIA(board)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetPosition(VECTOR2I(FromMM(grid.x0 + i * G), FromMM(grid.y0 + jj * G)))
            v.SetDrill(FromMM(j.g.vh))
            try:
                v.SetWidth(pcbnew.F_Cu, FromMM(j.g.vd))
            except TypeError:
                v.SetWidth(FromMM(j.g.vd))
            v.SetNet(net)
            board.Add(v)
            nvia += 1
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    left = board.GetConnectivity().GetUnconnectedCount(True)
    pcbnew.SaveBoard(dst, board)
    stem, psrc = os.path.splitext(dst)[0], os.path.splitext(pro)[0]
    with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
        f.write(pro_text)
    if os.path.exists(psrc + ".kicad_dru") and os.path.abspath(psrc + ".kicad_dru") != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(psrc + ".kicad_dru", stem + ".kicad_dru")
    failed = sorted(j.net for j in jobs if not j.ok or j.open)
    print("  %d tracks, %d vias written, %d nets kept as they were; %d of %d nets fully joined; board now has %d open links -> %s  [%.0f s]"
          % (ntr, nvia, nkept, len(jobs) - len(failed), len(jobs), left, dst, time.time() - t0), flush=True)
    if cfg.get("report"):
        with open(cfg["report"], "w", encoding="utf-8") as f:
            json.dump({"failed": failed, "why": {j.net: j.why for j in jobs if not j.ok or j.open}, "open": left, "log": log}, f, indent=1)


def run_rip(src, dst, cfg):
    pro = cfg.get("pro") or os.path.splitext(src)[0] + ".kicad_pro"
    pro_text = open(pro, encoding="utf-8").read()
    board = pcbnew.LoadBoard(src)
    rip = cfg["rip"]
    want = [re.compile(p) for p in rip["nets"]]
    keep = [re.compile(p) for p in rip.get("keep") or []]
    x0, y0, x1, y1 = rip.get("box") or [-1e9, -1e9, 1e9, 1e9]

    def inside(q):
        return x0 <= q[0] <= x1 and y0 <= q[1] <= y1

    def cut(a, b):
        """The point where a (inside) -> b (outside) leaves the box."""
        t = 1.0
        for (pa, pb, lo, hi) in ((a[0], b[0], x0, x1), (a[1], b[1], y0, y1)):
            if pb > hi:
                t = min(t, (hi - pa) / (pb - pa))
            if pb < lo:
                t = min(t, (lo - pa) / (pb - pa))
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    do_cut = rip.get("cut", True)
    saved = {}                                  # net -> {"complete": .., "items": [...]}  ("save": what was taken out)
    if rip.get("save"):
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        pads = {}
        for fp in board.GetFootprints():
            for p in fp.Pads():
                n = p.GetNetname()
                if n and any(r.fullmatch(n) for r in want) and not any(r.fullmatch(n) for r in keep):
                    pads.setdefault(n, []).append(p)
        for n, ps in pads.items():
            first = {q.m_Uuid.AsString() for q in conn.GetConnectedItems(ps[0], 0)} | {ps[0].m_Uuid.AsString()}
            saved[n] = {"complete": all(p.m_Uuid.AsString() in first for p in ps), "items": []}
    names = {int(l): str(board.GetStandardLayerName(l)) for l in board.GetEnabledLayers().CuStack()}
    hold = rip.get("hold") or []                # boxes whose copper stays where it is (a hand-made fan-out)

    def held(q):
        return any(h[0] <= q[0] <= h[2] and h[1] <= q[1] <= h[3] for h in hold)
    gone, cuts = [], 0
    for t in list(board.GetTracks()):
        n = t.GetNetname()
        if not any(r.fullmatch(n) for r in want) or any(r.fullmatch(n) for r in keep):
            continue
        if t.GetClass() == "PCB_VIA":
            if held((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y))):
                continue
        elif held((ToMM(t.GetStart().x), ToMM(t.GetStart().y))) and held((ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))):
            continue
        if t.GetClass() == "PCB_VIA":
            if inside((ToMM(t.GetPosition().x), ToMM(t.GetPosition().y))):
                gone.append(t)
                d_, h_ = via_size(t)
                saved.setdefault(n, {"complete": False, "items": []})["items"].append(
                    ["via", ToMM(t.GetPosition().x), ToMM(t.GetPosition().y), d_, h_, names[int(t.TopLayer())], names[int(t.BottomLayer())]])
            continue
        if t.GetClass() == "PCB_ARC" or int(t.GetLayer()) not in names:
            continue
        a = (ToMM(t.GetStart().x), ToMM(t.GetStart().y))
        b = (ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
        ia, ib = inside(a), inside(b)
        if ia and ib:
            gone.append(t)
            saved.setdefault(n, {"complete": False, "items": []})["items"].append(
                ["trk", a[0], a[1], b[0], b[1], ToMM(t.GetWidth()), names[int(t.GetLayer())]])
        elif (ia or ib) and do_cut:
            if ia:
                c = cut(a, b)
                t.SetStart(VECTOR2I(FromMM(c[0]), FromMM(c[1])))
            else:
                c = cut(b, a)
                t.SetEnd(VECTOR2I(FromMM(c[0]), FromMM(c[1])))
            cuts += 1
    if rip.get("save"):
        with open(rip["save"], "w", encoding="utf-8") as f:
            json.dump(saved, f)
    for t in gone:
        board.Remove(t)
    pcbnew.SaveBoard(dst, board)
    stem = os.path.splitext(dst)[0]
    with open(stem + ".kicad_pro", "w", encoding="utf-8", newline="") as f:
        f.write(pro_text)
    psrc = os.path.splitext(pro)[0]
    if os.path.exists(psrc + ".kicad_dru") and os.path.abspath(psrc + ".kicad_dru") != os.path.abspath(stem + ".kicad_dru"):
        shutil.copyfile(psrc + ".kicad_dru", stem + ".kicad_dru")
    print("  rip: %d tracks / vias taken out, %d tracks cut at the border -> %s" % (len(gone), cuts, dst), flush=True)


def main():
    src, dst, cfgp = sys.argv[1:4]
    cfg = json.load(open(cfgp, encoding="utf-8"))
    if cfg.get("mode") == "rip":
        run_rip(src, dst, cfg)
    else:
        run_route(src, dst, cfg)


if __name__ == "__main__":
    main()
