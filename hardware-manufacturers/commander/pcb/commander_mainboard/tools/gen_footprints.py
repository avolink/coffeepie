#!/usr/bin/env python3
"""Generates the project-specific footprints into lib/commander.pretty.

Everything else comes from the stock KiCad libraries.  Footprints flagged
PROVISIONAL in their description are reconstructed (from Radxa's published
placement drawings or from typical package data) and must be replaced by the
manufacturer land pattern before fabrication.
"""
import os
import re

import cpmodel

OUT = os.path.join(cpmodel.ROOT, "lib", "commander.pretty")
ROWS = "A B C D E F G H J K L M N P R T U V W Y AA AB AC AD AE AF AG AH AJ AK AL AM AN AP AR".split()


def rk3566_xy(ball):
    """Ball name -> (x, y) in mm, package centre origin, A1 corner top-left (KiCad: +y down).

    FCCSP-565: outer balls on a 38 x 35 grid at 0.40 mm, inner balls (names prefixed '1')
    on a 20 x 18 grid at 0.65 mm.  Verified against all 565 pad positions of the Radxa
    ZERO 3E V1.2 placement drawing (see tools/check_consistency.py).
    """
    m = re.match(r"^(1?)([A-Z]+)(\d+)$", ball)
    inner, row, col = m.group(1), ROWS.index(m.group(2)), int(m.group(3))
    if inner:
        return (col - 10.5) * 0.65, (row - 8.5) * 0.65
    return (col - 19.5) * 0.40, (row - 17) * 0.40


def header(name, descr, tags, smd=True):
    return (f'(footprint "{name}" (version 20240108) (generator "pcbnew") (generator_version "8.0") (layer "F.Cu")\n'
            f'  (descr "{descr}")\n  (tags "{tags}")\n'
            f'  (property "Reference" "REF**" (at 0 0 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            f'  (property "Value" "{name}" (at 0 0 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            f'  (attr {"smd" if smd else "through_hole"})\n')


def rect(layer, x0, y0, x1, y1, w=0.1):
    return f'  (fp_rect (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (stroke (width {w}) (type solid)) (fill none) (layer "{layer}"))\n'


def line(layer, x0, y0, x1, y1, w=0.12):
    return f'  (fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (stroke (width {w}) (type solid)) (layer "{layer}"))\n'


def text(layer, s, x, y, size=0.6):
    return f'  (fp_text user "{s}" (at {x:.3f} {y:.3f} 0) (layer "{layer}") (effects (font (size {size} {size}) (thickness {size * 0.15:.3f}))))\n'


def smd(name, shape, x, y, w, h, mask=None, extra=""):
    m = f" (solder_mask_margin {mask})" if mask is not None else ""
    return f'  (pad "{name}" smd {shape} (at {x:.4f} {y:.4f}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask"){m}{extra})\n'


def outline(body_w, body_h, crt=0.5, pin1=True):
    s = rect("F.Fab", -body_w / 2, -body_h / 2, body_w / 2, body_h / 2)
    s += rect("F.CrtYd", -body_w / 2 - crt, -body_h / 2 - crt, body_w / 2 + crt, body_h / 2 + crt, 0.05)
    s += rect("F.SilkS", -body_w / 2 - 0.1, -body_h / 2 - 0.1, body_w / 2 + 0.1, body_h / 2 + 0.1, 0.12)
    if pin1:
        s += f'  (fp_circle (center {-body_w / 2 - 0.45:.3f} {-body_h / 2 - 0.45:.3f}) (end {-body_w / 2 - 0.3:.3f} {-body_h / 2 - 0.45:.3f}) (stroke (width 0.15) (type solid)) (fill solid) (layer "F.SilkS"))\n'
    return s


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + ".kicad_mod"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body + ")\n")
    print("  lib/commander.pretty/" + name + ".kicad_mod")


def main():
    d = cpmodel.load()

    # ---- RK3566 ----
    name = "RK3566_FCCSP-565_15.5x14.4mm"
    s = header(name, "Rockchip RK3566 FCCSP-565, 15.5 x 14.4 mm, outer ring 0.40 mm pitch, inner field 0.65 mm pitch; "
                     "ball map checked against the Radxa ZERO 3E V1.2 pad drawing", "BGA FCCSP 565 RK3566")
    s += outline(15.5, 14.4, crt=0.25)
    for ball in d.comps["U1"].pins:
        x, y = rk3566_xy(ball)
        s += smd(ball, "circle", x, y, 0.25, 0.25, mask=0.05)
    write(name, s)

    # ---- WLCSP-12, 3 columns x 4 rows, 0.5 mm (UM3204H; pitch measured on the Radxa pad drawing) ----
    name = "WLCSP-12_3x4_P0.5mm"
    s = header(name, "WLCSP-12, 3 x 4 balls, 0.5 mm pitch (Union UM3204H)", "WLCSP CSP 12")
    s += outline(1.6, 2.1, crt=0.3)
    for r, row in enumerate("ABCD"):
        for c in range(3):
            s += smd(f"{row}{c + 1}", "circle", (c - 1) * 0.5, (r - 1.5) * 0.5, 0.25, 0.25, mask=0.05)
    write(name, s)

    # ---- low-profile sunk RJ45 (HanRun HR6042S), reconstructed from the Radxa drawings ----
    # local frame: origin on the board edge at the centre of the notch, jack opening towards -y,
    # +y runs into the board.  The notch itself (16 mm x 6.2 mm) is part of the board outline.
    name = "RJ45_HR6042S_8P8C_LowProfile"
    s = header(name, "PROVISIONAL - low-profile sunk RJ45 8P8C without magnetics (HanRun HR6042S-1188N15B-1R), land pattern "
                     "reconstructed from the Radxa ZERO 3E placement drawing; replace with the datasheet pattern", "RJ45 8P8C sunk")
    for n in range(1, 9):
        lx = 10.435 + 1.02 * n - 15.025
        ly = 7.886 if n % 2 else 9.24
        s += smd(str(n), "rect", lx, ly, 0.6, 1.0)
    for sx in (-8.04, 8.04):
        s += (f'  (pad "SH" thru_hole oval (at {sx} 1.735) (size 1.83 3.57) (drill oval 0.9 2.6) '
              f'(layers "*.Cu" "*.Mask"))\n')
    s += rect("F.Fab", -8.2, -6.4, 8.2, 10.7)
    s += rect("F.CrtYd", -9.4, -6.9, 9.4, 11.2, 0.05)
    s += line("Dwgs.User", -7.455, 0, -7.455, 3.66) + line("Dwgs.User", -7.455, 3.66, -7.005, 6.17)
    s += line("Dwgs.User", -7.005, 6.17, 7.005, 6.17) + line("Dwgs.User", 7.005, 6.17, 7.455, 3.66)
    s += line("Dwgs.User", 7.455, 3.66, 7.455, 0)
    s += text("Dwgs.User", "board notch", 0, 4.6, 0.8)
    write(name, s)

    # ---- single-channel LAN transformer, 6 pads (Radxa: GB020G00) ----
    name = "XFMR_LAN_1CH_6P"
    s = header(name, "PROVISIONAL - single-channel 1:1 LAN transformer with centre taps, 6 pads, 3.2 x 3.2 mm body "
                     "(Radxa: GB020G00); pad 1-2-6 chip side, 5-4-3 line side", "LAN transformer")
    s += outline(3.2, 3.2, crt=0.4)
    for num, x, y in (("1", -1.45, -1.0), ("6", -1.45, 0.0), ("2", -1.45, 1.0), ("5", 1.45, -1.0), ("3", 1.45, 0.0), ("4", 1.45, 1.0)):
        s += smd(num, "rect", x, y, 0.9, 0.55)
    write(name, s)

    # ---- 0504 common-mode choke (HDMI: BCMF062P120T) ----
    name = "CMC_0504_4P"
    s = header(name, "common-mode choke 0504 (0.65 x 0.5 mm), 4 pads at 0.5 mm; windings 1-2 and 4-3", "CMC 0504")
    s += outline(0.85, 0.65, crt=0.25, pin1=False)
    for num, x, y in (("1", -0.26, -0.25), ("2", 0.26, -0.25), ("4", -0.26, 0.25), ("3", 0.26, 0.25)):
        s += smd(num, "rect", x, y, 0.3, 0.3)
    write(name, s)

    # ---- PoE flyback transformer placeholder ----
    name = "XFMR_Flyback_EP13_PLACEHOLDER"
    s = header(name, "PROVISIONAL placeholder for the PoE flyback transformer (EP13 class, 17.5 x 13.5 mm, up to 12.7 mm tall). "
                     "Pads are named by function; renumber to the selected part (e.g. Coilcraft POE300F-50L)", "flyback transformer PoE")
    s += outline(17.5, 13.5, crt=0.5, pin1=False)
    for num, x, y in (("PA", -6.0, -7.4), ("PB", -2.0, -7.4), ("XA", 2.0, -7.4), ("XB", 6.0, -7.4), ("SA", -4.0, 7.4), ("SB", 4.0, 7.4)):
        s += smd(num, "rect", x, y, 2.4, 2.0)
    s += text("F.Fab", "PRI / AUX", 0, -4.5, 1.0) + text("F.Fab", "SEC", 0, 4.5, 1.0)
    write(name, s)


if __name__ == "__main__":
    main()
