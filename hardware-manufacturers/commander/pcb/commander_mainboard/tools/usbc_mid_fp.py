#!/usr/bin/env python
"""usbc_mid_fp.py PROJECT_DIR [...] - writes the mid-mount 16-pin USB-C receptacle HCTL HC-TYPE-C-16P-CB1.6
(LCSC C2894902) into each project's lib: lib/commander.pretty/USB_C_Receptacle_HCTL_HC-TYPE-C-16P-CB1.6.kicad_mod and a
plain box model lib/3d/USB_C_Receptacle_HCTL_HC-TYPE-C-16P-CB1.6.wrl (2026-11-18, numpad / touchpad J1).

Sources: HCTL customer drawing HC-TYPE-C-16P-CB1.6 rev C ("USB CF 16PIN (L=6.5) MID MOUNT 1.6MM", centre height
-0.02 mm: body 3.16 mm tall, 1.56 above the board's top face and 1.60 below it = flush with the underside of a 1.6 mm
board) and LCSC / EasyEDA's footprint of C2894902 (same pad x positions; its y positions are used, measured from the
board edge).  Frame as KiCad's HRO TYPE-C-31-M-12: origin on the board edge at the receptacle's centre line, mouth
towards +y, the board (and the pads) towards -y; A1 / B12 on the left.

Board notch (Edge.Cuts, drawn by small_board.py from SPEC "notch", shown here on User.1): 9.50 mm wide (drawing: 9.24,
EasyEDA: 9.32 - 0.13 mm more each side so the R0.5 the router leaves in the inner corners clears the 8.94 mm body),
6.60 mm deep.  The pad row's near end is then 0.17 mm from the notch's end (as in the maker's layout): the module
projects carry a DRC rule for it (J1 pads to the board edge 0.15 mm).
"""
import os
import sys

NAME = "USB_C_Receptacle_HCTL_HC-TYPE-C-16P-CB1.6"
PAD_Y = -7.347                         # pad row centre (EasyEDA: 28.93 x 10 mil behind the board edge)
PAD_L = 1.15
SIG = [("B8", -1.75), ("A5", -1.25), ("B7", -0.75), ("A6", -0.25), ("A7", 0.25), ("B6", 0.75), ("A8", 1.25), ("B5", 1.75)]
WIDE = [("A1", -3.20), ("B12", -3.20), ("A4", -2.40), ("B9", -2.40), ("A9", 2.40), ("B4", 2.40), ("A12", 3.20), ("B1", 3.20)]
SLOT_X = 5.62
SLOTS = [(-6.175, 1.0, 1.8, 0.6, 1.4), (-2.177, 1.0, 2.2, 0.6, 1.8)]      # y, pad w, pad l, drill w, drill l (drawing)
NOTCH_HW, NOTCH_D, NOTCH_R = 4.75, 6.60, 0.5
BODY_HW, BODY_L, BODY_TOP, BODY_BOT = 4.47, 6.50, 1.56, -1.60


def fp_text():
    o = []
    o.append('(footprint "%s"' % NAME)
    o.append('  (version 20240108) (generator "usbc_mid_fp")')
    o.append('  (layer "F.Cu")')
    o.append('  (descr "HCTL HC-TYPE-C-16P-CB1.6 (LCSC C2894902): USB-C receptacle, USB 2.0, 16 pins, mid mount in a board '
             'notch, 1.6 mm board (body flush with the underside). Drawing HC-TYPE-C-16P-CB1.6 rev C + EasyEDA footprint. '
             'Needs a %.2f x %.2f mm notch at the board edge, R%.1f inner corners (User.1)")' % (2 * NOTCH_HW, NOTCH_D, NOTCH_R))
    o.append('  (tags "USB C Type-C receptacle mid-mount sink 16P")')
    o.append('  (attr smd)')
    o.append('  (property "Reference" "REF**" (at 0 -9.2 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    o.append('  (property "Value" "%s" (at 0 1.6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))' % NAME)
    for n, x in SIG:
        o.append('  (pad "%s" smd roundrect (at %.3f %.3f) (size 0.300 %.3f) (layers "F.Cu" "F.Paste" "F.Mask") '
                 '(roundrect_rratio 0.25))' % (n, x, PAD_Y, PAD_L))
    for n, x in WIDE:
        o.append('  (pad "%s" smd roundrect (at %.3f %.3f) (size 0.600 %.3f) (layers "F.Cu" "F.Paste" "F.Mask") '
                 '(roundrect_rratio 0.25))' % (n, x, PAD_Y, PAD_L))
    for y, pw, pl, dw, dl in SLOTS:
        for sx in (-SLOT_X, SLOT_X):
            o.append('  (pad "SH" thru_hole oval (at %.3f %.3f) (size %.3f %.3f) (drill oval %.3f %.3f) (layers "*.Cu" "*.Mask"))'
                     % (sx, y, pw, pl, dw, dl))
    # the notch (documentation; the outline itself is drawn by the board generator)
    hw, d, r = NOTCH_HW, NOTCH_D, NOTCH_R

    def line(a, b, layer, w=0.1):
        o.append('  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width %.2f) (type solid)) (layer "%s"))'
                 % (a[0], a[1], b[0], b[1], w, layer))
    line((-hw, 0), (-hw, -(d - r)), "User.1")
    o.append('  (fp_arc (start %.3f %.3f) (mid %.3f %.3f) (end %.3f %.3f) (stroke (width 0.10) (type solid)) (layer "User.1"))'
             % (-hw, -(d - r), -hw + r * (1 - 0.70711), -(d - r * (1 - 0.70711)), -(hw - r), -d))
    line((-(hw - r), -d), (hw - r, -d), "User.1")
    o.append('  (fp_arc (start %.3f %.3f) (mid %.3f %.3f) (end %.3f %.3f) (stroke (width 0.10) (type solid)) (layer "User.1"))'
             % (hw - r, -d, hw - r * (1 - 0.70711), -(d - r * (1 - 0.70711)), hw, -(d - r)))
    line((hw, -(d - r)), (hw, 0), "User.1")
    # body on F.Fab, board edge on F.Fab, courtyard (body + wings + pads + 0.25)
    for a, b in (((-BODY_HW, 0), (BODY_HW, 0)), ((BODY_HW, 0), (BODY_HW, -BODY_L)), ((BODY_HW, -BODY_L), (-BODY_HW, -BODY_L)),
                 ((-BODY_HW, -BODY_L), (-BODY_HW, 0))):
        line(a, b, "F.Fab")
    cx, cy0, cy1 = SLOT_X + 0.5 + 0.25, 0.0, PAD_Y - PAD_L / 2 - 0.25
    for a, b in (((-cx, cy0), (cx, cy0)), ((cx, cy0), (cx, cy1)), ((cx, cy1), (-cx, cy1)), ((-cx, cy1), (-cx, cy0))):
        line(a, b, "F.CrtYd", 0.05)
    # silk: the two sides behind the wings, clear of the pads
    line((-BODY_HW - 0.15, -3.4), (-BODY_HW - 0.15, -5.0), "F.SilkS", 0.12)
    line((BODY_HW + 0.15, -3.4), (BODY_HW + 0.15, -5.0), "F.SilkS", 0.12)
    o.append('  (model "${KIPRJMOD}/lib/3d/%s.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))' % NAME)
    o.append(')')
    return "\n".join(o) + "\n"


def wrl_text():
    """A box for the body (3.16 mm tall, centre 0.02 mm under the board's top face) and two thin wings; VRML units are
    0.1 inch.  KiCad's model frame: x right, y UP (= -footprint y), z up from the board's top face."""
    k = 1 / 2.54

    def box(x0, x1, y0, y1, z0, z1, col):
        pts = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
        p = ", ".join("%.4f %.4f %.4f" % (x * k, y * k, z * k) for x, y, z in pts)
        faces = "0,2,3,1,-1, 4,5,7,6,-1, 0,1,5,4,-1, 2,6,7,3,-1, 0,4,6,2,-1, 1,3,7,5,-1"
        return ("Shape { appearance Appearance { material Material { diffuseColor %s specularColor 0.5 0.5 0.5 } }\n"
                "  geometry IndexedFaceSet { coord Coordinate { point [ %s ] } coordIndex [ %s ] } }\n" % (col, p, faces))
    steel = "0.75 0.75 0.78"
    out = ["#VRML V2.0 utf8\n# %s - plain box model written by usbc_mid_fp.py\n" % NAME]
    # (model y = -footprint y: the body runs from the board edge (y 0) to 6.5 mm into the board (model y +6.5))
    out.append(box(-BODY_HW, BODY_HW, 0.0, BODY_L, BODY_BOT, BODY_TOP, steel))
    for sx in (-1, 1):            # wings with the shell tabs, on the board's top face
        out.append(box(sx * BODY_HW, sx * (SLOT_X + 0.3), 1.2, 6.9, 0.0, 0.3, steel) if sx > 0 else
                   box(-(SLOT_X + 0.3), -BODY_HW, 1.2, 6.9, 0.0, 0.3, steel))
    return "".join(out)


def main():
    for prj in sys.argv[1:]:
        lib = os.path.join(prj, "lib", "commander.pretty")
        d3 = os.path.join(prj, "lib", "3d")
        os.makedirs(lib, exist_ok=True)
        os.makedirs(d3, exist_ok=True)
        with open(os.path.join(lib, NAME + ".kicad_mod"), "w", encoding="utf-8", newline="\n") as f:
            f.write(fp_text())
        with open(os.path.join(d3, NAME + ".wrl"), "w", encoding="utf-8", newline="\n") as f:
            f.write(wrl_text())
        print(prj, "->", NAME)


if __name__ == "__main__":
    main()
