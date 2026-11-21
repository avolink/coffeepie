#!/usr/bin/env python
"""fw_module_pads.py - the Framework input-module contact pads for our own tray modules (numpad, touchpad), derived
from the tray carrier's pogo pins so that pin n meets pad n:

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/fw_module_pads.py

Reads commander_tray.kicad_pcb (J2: the pogo connector of bay 1), takes the eight pins' positions relative to their
centroid, and writes lib/commander.pretty/FW_InputModule_Pads_2x4.kicad_mod into commander_numpad and
commander_touchpad: eight 1.5 mm round SMD pads on B.Cu (gold, no paste), origin at the block centre, the footprint
itself on the front (not flipped), so its local axes are the board's.  The tray strip and the modules map board
(x, y) to the chassis the same way (x -> +X, y -> -Y), so the offsets carry over unchanged.

Framework's B-size reference (FW_B_SIZE_DESIGN_REF, CC BY 4.0, github.com/FrameworkComputer/InputModules): one 2 x 4
block per module, 1.5 mm pads, 2.0 mm pitch along the module's width, 3.5 mm between the rows; centre 7.0 mm from
the contact edge and 16.96 mm from the module's left edge seen from the front.  Pinout (system side = the tray):
1, 7 GND - 2 VCC_5V - 3 USB D- - 4 BOARD_ID - 5 USB D+ - 6 SLEEP# - 8 VCC_3V3.
Also prints how far the pins' centroid is from the J2 / J3 courtyard centres used in small_board.py.
"""
import os
import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.normpath(os.path.join(HERE, "..", ".."))
b = pcbnew.LoadBoard(os.path.join(PCB, "commander_tray", "commander_tray.kicad_pcb"))
for ref in ("J2", "J3"):
    f = b.FindFootprintByReference(ref)
    pads = [(p.GetNumber(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in f.Pads()
            if p.GetNumber() in ("1", "2", "3", "4", "5", "6", "7", "8")]          # (not the unnumbered locating pegs)
    cx = sum(x for _, x, _ in pads) / len(pads)
    cy = sum(y for _, _, y in pads) / len(pads)
    cc = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    ccx, ccy = ToMM(cc.Centre().x), ToMM(cc.Centre().y)
    print("%s: pin centroid - courtyard centre = (%.3f, %.3f) mm" % (ref, cx - ccx, cy - ccy))
    if ref == "J2":
        rel = sorted((n, round(x - cx, 3), round(y - cy, 3)) for n, x, y in pads)
for n, x, y in rel:
    print("  pad %s at (%+.3f, %+.3f)" % (n, x, y))

lines = ['(footprint "FW_InputModule_Pads_2x4"', '  (version 20240108)', '  (generator "fw_module_pads.py")',
         '  (layer "F.Cu")',
         '  (descr "Framework Laptop 16 input-module contacts, module side: 2 x 4 gold pads, 1.5 mm, on the underside '
         '(B.Cu); positions taken from the Commander tray carrier\'s pogo pins (tools/fw_module_pads.py). Framework B-size '
         'reference, CC BY 4.0")',
         '  (tags "Framework input module pogo pads")',
         '  (attr smd exclude_from_pos_files exclude_from_bom)',
         '  (property "Reference" "REF**" (at 0 -4.6 0) (layer "B.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))',
         '  (property "Value" "FW_PADS" (at 0 4.6 0) (layer "B.Fab") (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))']
xs = [x for _, x, _ in rel]
ys = [y for _, _, y in rel]
x0, x1, y0, y1 = min(xs) - 1.25, max(xs) + 1.25, min(ys) - 1.25, max(ys) + 1.25
lines.append('  (fp_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.05) (type default)) (fill none) (layer "B.CrtYd"))' % (x0, y0, x1, y1))
lines.append('  (fp_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.1) (type default)) (fill none) (layer "B.Fab"))' % (x0 + 0.25, y0 + 0.25, x1 - 0.25, y1 - 0.25))
for n, x, y in rel:
    lines.append('  (pad "%s" smd circle (at %.3f %.3f) (size 1.5 1.5) (layers "B.Cu" "B.Mask"))' % (n, x, y))
lines.append(')')
for prj in ("commander_numpad", "commander_touchpad"):
    d = os.path.join(PCB, prj, "lib", "commander.pretty")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "FW_InputModule_Pads_2x4.kicad_mod"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("written", os.path.join(prj, "lib", "commander.pretty", "FW_InputModule_Pads_2x4.kicad_mod"))
