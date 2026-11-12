#!/usr/bin/env python
"""Lists footprint collisions on the generated board so the layout engineer knows where the
first placement still needs manual work.  Run with KiCad's Python after tools/gen_pcb.py:

    python.exe tools/report_overlaps.py

Two severities:
  courtyard  the IPC courtyards overlap.  At the density of the Radxa reference (0201 parts on
             0.635 mm rows) the stock KiCad courtyards overlap even for correctly placed
             neighbours, so most of these are benign.
  PAD        copper pads of two parts overlap: a real conflict that must be moved.
Writes build/overlaps.txt.
"""
import json
import os
import sys
from collections import Counter

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel      # noqa: E402

AREA = {"ethernet": "ethernet", "hdmi": "hdmi", "storage": "storage", "poe": "poe",
        "usb3_hub": "usb hubs / bays", "usb2_hub": "usb hubs / bays", "battery": "battery port"}


def bbox(obj):
    b = obj.GetBoundingBox()
    return ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom())


def inter(a, b, eps=0.02):
    return min(a[2], b[2]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[1], b[1]) > eps


def main():
    d = cpmodel.load()
    how = {}
    p = os.path.join(cpmodel.ROOT, "build", "placement.json")
    if os.path.exists(p):
        how = json.load(open(p, encoding="utf-8"))
    b = pcbnew.LoadBoard(os.path.join(cpmodel.ROOT, "commander_mainboard.kicad_pcb"))
    items = []
    for fp in b.GetFootprints():
        layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
        c = fp.GetCourtyard(layer)
        if not c.OutlineCount():
            continue
        bb = c.BBox()
        pads = [(bbox(pd), pd.GetNetname(), pd.GetAttribute() == pcbnew.PAD_ATTRIB_PTH) for pd in fp.Pads() if pd.GetNumber()]
        items.append((fp.GetReference(), fp.IsFlipped(), (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())), pads))
    items.sort(key=lambda t: t[2][0])
    pairs = []
    for i, a in enumerate(items):
        for c in items[i + 1:]:
            if c[2][0] >= a[2][2]:
                break
            if not inter(a[2], c[2]):
                continue
            same_side = a[1] == c[1]
            pad_hit = any(inter(pa[0], pc[0], 0.0) and (same_side or pa[2] or pc[2]) and (pa[1] != pc[1] or not pa[1])
                          for pa in a[3] for pc in c[3])
            if same_side or pad_hit:
                pairs.append((a[0], c[0], "PAD" if pad_hit else "courtyard"))

    def area(r):
        if r not in d.comps:
            return "mounting hole"
        return AREA.get(d.comps[r].sheet, "codec core")

    sev = Counter(s for _, _, s in pairs)
    by_area = Counter((s, " / ".join(sorted({area(r1), area(r2)}))) for r1, r2, s in pairs)
    by_how = Counter()
    for r1, r2, s in pairs:
        if s == "PAD":
            by_how[" + ".join(sorted({how.get(r1, "?"), how.get(r2, "?")}))] += 1
    lines = [f"footprints: {len(items)}   colliding pairs: {len(pairs)}   (pad conflicts: {sev['PAD']}, courtyard only: {sev['courtyard']})", ""]
    lines += [f"  {v:4d}  {k[0]:9s} {k[1]}" for k, v in sorted(by_area.items(), key=lambda kv: (kv[0][0] != 'PAD', -kv[1]))]
    lines += ["", "pad conflicts by how the two parts were positioned:"]
    lines += [f"  {v:4d}  {k}" for k, v in by_how.most_common()]
    lines += ["", "PAD conflicts (move these first):"]
    lines += [f"  {r1:8s} {r2:8s}" for r1, r2, s in pairs if s == "PAD"]
    lines += ["", "courtyard-only overlaps:"]
    lines += [f"  {r1:8s} {r2:8s}" for r1, r2, s in pairs if s != "PAD"]
    with open(os.path.join(cpmodel.ROOT, "build", "overlaps.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:4 + len(by_area) + len(by_how)]))


if __name__ == "__main__":
    main()
