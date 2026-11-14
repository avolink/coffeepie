#!/usr/bin/env python
"""EXPERIMENT: can the scripted router connect the RK3566 to the LPDDR4?  Run with KiCad's Python.

It works on a COPY of the board (build/ddr_try.kicad_pcb) and never touches the project's board file.
Rules used: 0.09 mm tracks and clearance, 0.25 / 0.15 mm vias that may sit in a BGA pad, three signal layers
(B.Cu where the two chips are, In2.Cu, F.Cu), 0.025 mm grid.  It reports how many of the memory nets were
connected and how long each one came out - which is what decides whether length matching is worth attempting.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/route_ddr.py [passes]
"""
import collections
import json
import os
import shutil
import sys

os.environ.setdefault("CP_GRID", "0.025")
import pcbnew                                   # noqa: E402
from pcbnew import ToMM                         # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402
import route                                    # noqa: E402

NL = chr(10)
ROOT = cpmodel.ROOT
SRC = os.path.join(ROOT, cpmodel.PRJ + ".kicad_pcb")
DST = os.path.join(ROOT, "build", "ddr_try.kicad_pcb")
REGION = ("ddr", 4.5, 60.8, 27.0, 90.6)         # the two packages and the gap between them (design mm)


def main():
    passes = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    shutil.copyfile(SRC, DST)
    # the copy gets its own project file with the finer via allowed, so its DRC judges it by the rules used
    pro = json.load(open(os.path.join(ROOT, cpmodel.PRJ + ".kicad_pro"), encoding="utf-8"))
    rules = pro["board"]["design_settings"]["rules"]
    rules.update(min_via_diameter=0.25, min_through_hole_diameter=0.15, min_via_annular_width=0.05, min_hole_to_hole=0.25)
    json.dump(pro, open(DST.replace(".kicad_pcb", ".kicad_pro"), "w", encoding="utf-8"), indent=2)

    board = pcbnew.LoadBoard(DST)
    route.REGIONS[:] = [REGION]
    route.SKIP_CLASSES.discard("DDR")
    r = route.Router(board)
    r.only, r.bga = "LPDDR4_*", True
    nets_done, nets_part, fan_ok, fan_bad = r.run(passes=passes)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(DST, board)

    # what was achieved, net by net
    length = collections.Counter()
    vias = collections.Counter()
    layers = collections.defaultdict(set)
    for t in board.GetTracks():
        n = t.GetNetname()
        if not n.startswith("LPDDR4_"):
            continue
        if t.GetClass() == "PCB_VIA":
            vias[n] += 1
        else:
            length[n] += ToMM(t.GetLength())
            layers[n].add(board.GetLayerName(t.GetLayer()))
    done = {name for _, name, okp, total in nets_done}
    part = {name for _, name, okp, total in nets_part}
    lines = ["DDR routing experiment (" + cpmodel.PRJ + ") - on a copy: build/ddr_try.kicad_pcb", "",
             f"grid {route.G} mm, track / clearance 0.09 mm, via 0.25 / 0.15 mm (in-pad allowed), passes {passes}",
             f"memory nets connected end to end: {len(done)} of {len(done) + len(part)}",
             f"not connected: {len(part)}  {' '.join(sorted(part))}", ""]
    if done:
        ls = sorted((length[n], n) for n in done)
        lines += [f"routed length of the connected nets: shortest {ls[0][0]:.2f} mm ({ls[0][1]}), longest {ls[-1][0]:.2f} mm ({ls[-1][1]})",
                  f"vias per connected net: {min(vias[n] for n in done)} to {max(vias[n] for n in done)}", ""]
        groups = collections.defaultdict(list)
        for n in sorted(done | part):
            base = n.replace("LPDDR4_", "")
            ch = base.rsplit("_", 1)[-1] if base.rsplit("_", 1)[-1] in ("A", "B") else "-"
            kind = "".join(c for c in base.split("_")[0] if not c.isdigit())
            lane = ""
            if kind in ("DQ", "DM", "DQSP", "DQSN"):
                num = int("".join(c for c in base.split("_")[0] if c.isdigit()) or 0)
                lane = str(num // 8 if kind == "DQ" else num)
                kind = "data"
            elif kind in ("A", "CLKP", "CLKN", "CSN", "CKE", "ODT"):
                kind = "command"
            groups[(ch, kind, lane)].append(n)
        lines.append("by matching group (channel, kind, byte lane): connected / total, length spread of the connected ones")
        for key, ns in sorted(groups.items()):
            ok = [n for n in ns if n in done]
            spread = (f"{min(length[n] for n in ok):6.2f} .. {max(length[n] for n in ok):6.2f} mm  (spread {max(length[n] for n in ok) - min(length[n] for n in ok):.2f})") if ok else "-"
            lines.append(f"  channel {key[0]}  {key[1]:8s} lane {key[2] or '-'}:  {len(ok):2d} / {len(ns):2d}   {spread}")
        lines.append("")
        lines += [f"  {n:22s} {length[n]:7.2f} mm  {vias[n]} via  {' '.join(sorted(layers[n]))}" for l_, n in ls]
    lines += [""] + ["  " + f for f in r.failed[:80]]
    open(os.path.join(ROOT, "build", "ddr_report.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    print(NL.join(lines[:22]))


if __name__ == "__main__":
    main()
