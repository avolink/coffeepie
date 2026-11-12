#!/usr/bin/env python
"""Three-way consistency check.  Run with KiCad's Python (needs pcbnew):

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/check_consistency.py build/netlist.net

Compares, pad by pad:
    A  the design model            (src/netlist/*.net)
    B  the generated schematic     (netlist exported by kicad-cli, passed as argument)
    C  the generated board         (commander_mainboard.kicad_pcb)
and, separately, the RK3566 footprint against the pad positions of the Radxa ZERO 3E
V1.2 placement drawing.  Exit status 1 if anything differs.
"""
import json
import os
import re
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                          # noqa: E402
from gen_footprints import rk3566_xy    # noqa: E402

ROOT = cpmodel.ROOT


def model_pads(d):
    out = {}
    for c in d.comps.values():
        for pin, net in c.pins.items():
            for pad in cpmodel.pads_for(c, pin):
                out[(c.ref, pad)] = net
    return out


def schematic_pads(path):
    txt = open(path, encoding="utf-8").read()
    out = {}
    i = txt.find("(nets")
    for m in re.finditer(r'\(net\s+\(code\s+"?\d+"?\)\s+\(name\s+"([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', txt[i:], flags=re.S):
        name = m.group(1)
        for n in re.finditer(r'\(node\s+\(ref\s+"([^"]+)"\)\s+\(pin\s+"([^"]+)"\)', m.group(2)):
            out[(n.group(1), n.group(2))] = name
    return out


def board_pads():
    b = pcbnew.LoadBoard(os.path.join(ROOT, "commander_mainboard.kicad_pcb"))
    out = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNumber():
                out.setdefault((fp.GetReference(), p.GetNumber()), p.GetNetname() or None)
    return out


def diff(name_a, a, name_b, b, limit=12):
    bad = 0
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k, "<absent>"), b.get(k, "<absent>")
        if va != vb:
            if bad < limit:
                print(f"    {k[0]}.{k[1]}: {name_a}={va}  {name_b}={vb}")
            bad += 1
    return bad


def main():
    d = cpmodel.load()
    A = model_pads(d)
    C = board_pads()
    refs = set(d.comps)
    C = {k: v for k, v in C.items() if k[0] in refs}
    total = 0

    # board pads that are mechanical (shield / mounting) and carry no schematic pin are ignored
    Cx = {k: v for k, v in C.items() if k in A or v}
    n = diff("model", A, "board", Cx)
    print(f"model vs board      : {len(A)} model pads, {len(Cx)} board pads, {n} differences")
    total += n

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        B = schematic_pads(sys.argv[1])
        An = {k: v for k, v in A.items() if v is not None}
        # KiCad names unconnected pins 'unconnected-(...)': treat as no-connect
        Bn = {k: v for k, v in B.items() if not v.startswith("unconnected-")}
        n = diff("model", An, "schematic", Bn)
        print(f"model vs schematic  : {len(An)} connected model pads, {len(Bn)} connected schematic pins, {n} differences")
        total += n
    else:
        print("model vs schematic  : skipped (no netlist file given)")

    # RK3566 footprint vs Radxa pad drawing
    ref = json.load(open(os.path.join(ROOT, "src", "reference", "radxa_zero3e_placement.json")))
    dots = [(p[0], p[1]) for p in ref["top"]["pads"] if len(p) == 3 and abs(p[2] - 0.356) < 0.004]
    cx, cy = 28.194, 12.7
    hit = 0
    for ball in d.comps["U1"].pins:
        x, y = rk3566_xy(ball)
        px, py = cx - y, cy - x                      # package frame -> Radxa board frame
        if any(abs(px - a) < 0.03 and abs(py - b) < 0.03 for a, b in dots):
            hit += 1
    print(f"RK3566 ball map     : {hit}/{len(d.comps['U1'].pins)} balls coincide with the {len(dots)} pads of the Radxa drawing")
    if hit != len(dots) or hit != len(d.comps["U1"].pins):
        total += 1

    print("CONSISTENT" if total == 0 else f"INCONSISTENT ({total})")
    raise SystemExit(0 if total == 0 else 1)


if __name__ == "__main__":
    main()
