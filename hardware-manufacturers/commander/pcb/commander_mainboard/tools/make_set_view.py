#!/usr/bin/env python
"""Both boards in one KiCad file, side by side as they sit in the case:  ../commander_set/commander_set.kicad_pcb

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_set_view.py

The keyboard is put to the right of the codec column and below the hub strip, its right edge where the user's
layout sketch has it (346.98 mm overall).  The sketch's height (170.05 mm) is not kept: with the hub strip as deep as
it is now, the keyboard would lie 18 mm over it.  Its references and nets get the prefix "KB_" so that nothing is
shared with the mainboard (no ratsnest between the boards).

FOR LOOKING AT AND FOR FIT CHECKS ONLY.  The two boards are made separately - the mainboard has 6 copper layers,
the keyboard 2 - each from its own project and its own Gerber package (commander/fabrication/gerber/).  Ordered
together, they are two designs in one order; a fabricator cannot make them as one panel from this file.
"""
import os
import shutil
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, "..", ".."))
MAIN = os.path.join(PCB, "commander_mainboard", "commander_mainboard.kicad_pcb")
KBD = os.environ.get("CP_KBD_PCB") or os.path.join(PCB, "commander_keyboard", "commander_keyboard.kicad_pcb")
OUT_DIR = os.path.join(PCB, "commander_set")
OUT = os.path.join(OUT_DIR, "commander_set.kicad_pcb")
OVERALL = (346.98, 170.05)          # mm, the user's layout sketch (only the width is kept: see above)
GAP = 1.0                           # mm between the hub strip and the keyboard


def outline_bbox(board):
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    bb = ps.BBox()
    return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())


def copy(item):
    d = item.Duplicate()
    return d.Cast() if hasattr(d, "Cast") else d


def main():
    mb = pcbnew.LoadBoard(MAIN)
    kb = pcbnew.LoadBoard(KBD)
    mx0, my0, mx1, my1 = outline_bbox(mb)
    kx0, ky0, kx1, ky1 = outline_bbox(kb)
    # right edge as in the sketch; top edge 1 mm below the hub strip (in the sketch the keyboard is 18 mm higher, which
    # would put it on top of the strip: the strip is 21.7 mm deep now)
    ps = pcbnew.SHAPE_POLY_SET()
    mb.GetBoardPolygonOutlines(ps, True)
    xs = mx0 + 200.0
    ys = []
    for k in range(ps.OutlineCount()):
        o = ps.Outline(k)
        pts = [(ToMM(o.CPoint(i).x), ToMM(o.CPoint(i).y)) for i in range(o.PointCount())]
        for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
            if (ax > xs) != (bx > xs):
                ys.append(ay + (xs - ax) * (by - ay) / (bx - ax))
    strip_bottom = max(ys)
    dx, dy = mx0 + OVERALL[0] - kx1, strip_bottom + GAP - ky0
    off = VECTOR2I(FromMM(dx), FromMM(dy))

    nets = {}
    for name, ni in kb.GetNetsByName().items():
        name = str(name)
        if name:
            n2 = pcbnew.NETINFO_ITEM(mb, "KB_" + name)
            mb.Add(n2)
            nets[name] = n2

    def net_of(item):
        return nets.get(item.GetNetname())
    nfp = ntr = nz = nd = 0
    for fp in kb.GetFootprints():
        f2 = pcbnew.FOOTPRINT(fp)
        f2.SetReference("KB_" + fp.GetReference())
        mb.Add(f2)
        for p in f2.Pads():
            n = net_of(p)
            if n is not None:
                p.SetNet(n)
        f2.Move(off)
        nfp += 1
    for t in kb.GetTracks():
        t2 = copy(t)
        mb.Add(t2)
        n = net_of(t)
        if n is not None:
            t2.SetNet(n)
        t2.Move(off)
        ntr += 1
    for z in kb.Zones():
        z2 = pcbnew.ZONE(z)
        mb.Add(z2)
        n = net_of(z)
        if n is not None:
            z2.SetNet(n)
        z2.Move(off)
        nz += 1
    for d in kb.GetDrawings():
        d2 = copy(d)
        mb.Add(d2)
        d2.Move(off)
        nd += 1
    note = pcbnew.PCB_TEXT(mb)
    note.SetText("VIEW / FIT CHECK ONLY - each board is made from its own project:\n"
                 "pcb/commander_mainboard (6 layers) and pcb/commander_keyboard (2 layers)")
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
    print("together: %.2f x %.2f mm  ->  %s" % (max(mx1, kx1 + dx) - mx0, max(my1, ky1 + dy) - my0, OUT))


if __name__ == "__main__":
    sys.exit(main())
