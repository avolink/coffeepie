#!/usr/bin/env python
"""Component heights per face.  Run with KiCad's Python; writes build/heights.txt.

Heights are typical seated heights of the package family (mm), not measured values of the parts that will be
bought: use them to see what sets the clearance on each face, then confirm against the datasheets.
Limits come from the case (CFG in gen_pcb.py): about 3 mm above the board, about 10 mm below it, about 7 mm
below it where the heatsink plate is (the codec core).  A part other than a connector that is too tall for the
top face makes the script exit with code 1; connectors and bottom-face parts that do not fit are listed as
open items, because fixing them is a choice of part, not of placement.
"""
import os
import sys

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                      # noqa: E402
from gen_pcb import CFG, OX, OY     # noqa: E402

NL = chr(10)
TOP_LIMIT, BOTTOM_LIMIT, PLATE_LIMIT = CFG["CLEAR_TOP"], CFG["CLEAR_BOTTOM"], CFG["CLEAR_OVER_PLATE"]
HEIGHT = (
    ("XFMR_Flyback", 12.7), ("XFMR_Bourns_PLN", 8.0), ("PinHeader", 8.5), ("CP_Elec_6.3x7.7", 7.7), ("SMDIP-4", 4.0), ("RJ45", None),
    ("USB_C_Receptacle_JAE", 3.3), ("USB_C_Receptacle_HRO", 3.2), ("CP_EIA-7343-31", 3.1), ("XFMR_LAN", 3.0),
    ("SRP5030", 3.0), ("SWPA4030", 3.0), ("HDMI_Micro", 3.0), ("JST_SH", 2.95), ("C_1210", 2.5), ("D_SMA", 2.4),
    ("SOP-4_4.4x2.6", 2.1), ("XAL4020", 2.1), ("CP_EIA-7343-20", 2.0), ("C_1808", 2.0), ("SW_Push", 1.9), ("SW_SPST_EVQP7", 1.35), ("C_1206", 1.7),
    ("microSD", 1.5), ("SOT-23", 1.45), ("0805", 1.3), ("L_1008_2520", 1.2), ("ACM2012", 1.2), ("CMC_0504", 1.2),
    ("HTSSOP", 1.2), ("PowerDI", 1.15), ("SOD-123", 1.1), ("FCCSP", 1.0), ("BGA", 1.0), ("PowerPAK", 1.0), ("Fuse_1206", 1.0),
    ("QFN", 0.9), ("0603", 0.9), ("Crystal", 0.8), ("SOD-523", 0.7), ("R_2512", 0.6), ("WLCSP", 0.6), ("USON", 0.6),
    ("0402", 0.55), ("0201", 0.33), ("TestPoint", 0.05), ("MountingHole", 0.0),
)


def height(name):
    for key, h in HEIGHT:
        if key in name:
            return h
    return "?"


def main():
    b = pcbnew.LoadBoard(os.environ.get("CP_PCB") or os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb"))
    faces = {"TOP": [], "BOTTOM": []}
    for fp in b.GetFootprints():
        if ToMM(fp.GetPosition().y) - OY > 200:
            continue
        name = str(fp.GetFPID().GetLibItemName())
        faces["BOTTOM" if fp.IsFlipped() else "TOP"].append((height(name), fp.GetReference(), fp.GetValue(), name,
                                                             ToMM(fp.GetPosition().x) - OX, ToMM(fp.GetPosition().y) - OY))
    lines = ["Component heights per face (" + cpmodel.PRJ + ") - typical package heights, mm", ""]
    over = []
    for face, items in faces.items():
        known = [i for i in items if isinstance(i[0], (int, float))]
        unknown = sorted({i[3] for i in items if not isinstance(i[0], (int, float))})
        groups = {}
        for h, ref, val, name, x, y in known:
            groups.setdefault((h, name), []).append(ref)
        lines.append(f"{face} face: {len(items)} parts, tallest {max(i[0] for i in known):.1f} mm")
        for (h, name), refs in sorted(groups.items(), key=lambda kv: -kv[0][0])[:9]:
            lines.append(f"   {h:5.1f}  {name:52s} {len(refs):3d}  {' '.join(sorted(refs)[:10])}")
        if unknown:
            lines.append("   height not in the table: " + ", ".join(unknown))
        lines.append("")
        if face == "TOP":
            over = [(h, ref, name) for h, ref, val, name, x, y in known if h > TOP_LIMIT + 0.001 and ref[0] != "J"]
            conn = [(h, ref, name, y) for h, ref, val, name, x, y in known if h > TOP_LIMIT + 0.001 and ref[0] == "J"]
        else:
            core_y = CFG["CORE_Y0"]
            deep = [(h, ref, name) for h, ref, val, name, x, y in known if h > BOTTOM_LIMIT]
            plate = [(h, ref, name) for h, ref, val, name, x, y in known
                     if cpmodel.VARIANT == "main" and y >= core_y and x <= CFG["COL_W"] and PLATE_LIMIT < h <= BOTTOM_LIMIT]
    lines.append(f"TOP, clearance {TOP_LIMIT} mm - parts that are too tall (connectors apart): {len(over)}  "
                 + " ".join(f"{ref} ({h} mm)" for h, ref, name in sorted(over, reverse=True)))
    lines.append(f"TOP, connectors taller than {TOP_LIMIT} mm (OPEN - a choice of connector or of face): {len(conn)}  "
                 + " ".join(f"{ref} ({h} mm)" for h, ref, name, y in sorted(conn, key=lambda c: c[1])))
    lines.append(f"BOTTOM, clearance {BOTTOM_LIMIT} mm - parts that do not fit (OPEN - needs a lower part): {len(deep)}  "
                 + " ".join(f"{ref} ({h} mm)" for h, ref, name in sorted(deep, reverse=True)))
    lines.append(f"BOTTOM over the heatsink plate, clearance {PLATE_LIMIT} mm - parts that do not fit: {len(plate)}  "
                 + " ".join(f"{ref} ({h} mm)" for h, ref, name in sorted(plate, reverse=True)))
    print(NL.join(lines))
    os.makedirs(os.path.join(cpmodel.ROOT, "build"), exist_ok=True)
    open(os.path.join(cpmodel.ROOT, "build", "heights.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    return 1 if over and cpmodel.VARIANT == "main" else 0


if __name__ == "__main__":
    sys.exit(main())
