#!/usr/bin/env python3
"""Preliminary bill of materials from the design model -> fabrication/bom/.

Grouped by (value, footprint, description).  Column 'origin' tells the auditor where a
line comes from: 'Radxa ZERO 3E V1.2' for parts carried over from the reference schematic,
'Commander' for the circuitry added on this board.
Package sizes in the CSV are the ones used on the board (carried-over chip passives take
the size found in Radxa's placement drawing), read back from the generated PCB when present.
"""
import csv
import os
import re
from collections import OrderedDict

import cpmodel

OUTDIR = os.path.normpath(os.path.join(cpmodel.ROOT, "..", "..", "fabrication", "bom"))
NEW_SHEETS = ("poe", "usb3_hub", "usb2_hub")
NEW_REFS = re.compile(r"^(U20|U21|J21|SW\d|TP[2-6]|R40\d|C40\d|D30)$")


def board_footprints():
    """ref -> footprint id as placed on the board (plain text scan, no pcbnew needed)."""
    path = os.path.join(cpmodel.ROOT, "commander_mainboard.kicad_pcb")
    out = {}
    if not os.path.exists(path):
        return out
    txt = open(path, encoding="utf-8").read()
    for m in re.finditer(r'\(footprint "([^"]+)"(.*?)\(property "Reference" "([^"]+)"', txt, flags=re.S):
        out[m.group(3)] = m.group(1)
    return out


def natural(ref):
    m = re.match(r"^(\d?)([A-Z]+)(\d+)$", ref)
    return (m.group(2), int(m.group(3)), m.group(1)) if m else (ref, 0, "")


def main():
    d = cpmodel.load()
    onboard = board_footprints()
    groups = OrderedDict()
    for c in d.comps.values():
        if c.kind == "TP":
            continue
        fp = onboard.get(c.ref, c.fp)
        origin = "Commander" if (c.sheet in NEW_SHEETS or NEW_REFS.match(c.ref)) else "Radxa ZERO 3E V1.2"
        value = c.value if not c.dnp else "DNP"
        key = (value, fp, c.desc if c.kind in ("ic", "two") else "", c.dnp, origin)
        groups.setdefault(key, []).append(c.ref)
    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "commander_mainboard_revA0_bom.csv")
    rows = []
    for (value, fp, desc, dnp, origin), refs in groups.items():
        refs.sort(key=natural)
        rows.append([len(refs), value, fp.split(":", 1)[-1], desc, "DNP" if dnp else "", origin, " ".join(refs)])
    rows.sort(key=lambda r: (r[4] == "DNP", natural(r[6].split()[0])))
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["qty", "value", "footprint", "description", "populate", "origin", "references"])
        w.writerows(rows)
    fitted = sum(r[0] for r in rows if r[4] != "DNP")
    dnp = sum(r[0] for r in rows if r[4] == "DNP")
    print(f"  fabrication/bom/{os.path.basename(out)}  {len(rows)} lines, {fitted} fitted + {dnp} DNP parts")


if __name__ == "__main__":
    main()
