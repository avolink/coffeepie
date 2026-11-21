#!/usr/bin/env python
"""hub_clean_copper.py SRC DST [REF ...] - remove every track / via that touches (or comes within 0.16 mm of) a pad of
another net on the given footprints (default: the hub's bay receptacles J31..J39 and every part within 16 mm of
them), so that moved parts and new footprints do not short against copper left from before; the router redoes it.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/hub_clean_copper.py commander_hub.kicad_pcb build/hub_clean.kicad_pcb
"""
import sys

import pcbnew
from pcbnew import FromMM, ToMM

REFS = ["J%d" % i for i in range(31, 40)]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    refs = set(sys.argv[3:])
    if not refs:
        centres = [b.FindFootprintByReference(r).GetPosition() for r in REFS]
        for f in b.GetFootprints():
            p = f.GetPosition()
            if any(abs(ToMM(p.x - c.x)) < 16.0 and abs(ToMM(p.y - c.y)) < 22.0 for c in centres):
                refs.add(f.GetReference())
    pads = [p for f in b.GetFootprints() if f.GetReference() in refs for p in f.Pads()]
    clr = FromMM(0.16)                 # (the widest clearance class on the hub, PWR_5V, is 0.15)
    kill = []
    layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu]
    for t in b.GetTracks():
        n = t.GetNetCode()
        bbt = t.GetBoundingBox()
        for p in pads:
            if p.GetNetCode() == n and n > 0:
                continue
            bbp = p.GetBoundingBox()
            bbp.Inflate(FromMM(0.6))
            if not bbp.Intersects(bbt):
                continue
            hit = False
            for lay in layers:
                if not (t.IsOnLayer(lay) and p.IsOnLayer(lay)):
                    continue
                if t.GetEffectiveShape(lay).Collide(p.GetEffectiveShape(lay), clr):
                    hit = True
                    break
            if not hit and p.HasHole():          # a drilled pad meets copper on every layer
                hs = p.GetEffectiveHoleShape()
                for lay in layers:
                    if t.IsOnLayer(lay) and t.GetEffectiveShape(lay).Collide(hs, FromMM(0.26)):
                        hit = True
                        break
            if hit:
                kill.append(t)
                break
    for t in kill:
        b.Remove(t)
    pcbnew.SaveBoard(dst, b)
    print("checked %d footprints, %d pads; removed %d tracks / vias touching another net's pad" % (len(refs), len(pads), len(kill)))


if __name__ == "__main__":
    main()
