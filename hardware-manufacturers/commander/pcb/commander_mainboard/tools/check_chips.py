#!/usr/bin/env python
"""Assembly check around the big chips.  Run with KiCad's Python.

For every large IC (BGA / QFN, 20 pads or more) it lists
  * parts on the SAME face whose pads or courtyard overlap the chip      -> cannot be assembled as placed
  * through-hole pads of any part that come up inside the chip's outline  -> would be drilled through its land pattern
and, for the chips that are meant to touch the heatsink plate (bottom face), the neighbours within 2 mm, because
anything taller than the chip there decides the shape of the pedestal on the plate.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/check_chips.py      exit code 1 if a chip is obstructed
"""
import os
import sys

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                      # noqa: E402
from gen_pcb import OX, OY          # noqa: E402

NL = chr(10)
# typical seated heights (mm) by footprint family, for the neighbour list; unknown ones are flagged
HEIGHT = (("0201", 0.33), ("0402", 0.55), ("0603", 0.9), ("0805", 1.3), ("1206", 1.7), ("1008_2520", 1.2), ("2520", 1.2),
          ("SOT-23", 1.2), ("SOD-123", 1.2), ("SOD-523", 0.7), ("D_SMA", 2.4), ("WLCSP", 0.6), ("USON", 0.6), ("Crystal_SMD_3225", 0.8),
          ("Crystal_SMD_3215", 0.9), ("FCCSP", 1.0), ("BGA-200", 1.0), ("LFBGA-153", 1.0), ("QFN", 0.9), ("TestPoint", 0.05),
          ("SRP5030", 3.0), ("SWPA4030", 3.0), ("EIA-7343", 3.1), ("PowerDI", 1.2), ("Fuse_1206", 1.0))


def height(fp):
    name = str(fp.GetFPID().GetLibItemName())
    for key, h in HEIGHT:
        if key in name:
            return h
    return None


def box(bb):
    return (ToMM(bb.GetLeft()) - OX, ToMM(bb.GetTop()) - OY, ToMM(bb.GetRight()) - OX, ToMM(bb.GetBottom()) - OY)


def court(fp):
    c = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    return box(c.BBox() if c.OutlineCount() else fp.GetBoundingBox(False))


def body(fp):
    """Bounding box of the pads: the land pattern itself."""
    xs, ys = [], []
    for p in fp.Pads():
        b = box(p.GetBoundingBox())
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    return (min(xs), min(ys), max(xs), max(ys))


def package(fp):
    """Outline of the package (fabrication layer): for a BGA it is larger than the ball field."""
    layer = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
    b0 = body(fp)
    xs, ys = [b0[0], b0[2]], [b0[1], b0[3]]
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer and g.GetClass() == "PCB_SHAPE":
            bb = box(g.GetBoundingBox())
            xs += [bb[0], bb[2]]
            ys += [bb[1], bb[3]]
    return (min(xs), min(ys), max(xs), max(ys))


def inter(a, b, eps=0.02):
    return a[0] < b[2] - eps and b[0] < a[2] - eps and a[1] < b[3] - eps and b[1] < a[3] - eps


def gap(a, b):
    dx, dy = max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0)
    return (dx * dx + dy * dy) ** 0.5


def main():
    b = pcbnew.LoadBoard(os.environ.get("CP_PCB") or os.path.join(cpmodel.ROOT, cpmodel.PRJ + ".kicad_pcb"))
    fps = [fp for fp in b.GetFootprints() if fp.GetPadCount() and ToMM(fp.GetPosition().y) - OY < 200]
    chips = sorted([fp for fp in fps if fp.GetPadCount() >= 20 and fp.GetReference()[0] == "U"], key=lambda f: f.GetReference())
    lines = ["Assembly check around the big chips (" + cpmodel.PRJ + ")", ""]
    blocked = 0
    for chip in chips:
        ref, side = chip.GetReference(), chip.IsFlipped()
        cc, cb = court(chip), package(chip)
        pad_hits, court_hits, drill_hits, near = [], [], [], []
        for fp in fps:
            if fp is chip:
                continue
            r = fp.GetReference()
            for p in fp.Pads():
                if p.HasHole() and inter(box(p.GetBoundingBox()), cb):
                    drill_hits.append(f"{r}.{p.GetNumber()}")
            if fp.IsFlipped() != side:
                continue
            if inter(body(fp), cb):
                pad_hits.append(r)
            elif inter(court(fp), cc):
                court_hits.append(r)
            elif gap(body(fp), cb) < 2.0:
                h = height(fp)
                near.append((r, h, str(fp.GetFPID().GetLibItemName())))
        face = "BOTTOM (heatsink side)" if side else "top"
        lines.append(f"{ref} {chip.GetValue()}  [{face}]  package {cb[2] - cb[0]:.1f} x {cb[3] - cb[1]:.1f} mm at x {cb[0]:.1f}..{cb[2]:.1f}, y {cb[1]:.1f}..{cb[3]:.1f}")
        lines.append(f"    parts UNDER / ON the package (same face): {len(pad_hits)}  {' '.join(sorted(pad_hits))}")
        lines.append(f"    through-hole pads inside its outline: {len(drill_hits)}  {' '.join(sorted(drill_hits))}")
        lines.append(f"    courtyard-only neighbours (touching, same face): {len(court_hits)}  {' '.join(sorted(court_hits)[:30])}")
        if side:
            hchip = height(chip) or 1.0
            tall = sorted((r, h, n) for r, h, n in near if h is None or h > hchip)
            lines.append(f"    neighbours within 2 mm: {len(near)}; taller than the chip ({hchip} mm) or of unknown height: "
                         + (", ".join(f"{r} ({'?' if h is None else h} mm, {n})" for r, h, n in tall) or "none"))
        blocked += len(pad_hits) + len(drill_hits)
        lines.append("")
    lines.append(f"chips checked: {len(chips)}   obstructions (parts under a package + drills through one): {blocked}")
    print(NL.join(lines))
    os.makedirs(os.path.join(cpmodel.ROOT, "build"), exist_ok=True)
    open(os.path.join(cpmodel.ROOT, "build", "chip_clearance.txt"), "w", encoding="utf-8").write(NL.join(lines) + NL)
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
