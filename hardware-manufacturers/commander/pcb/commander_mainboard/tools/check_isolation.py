#!/usr/bin/env python
"""Measures the gap between PoE-primary copper and everything else (pads, tracks, vias, planes).
Run with KiCad's Python.  The Ethernet head (y < PRI_Y0) is Radxa's own arrangement and is not judged here.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/check_isolation.py      exit code 1 below 2.0 mm
"""
import fnmatch
import math
import os
import sys

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import CFG, OX, OY     # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NL = chr(10)
LIMIT = 2.0
BRIDGES = ("T1", "U31", "C518")      # parts that are allowed to straddle the barrier


def primary(net):
    return bool(net) and (fnmatch.fnmatch(net, "TR?_48V") or (net.startswith("POE_") and net not in ("POE_SEC", "POE_SNUB")))


def box(bb):
    return (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)


def gap(a, b):
    return math.hypot(max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0))


def main():
    b = pcbnew.LoadBoard(os.path.join(ROOT, "commander_mainboard.kicad_pcb"))
    pri, selv = [], []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            r = box(p.GetBoundingBox())
            if (r[1] + r[3]) / 2 < CFG["PRI_Y0"] - 0.2:
                continue
            n = p.GetNetname()
            if primary(n):
                pri.append((r, f"{fp.GetReference()}.{p.GetNumber()} [{n}]"))
            elif n and n != "CHASSIS":
                selv.append((r, f"pad {fp.GetReference()}.{p.GetNumber()} [{n}]", fp.GetReference()))
    for t in b.GetTracks():
        selv.append((box(t.GetBoundingBox()), f"{t.GetClass()} [{t.GetNetname()}]", ""))
    worst = []
    for r, name in pri:
        for s, sname, sref in selv:
            g = gap(r, s)
            if g < LIMIT + 1.0:
                worst.append((g, name, sname))
    # planes: distance from every primary pad to the filled copper of each zone
    zmin = 1e9
    for z in b.Zones():
        for layer in z.GetLayerSet().Seq():
            poly = z.GetFilledPolysList(layer)
            for r, name in pri:
                for x, y in ((r[0], r[1]), (r[2], r[1]), (r[0], r[3]), (r[2], r[3])):
                    d = poly.Distance(pcbnew.VECTOR2I(pcbnew.FromMM(x + OX), pcbnew.FromMM(y + OY)))
                    zmin = min(zmin, ToMM(d))
    worst.sort()
    below = [w for w in worst if w[0] < LIMIT - 1e-6]
    lines = ["", "Isolation check (PoE primary against all other copper, pad boxes, below the Ethernet head):",
             f"  primary pads: {len(pri)}   other pads / tracks / vias checked: {len(selv)}",
             f"  smallest gap to a pad, track or via: {worst[0][0]:.2f} mm ({worst[0][1]} - {worst[0][2]})" if worst else "  nothing within 3 mm",
             f"  smallest gap to a poured plane: {zmin:.2f} mm" if zmin < 1e8 else "  no planes on the board yet",
             f"  pairs below {LIMIT} mm: {len(below)}"] + [f"    {g:.2f} mm  {a}  -  {s}" for g, a, s in below[:20]]
    print(NL.join(lines))
    rep = os.path.join(ROOT, "build", "routing_report.txt")
    if os.path.exists(rep):
        open(rep, "a", encoding="utf-8").write(NL.join(lines) + NL)
    return 1 if below or zmin < LIMIT else 0


if __name__ == "__main__":
    sys.exit(main())
