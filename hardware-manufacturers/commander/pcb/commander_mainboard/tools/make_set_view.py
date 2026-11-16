#!/usr/bin/env python
"""The three boards in one KiCad file, as they sit in the case:  ../commander_set/commander_set.kicad_pcb

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_set_view.py

The mainboard (the codec column with the M.2 socket J41) is the base.  The hub board (../commander_hub) keeps the
mainboard's coordinates, so it goes in where it is: its card edge in J41.  The keyboard is put to the right of the
column and 1 mm below the hub board, its right edge where the user's layout sketch has it (346.98 mm overall).  The
sketch's height (170.05 mm) is not kept: the keyboard would lie 18 mm over the hub board.  Hub references and nets
get the prefix "HUB_", keyboard ones "KB_", so that nothing is shared between boards (no ratsnest between them).

FOR LOOKING AT AND FOR FIT CHECKS ONLY.  The boards are made separately, each from its own project and Gerber
package (commander/fabrication/gerber/): mainboard 6 layers 1.2 mm, hub 6 layers 0.8 mm (M.2 card), keyboard
2 layers 1.6 mm.  Three thicknesses cannot share a panel: ordered together they are three designs in one order.
"""
import os
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, "..", ".."))
MAIN = os.path.join(PCB, "commander_mainboard", "commander_mainboard.kicad_pcb")
HUB = os.path.join(PCB, "commander_hub", "commander_hub.kicad_pcb")
KBD =os.environ.get("CP_KBD_PCB") or os.path.join(PCB, "commander_keyboard", "commander_keyboard.kicad_pcb")
OUT_DIR = os.path.join(PCB, "commander_set")
OUT = os.path.join(OUT_DIR, "commander_set.kicad_pcb")
OVERALL = (346.98, 170.05)          # mm, the user's layout sketch (only the width is kept: see above)
GAP = 1.0                           # mm between the hub board and the keyboard


def outline_bbox(board):
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    bb = ps.BBox()
    return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())


def copy(item):
    d = item.Duplicate()
    return d.Cast() if hasattr(d, "Cast") else d


def merge(mb, src, prefix, off):
    """Copy every part, track, zone and drawing of board `src` into `mb`, moved by `off`, references and nets
    prefixed so that they stay apart from the mainboard's."""
    nets = {}
    for name, ni in src.GetNetsByName().items():
        name = str(name)
        if name:
            n2 = pcbnew.NETINFO_ITEM(mb, prefix + name)
            mb.Add(n2)
            nets[name] = n2

    def net_of(item):
        return nets.get(item.GetNetname())
    nfp = ntr = nz = nd = 0
    for fp in src.GetFootprints():
        f2 = pcbnew.FOOTPRINT(fp)
        f2.SetReference(prefix + fp.GetReference())
        mb.Add(f2)
        for p in f2.Pads():
            n = net_of(p)
            if n is not None:
                p.SetNet(n)
        f2.Move(off)
        nfp += 1
    for t in src.GetTracks():
        t2 = copy(t)
        mb.Add(t2)
        n = net_of(t)
        if n is not None:
            t2.SetNet(n)
        t2.Move(off)
        ntr += 1
    for z in src.Zones():
        z2 = pcbnew.ZONE(z)
        mb.Add(z2)
        n = net_of(z)
        if n is not None:
            z2.SetNet(n)
        z2.Move(off)
        nz += 1
    for d in src.GetDrawings():
        d2 = copy(d)
        mb.Add(d2)
        d2.Move(off)
        nd += 1
    return nfp, ntr, nz, nd


def main():
    mb = pcbnew.LoadBoard(MAIN)
    hb = pcbnew.LoadBoard(HUB)
    kb = pcbnew.LoadBoard(KBD)
    mx0, my0, mx1, my1 = outline_bbox(mb)
    hx0, hy0, hx1, hy1 = outline_bbox(hb)
    kx0, ky0, kx1, ky1 = outline_bbox(kb)
    # the hub board is drawn in the mainboard's coordinates: it goes in unmoved, card edge in J41
    n = merge(mb, hb, "HUB_", VECTOR2I(0, 0))
    print("hub board: %d parts, %d tracks / vias, %d zones, %d drawings" % n)
    # keyboard: right edge as in the sketch; top edge 1 mm below the hub board (in the sketch the keyboard is 18 mm
    # higher, which would put it on top of the hub board: that is 21.7 mm deep)
    dx, dy = mx0 + OVERALL[0] - kx1, hy1 + GAP - ky0
    off = VECTOR2I(FromMM(dx), FromMM(dy))
    nfp, ntr, nz, nd = merge(mb, kb, "KB_", off)
    note = pcbnew.PCB_TEXT(mb)
    note.SetText("VIEW / FIT CHECK ONLY - each board is made from its own project:\n"
                 "pcb/commander_mainboard (6 layers, 1.2 mm), pcb/commander_hub (6 layers, 0.8 mm)\n"
                 "and pcb/commander_keyboard (2 layers, 1.6 mm)")
    note.SetLayer(pcbnew.Cmts_User)
    note.SetTextSize(VECTOR2I(FromMM(3), FromMM(3)))
    note.SetTextThickness(FromMM(0.4))
    note.SetPosition(VECTOR2I(FromMM(mx0 + 150), FromMM(my0 - 14)))
    mb.Add(note)

    os.makedirs(OUT_DIR, exist_ok=True)
    pcbnew.SaveBoard(OUT, mb, True)
    shutil.copyfile(os.path.splitext(MAIN)[0] + ".kicad_pro", os.path.join(OUT_DIR, "commander_set.kicad_pro"))
    for lib in ("fp-lib-table", "sym-lib-table"):
        src = os.path.join(PCB, "commander_mainboard", lib)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(OUT_DIR, lib))
    if not os.path.exists(os.path.join(OUT_DIR, "lib")):
        shutil.copytree(os.path.join(PCB, "commander_mainboard", "lib"), os.path.join(OUT_DIR, "lib"))
        shutil.copy(os.path.join(PCB, "commander_keyboard", "lib", "commander.pretty", "KeySwitch_Keychron_LP_Optical.kicad_mod"),
                    os.path.join(OUT_DIR, "lib", "commander.pretty"))
        shutil.copy(os.path.join(PCB, "commander_keyboard", "lib", "commander.pretty", "ISP_2x3_P2.54mm_Pads.kicad_mod"),
                    os.path.join(OUT_DIR, "lib", "commander.pretty"))
    print("keyboard placed at offset (%.2f, %.2f) mm: %d parts, %d tracks / vias, %d zones, %d drawings" % (dx, dy, nfp, ntr, nz, nd))
    x0, y0 = min(mx0, hx0, kx0 + dx), min(my0, hy0, ky0 + dy)
    print("together: %.2f x %.2f mm  ->  %s" % (max(mx1, hx1, kx1 + dx) - x0, max(my1, hy1, ky1 + dy) - y0, OUT))


if __name__ == "__main__":
    sys.exit(main())
