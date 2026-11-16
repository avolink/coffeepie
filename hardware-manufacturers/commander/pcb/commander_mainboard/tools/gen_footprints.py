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
    if "U1" in d.comps:                     # variants without the codec core skip this footprint
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
    # ---- PoE flyback transformer: Bourns PLN0xx-ER20 planar series (PLN060-ER20A05S) ----
    # Land pattern from the Bourns data sheet (rev. 01/24, "Recommended Layout"), drawn turned half a turn so the
    # primary / auxiliary row (pins 1-4) is at the top and the secondary row (pins 5, 6) at the bottom.
    # Rows: inner edges 19.0 mm apart, outer edges 23.5 mm; small pads 2.85 / 2.60 mm wide, large pads 3.8 mm.
    name = "XFMR_Bourns_PLN0xx-ER20"
    s = header(name, "Bourns PLN0xx-ER20 planar flyback transformer, 22.5 x 21.0 mm, 8.0 mm tall (PLN060-ER20A05S: 36-72 V in, "
                     "5 V out, 200 kHz, 1500 Vrms). Pins 2-3 primary, 1-4 auxiliary, 5-6 secondary. Check against the current data sheet",
               "planar flyback transformer PoE Bourns PLN")
    s += rect("F.Fab", -10.5, -10.6, 10.5, 9.4)
    s += rect("F.CrtYd", -10.75, -12.6, 10.75, 11.4, 0.05)
    s += rect("F.SilkS", -10.6, -10.0, 10.6, 8.8, 0.12)
    for num, x, y, w in (("4", -7.475, -11.225, 2.85), ("3", -4.35, -11.225, 2.6), ("2", 4.35, -11.225, 2.6), ("1", 7.475, -11.225, 2.85),
                         ("5", -8.25, 10.025, 3.8), ("6", 8.25, 10.025, 3.8)):
        s += smd(num, "rect", x, y, w, 2.25)
    s += text("F.Fab", "PRI 2-3 / AUX 1-4", 0, -6.0, 1.0) + text("F.Fab", "SEC 5-6", 0, 5.5, 1.0)
    write(name, s)

    # ---- M.2 Key M card edge (the hub board's plug, branch m2-hub) ----
    # Taken from KiCad's own Connector_PCBEdge:M.2_2230-xx-M (PCI-SIG M.2 Electromechanical Spec 1.0): its 67 finger
    # pads and the tongue part of its outline (y >= 0: the key notch and the two lead-in corners).  The card body
    # outline of a 2230 module is left out; the hub board draws its own, meeting the tongue at x = +-11, y = 0.
    # Local frame as in KiCad's footprint: the card's mating edge at y = 4, the card body towards -y.
    name = "M2_CardEdge_KeyM_Tongue"
    src = stock_footprint("Connector_PCBEdge.pretty", "M.2_2230-xx-M.kicad_mod")
    if src:
        s = header(name, "M.2 Key M card-edge fingers (67), 0.8 mm board, from KiCad M.2_2230-xx-M without the card body outline. "
                         "Fab notes: ENIG on the fingers, 20 deg bevel on the mating edge, no copper or mask in the key notch",
                   "M.2 card edge Key M")
        for blk in sexpr_blocks(src, "pad"):
            s += "  " + blk + "\n"
        for blk in sexpr_blocks(src, "fp_line") + sexpr_blocks(src, "fp_arc"):
            ys = [float(v) for v in re.findall(r"\((?:start|mid|end) [-\d.]+ ([-\d.]+)\)", blk)]
            # (the two shoulder lines along y = 0 are the 22 mm card body: the hub board's own outline meets the
            #  lead-in arcs at x = +-10.425 instead, its body being the strip's 21.72 mm)
            # (the key notch's rounded end dips to y -0.1: keep everything that reaches into the tongue, y > 0)
            if '"Edge.Cuts"' in blk and ys and min(ys) > -1.0 and max(ys) > 0:
                s += "  " + blk + "\n"
        s += text("Dwgs.User", "ENIG, 20deg bevel, 0.8 mm", 0, -1.5, 0.8)
        s += rect("F.CrtYd", -11.25, 0.0, 11.25, 4.25, 0.05)     # (stops at the board body: parts may start there)
        write(name, s)
    m2_socket()
    usbc24_hoauc()


def usbc24_hoauc():
    """HOAUC HYCW275-USBC24-050B (LCSC C42400261): USB-C 24-pin receptacle, right angle, top mount, two staggered
    rows of SMD pads at the back, 3.26 mm tall.  Land pattern from the JLCEDA/EasyEDA Official Library footprint
    "USB-C-SMD_HYCW275-USBC24-050B" (https://lceda.cn/, https://easyeda.com), checked against HOAUC drawing
    HYC-2109011553 (holes 6.80 apart and 5.90 behind the front, front legs 8.64 apart and 2.70 behind it).
    Origin: centre of the mating face, which is flush with the board edge ("product edge"); the body runs
    towards -y.  The four rear hold-down slots pair up into an L on each side."""
    name = "USB_C_Receptacle_HOAUC_HYCW275-USBC24-050B"
    s = header(name, "HOAUC HYCW275-USBC24-050B USB-C 24P receptacle, right angle, top mount, 3.26 mm tall (LCSC C42400261). "
                     "Footprint source: JLCEDA/EasyEDA Official Library (https://lceda.cn/, https://easyeda.com), "
                     "checked against HOAUC drawing HYC-2109011553", "USB C Type-C receptacle 24P HOAUC", smd=False)
    for i in range(12):                                  # A1..A12 left to right, B12..B1 left to right, 0.5 mm, staggered
        s += smd("A%d" % (i + 1), "rect", -2.63 + 0.5 * i, -7.82, 0.25, 0.95)
        s += smd("B%d" % (12 - i), "rect", -2.88 + 0.5 * i, -6.57, 0.25, 0.95)
    for sx in (-1, 1):
        s += (f'  (pad "SH" thru_hole oval (at {3.84 * sx:.2f} -6.85) (size 1.5 1.0) (drill oval 1.3 0.6) '
              f'(layers "*.Cu" "*.Mask"))\n')
        s += (f'  (pad "SH" thru_hole oval (at {4.34 * sx:.2f} -7.35) (size 1.0 2.0) (drill oval 0.6 1.6) '
              f'(layers "*.Cu" "*.Mask"))\n')
        s += (f'  (pad "SH" thru_hole oval (at {4.32 * sx:.2f} -2.70) (size 1.3 2.5) (drill oval 0.9 2.1) '
              f'(layers "*.Cu" "*.Mask"))\n')
        s += (f'  (pad "" np_thru_hole circle (at {3.40 * sx:.2f} -5.90) (size 0.6 0.6) (drill 0.6) '
              f'(layers "*.Cu" "*.Mask"))\n')
    s += rect("F.Fab", -4.47, -7.90, 4.47, 0.0)
    s += rect("F.CrtYd", -5.25, -8.60, 5.25, 0.25, 0.05)
    s += line("F.SilkS", -4.62, -5.00, -4.62, -4.15) + line("F.SilkS", 4.62, -5.00, 4.62, -4.15)
    s += line("F.SilkS", -4.62, -1.25, -4.62, 0.0) + line("F.SilkS", 4.62, -1.25, 4.62, 0.0)
    s += text("F.Fab", "mating face / board edge", 0, 0.8, 0.5)
    s += f'  (fp_circle (center -2.63 -8.75) (end -2.48 -8.75) (stroke (width 0.15) (type solid)) (fill solid) (layer "F.SilkS"))\n'
    write(name, s)


def m2_socket():
    """LOTES APCI0146-P00xA, M.2 Key M socket, top mount, H 2.06 mm (drawing AP-APCI0146-P rev A, sheet 3,
    "recommended PCB layout").  Origin: centre of the slot on the housing's front face (where the card enters);
    the card comes from +y.  Rows measured from the back row's outer pad edge (yb): back (odd) row 0-1.55,
    hold-down pads 0-2.75, locating posts at 6.05, front (even) row 7.55-9.10; front face at 8.72 (post 2.67
    behind it, side view on sheet 1)."""
    name = "M2_Socket_KeyM_LOTES_APCI0146"
    f = 8.72                                   # yb of the front face
    s = header(name, "LOTES APCI0146-P001A/-P002A M.2 Key M socket, 0.5 mm, top mount, 2.06 mm tall, card 0.3 mm above "
                     "the board (LCSC C841645). Land pattern from drawing AP-APCI0146-P sheet 3", "M.2 socket Key M LOTES")
    for n in range(1, 76):
        if 59 <= n <= 66:
            continue
        if n % 2:
            s += smd(str(n), "rect", -9.25 + (n - 1) * 0.25, 0.775 - f, 0.30, 1.55)
        else:
            s += smd(str(n), "rect", -9.0 + (n - 2) * 0.25, 8.325 - f, 0.30, 1.55)
    for x in (-10.35, 10.35):
        s += smd("MP", "rect", x, 1.375 - f, 1.20, 2.75)
    for x, d in ((-10.0, 1.10), (10.0, 1.60)):
        s += (f'  (pad "" np_thru_hole circle (at {x} {6.05 - f:.3f}) (size {d} {d}) (drill {d}) '
              f'(layers "*.Cu" "*.Mask"))\n')
    s += rect("F.Fab", -10.925, -6.60, 10.925, 0.0)
    s += rect("F.CrtYd", -11.25, -9.0, 11.25, 0.6, 0.05)
    s += line("F.SilkS", -10.925, 0.0, -9.6, 0.0) + line("F.SilkS", 9.6, 0.0, 10.925, 0.0)
    s += text("F.Fab", "card enters here", 0, 1.2, 0.6)
    s += f'  (fp_circle (center -9.25 {-f - 0.5:.3f}) (end -9.1 {-f - 0.5:.3f}) (stroke (width 0.15) (type solid)) (fill solid) (layer "F.SilkS"))\n'
    write(name, s)


def stock_footprint(lib, name):
    """Text of a footprint from KiCad's own library (Windows install, also seen from WSL), or None."""
    for base in (os.environ.get("KICAD_FOOTPRINT_DIR", ""), "C:/Program Files/KiCad/10.0/share/kicad/footprints",
                 "/mnt/c/Program Files/KiCad/10.0/share/kicad/footprints"):
        p = os.path.join(base, lib, name)
        if base and os.path.exists(p):
            return open(p, encoding="utf-8").read()
    print("  (KiCad footprint library not found: %s/%s skipped)" % (lib, name))
    return None


def sexpr_blocks(text_, head):
    """Every top-level '(head ...)' block inside a footprint, as one line each."""
    out, i = [], 0
    pat = re.compile(r"\(" + re.escape(head) + r"\s")
    while True:
        m = pat.search(text_, i)
        if not m:
            return out
        i = m.start()
        depth, j = 0, i
        while True:
            if text_[j] == "(":
                depth += 1
            elif text_[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(" ".join(text_[i:j + 1].split()))
        i = j + 1


if __name__ == "__main__":
    main()
