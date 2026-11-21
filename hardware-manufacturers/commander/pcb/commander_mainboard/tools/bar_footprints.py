"""bar_footprints.py - the custom footprints of the front battery bar's two boards (commander_bar_bms: the joint pads;
commander_bar_contacts: the castellated edge and the cell pads), written into each project's lib/commander.pretty."""
import os
import sys

PCB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
XS = [5.17, 11.67, 18.16, 24.66, 31.16, 37.66, 44.16, 50.66, 57.16, 63.66, 68.5]     # joint x on both boards (board mm)
XC = (XS[0] + XS[-1]) / 2


def rect(x0, y0, x1, y1, layer, w):
    return '  (fp_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width %s) (type default)) (fill none) (layer "%s"))\n' % (x0, y0, x1, y1, w, layer)


def head(name, descr, tags, attr):
    return ('(footprint "%s" (version 20221018) (generator pcbnew)\n  (layer "F.Cu")\n  (descr "%s")\n  (tags "%s")\n  (attr %s)\n'
            '  (fp_text reference "REF**" (at 0 -2.6) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            '  (fp_text value "%s" (at 0 2.6) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))\n') % (name, descr, tags, attr, name)


# 1. on the BMS board: 11 SMD pads; the contact board (1.0 mm) stands on the strip y -1.6 .. -0.6 of this footprint,
#    the pads' fillets climb its front face
s = head("BarContacts_Joint_11", "solder joint to the front battery bar's cell-contact board: 11 pads 1.6 x 2.2 mm under its castellated edge; the board stands on y -1.6..-0.6",
         "joint castellated", "smd exclude_from_bom")
for i, x in enumerate(XS):
    s += '  (pad "%d" smd roundrect (at %.3f 0) (size 1.6 2.2) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.15))\n' % (i + 1, x - XC)
half = XC - XS[0] + 0.8 + 0.25
s += rect(-half, -1.6, half, 1.6, "F.CrtYd", 0.05)
s += rect(-(XC - 0.0), -1.6, XS[-1] - XC + 7.3, -0.6, "F.Fab", 0.1)            # the contact board (75.8 mm, past this board's right edge)
s += ")\n"
open(PCB + "/commander_bar_bms/lib/commander.pretty/BarContacts_Joint_11.kicad_mod", "w", newline="\n").write(s)

# 2. on the contact board: 11 castellated half-holes on the board's bottom edge (y = 0 of the footprint = the edge)
s = head("BarContacts_Castellated_11", "castellated edge of the front battery bar's cell-contact board: 11 plated half-holes 0.8 mm, pads 1.6 x 1.8, soldered to the BMS board",
         "castellated", "smd exclude_from_bom")
for i, x in enumerate(XS):
    s += ('  (pad "%d" thru_hole roundrect (at %.3f 0) (size 1.6 1.8) (drill 0.8) (property pad_prop_castellated) (layers "*.Cu" "*.Mask")'
          ' (roundrect_rratio 0.15))\n') % (i + 1, x - XC)
for x in XS:                                   # one courtyard per half-hole (the lane pads come down between them)
    s += rect(x - XC - 0.95, -1.0, x - XC + 0.95, 1.0, "F.CrtYd", 0.05)
s += ")\n"
open(PCB + "/commander_bar_contacts/lib/commander.pretty/BarContacts_Castellated_11.kicad_mod", "w", newline="\n").write(s)

# 3. the cell contact pad: ENIG, 6.5 mm, no paste (nothing is soldered on it)
s = head("BattContact_Pad_D6.0mm", "cell contact: a plain 6.0 mm ENIG pad the cell end presses against (no part)", "battery contact pad", "smd exclude_from_bom")
s += '  (pad "1" smd circle (at 0 0) (size 6.0 6.0) (layers "F.Cu" "F.Mask"))\n'
s += '  (fp_circle (center 0 0) (end 3.25 0) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))\n'
s += ")\n"
open(PCB + "/commander_bar_contacts/lib/commander.pretty/BattContact_Pad_D6.0mm.kicad_mod", "w", newline="\n").write(s)
print("ok, joint centre x = %.3f" % XC)
