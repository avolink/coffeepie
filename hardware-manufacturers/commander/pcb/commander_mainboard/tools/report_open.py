#!/usr/bin/env python
"""What is still unconnected, and where.  Run with KiCad's Python:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/report_open.py [board.kicad_pcb]

For every net: the number of separate copper islands its pads fall into (1 = fully connected).  The open
connections (islands - 1) are summed per net class and per board area, and written to build/open_report.txt.
"""
import collections
import os
import sys

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402
from gen_pcb import CFG, OX, OY                 # noqa: E402

NL = chr(10)


def area_of(x, y):
    if x >= CFG["COL_W"]:
        return "strip"
    if y >= CFG["FRONT_Y0"]:
        return "front"
    if y < 8.6:
        return "head"
    if y <= 60.3:
        return "poe"
    return "core"


def islands(board):
    """net code -> list of islands, each a list of pads (pads, tracks, vias and zone fills joined by union-find)."""
    conn = board.GetConnectivity()
    parent = {}

    def find(k):
        while parent.setdefault(k, k) != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a_, b_):
        ra, rb = find(a_), find(b_)
        if ra != rb:
            parent[ra] = rb

    def key(it):
        return it.m_Uuid.AsString()

    by_net = collections.defaultdict(list)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() > 0:
                by_net[p.GetNetCode()].append(p)
                for t in conn.GetConnectedTracks(p):
                    union(key(p), key(t))
    zones = collections.defaultdict(list)
    for z in board.Zones():
        zones[z.GetNetCode()].append(z)
    for t in board.GetTracks():
        for q in conn.GetConnectedTracks(t):
            union(key(t), key(q))
        for q in conn.GetConnectedPads(t):
            union(key(t), key(q))
        if t.GetClass() == "PCB_VIA":
            for z in zones.get(t.GetNetCode(), ()):
                if z.HitTestFilledArea(z.GetLayer(), t.GetPosition(), 0):
                    union(key(t), key(z))
    for code, zs in zones.items():
        for p in by_net.get(code, ()):
            for z in zs:
                if p.IsOnLayer(z.GetLayer()) and z.HitTestFilledArea(z.GetLayer(), p.GetPosition(), 0):
                    union(key(p), key(z))
    out = {}
    for code, pads in by_net.items():
        groups = collections.defaultdict(list)
        for p in pads:
            groups[find(key(p))].append(p)
        out[code] = list(groups.values())
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb")
    board = pcbnew.LoadBoard(path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    isl = islands(board)
    by_cls = collections.Counter()
    by_area = collections.Counter()
    nets = []
    for code, groups in isl.items():
        n_open = len(groups) - 1
        if n_open <= 0:
            continue
        ni = board.FindNet(code)
        name, cname = ni.GetNetname(), ni.GetNetClassName()
        areas = set()
        for g in groups:
            for p in g:
                areas.add(area_of(ToMM(p.GetPosition().x) - OX, ToMM(p.GetPosition().y) - OY))
        a = "+".join(sorted(areas))
        by_cls[cname] += n_open
        by_area[a] += n_open
        nets.append((a, cname, name, n_open, sum(len(g) for g in groups)))
    total = sum(by_cls.values())
    all_conn = sum(sum(len(g) for g in groups) - 1 for groups in isl.values())      # connections a finished board has
    per_layer, nvia = collections.Counter(), 0
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            nvia += 1
        else:
            per_layer[board.GetLayerName(t.GetLayer())] += ToMM(t.GetLength())
    lines = [f"{os.path.basename(path)}: {total} open connections on {len(nets)} nets ({len(isl)} nets in all)",
             f"connections made: {all_conn - total} of {all_conn} ({100.0 * (all_conn - total) / max(1, all_conn):.1f} %)",
             "tracks by layer: " + ", ".join(f"{k} {v:.0f} mm" for k, v in sorted(per_layer.items())) + f"; vias: {nvia}",
             "", "by net class:"]
    lines += [f"  {k:14s} {v}" for k, v in by_cls.most_common()]
    lines += ["", "by area (where the net's pads are):"]
    lines += [f"  {k:28s} {v}" for k, v in by_area.most_common()]
    lines += ["", "nets:"]
    lines += [f"  {a:24s} {c:12s} {n:28s} {o} open / {p} pads" for a, c, n, o, p in sorted(nets)]
    os.makedirs(os.path.join(cpmodel.ROOT, "build"), exist_ok=True)
    open(os.path.join(cpmodel.ROOT, "build", "open_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(lines[:lines.index("nets:")]))


if __name__ == "__main__":
    main()
