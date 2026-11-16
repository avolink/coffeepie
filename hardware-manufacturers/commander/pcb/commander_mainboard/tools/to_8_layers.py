#!/usr/bin/env python
"""to_8_layers.py SRC DST - the mainboard from 6 to 8 copper layers, nothing of the existing copper moved.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/to_8_layers.py commander_mainboard.kicad_pcb build/main8.kicad_pcb

KiCad numbers inner layers from the top, so the two new layers come in between In4 and B.Cu:

    6 layers                          8 layers
    F.Cu   signal                     F.Cu   signal
    In1    GND plane                  In1    GND plane
    In2    signal                     In2    signal       memory: command / address / clock
    In3    supply pours               In3    supply pours memory: data byte 1 (the pours open inside the memory area)
    In4    GND plane                  In4    GND plane
    B.Cu   signal                     In5    signal  NEW  memory: data byte 0, between two ground planes
                                      In6    GND plane NEW (a copy of In4's ground pours)
                                      B.Cu   signal       now 1 dielectric from a ground plane (In6), not 1 + In5

Every keep-out that covered all the inner layers (the PoE isolation barrier among them) is widened to In5 / In6.
Board thickness stays 1.2 mm.
"""
import sys

import pcbnew
from pcbnew import FromMM

NEW = (pcbnew.In5_Cu, pcbnew.In6_Cu)
OLD_INNER = (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.In4_Cu)


def widen(z):
    """A keep-out on every inner layer gets In5 and In6; one on the In4 ground plane (the Ethernet line areas' 'no
    ground pour' areas sit on In1 and In4) gets the new ground plane In6."""
    ls = z.GetLayerSet()
    add = NEW if all(ls.Contains(l) for l in OLD_INNER) else (pcbnew.In6_Cu,) if ls.Contains(pcbnew.In4_Cu) else ()
    for l in add:
        ls.AddLayer(l)
    if add:
        z.SetLayerSet(ls)
    return 1 if add else 0


def main():
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    ds = b.GetDesignSettings()
    if b.GetCopperLayerCount() != 6:
        raise SystemExit("expected a 6-layer board, found %d" % b.GetCopperLayerCount())
    b.SetCopperLayerCount(8)
    en = b.GetEnabledLayers()
    for l in NEW:
        en.AddLayer(l)
    b.SetEnabledLayers(en)
    b.SetLayerType(pcbnew.In5_Cu, pcbnew.LT_SIGNAL)
    b.SetLayerType(pcbnew.In6_Cu, pcbnew.LT_POWER)
    ds.SetBoardThickness(FromMM(1.2))           # (the file has no stackup block: KiCad derives it from the layers)

    widened = copied = 0
    for z in list(b.Zones()):
        if z.GetIsRuleArea():
            widened += widen(z)
        elif z.GetNetname() == "GND" and z.IsOnLayer(pcbnew.In4_Cu) and z.GetLayerSet().CuStack().size() == 1:
            z2 = pcbnew.ZONE(z)
            z2.SetLayer(pcbnew.In6_Cu)
            z2.SetZoneName((z.GetZoneName() or "GND") + " (In6)")
            b.Add(z2)
            copied += 1
    for f in b.GetFootprints():
        for z in f.Zones():
            if z.GetIsRuleArea():
                widened += widen(z)
    for d in b.GetDrawings():                   # the board's own title note
        if d.GetClass() == "PCB_TEXT":
            d = d.Cast()
            if "6-layer" in d.GetText():
                d.SetText(d.GetText().replace("6-layer", "8-layer"))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(dst, b)
    print("8 layers: %d GND pours copied In4 -> In6, %d keep-outs widened to In5 / In6  ->  %s" % (copied, widened, dst))


if __name__ == "__main__":
    main()
