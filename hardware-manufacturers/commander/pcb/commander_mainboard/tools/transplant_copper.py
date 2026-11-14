#!/usr/bin/env python
"""Copies the tracks and vias of one board file into another board file with the same placement.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/transplant_copper.py routed.kicad_pcb placed.kicad_pcb

Used to keep the routing of the areas that did not change (bay strip, front, PoE) when only the placement of the
codec core was regenerated.  It refuses to copy a track that ends on a pad which is no longer where it was.
"""
import sys

import pcbnew
from pcbnew import ToMM


def main():
    src_path, dst_path = sys.argv[1], sys.argv[2]
    src, dst = pcbnew.LoadBoard(src_path), pcbnew.LoadBoard(dst_path)
    pos = {}
    for fp in dst.GetFootprints():
        pos[fp.GetReference()] = (fp.GetPosition().x, fp.GetPosition().y, fp.GetOrientationDegrees(), fp.IsFlipped())
    moved = {}
    for fp in src.GetFootprints():
        p = pos.get(fp.GetReference())
        if p is None or p != (fp.GetPosition().x, fp.GetPosition().y, fp.GetOrientationDegrees(), fp.IsFlipped()):
            moved[fp.GetReference()] = fp
    # nets with copper on a pad of a part that moved: their copper is not copied
    bad_nets = set()
    for fp in moved.values():
        for pad in fp.Pads():
            if pad.GetNetCode() <= 0:
                continue
            for t in src.GetTracks():
                if t.GetNetCode() != pad.GetNetCode():
                    continue
                pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
                if any(pad.HitTest(q, 1000) for q in pts) and (t.GetClass() == "PCB_VIA" or pad.IsOnLayer(t.GetLayer())):
                    bad_nets.add(pad.GetNetname())
                    break
    n = 0
    for t in src.GetTracks():
        name = t.GetNetname()
        if name in bad_nets:
            continue
        net = dst.FindNet(name)
        if net is None:
            continue
        if t.GetClass() == "PCB_VIA":
            v = pcbnew.PCB_VIA(dst)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetPosition(t.GetPosition())
            v.SetDrill(t.GetDrillValue())
            try:
                v.SetWidth(pcbnew.F_Cu, t.GetWidth(pcbnew.F_Cu))
            except TypeError:
                v.SetWidth(t.GetWidth())
            v.SetNet(net)
            dst.Add(v)
        else:
            k = pcbnew.PCB_TRACK(dst)
            k.SetStart(t.GetStart())
            k.SetEnd(t.GetEnd())
            k.SetWidth(t.GetWidth())
            k.SetLayer(t.GetLayer())
            k.SetNet(net)
            dst.Add(k)
        n += 1
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu, pcbnew.B_Cu):
        dst.SetLayerType(layer, src.GetLayerType(layer))
    pcbnew.SaveBoard(dst_path, dst)
    print("copied %d tracks and vias; parts at a different position: %d; nets left out because their copper sat on such a part: %d %s"
          % (n, len(moved), len(bad_nets), " ".join(sorted(bad_nets))[:300]))


if __name__ == "__main__":
    main()
