#!/usr/bin/env python3
"""kbd_optical_model.py OUTDIR - the 3D stand-in of the keyboard's key footprint, for the chassis model.

The keyboard came from Altium; its key footprint ("Interruptor optico Keychron de bajo perfil", 84 of them) carries
the three soldered parts of an optical key - infra-red emitter, phototransistor, backlight LED - and an embedded STEP
body that the 3D export for SketchUp cannot read.  The export used to put ONE 6.6 x 11 x 6 mm block there (the pads'
bounding box at a guessed switch height), which looks nothing like the board.  This writes
OUTDIR/Interruptor__ptico_Keychron_de_bajo_perfil.wrl with the three parts as they are on the board:

    emitter   pads 1 / 4  (x 3.74, y -4.35 / -2.10)   side-looking, 2.1 x 1.0 x 1.0 mm, lens towards the key's centre
    receiver  pads 2 / 5  (x 9.04, ...)                the same, black, lens towards the emitter
    LED       pads 3 / 6  (x 5.83 / 8.08, y -11.86)    2.0 x 1.25 x 0.8 mm

Sizes: the pad pitch of all three is 2.25 mm with 1.3 mm pads - 0805-size parts; 2.1 mm is the length in the switch
maker's footprint drawing.  Heights are ESTIMATES (no part numbers in the Altium design).  The switch itself is a
plug-in part and is not drawn.  VRML units are 2.54 mm, y up (KiCad's footprint y is down)."""
import os
import sys

U = 2.54


def box(cx, cy, cz, sx, sy, sz, col):
    return ("Transform { translation %.5f %.5f %.5f children [ Shape { appearance Appearance { material Material { "
            "diffuseColor %.2f %.2f %.2f } } geometry Box { size %.5f %.5f %.5f } } ] }\n"
            % (cx / U, -cy / U, cz / U, col[0], col[1], col[2], sx / U, sy / U, sz / U))


def dome(cx, cy, cz, r, h, col):
    # a cylinder standing on the board (VRML's cylinder axis is y: turned about x); half of it is inside the body
    return ("Transform { translation %.5f %.5f %.5f rotation 1 0 0 1.5708 children [ Shape { appearance Appearance { "
            "material Material { diffuseColor %.2f %.2f %.2f } } geometry Cylinder { radius %.5f height %.5f } } ] }\n"
            % (cx / U, -cy / U, cz / U, col[0], col[1], col[2], r / U, h / U))


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    clear, black, led, tin = (0.78, 0.84, 0.92), (0.06, 0.06, 0.07), (0.96, 0.86, 0.30), (0.80, 0.80, 0.78)
    ymid = (-4.35 - 2.10) / 2
    s = "#VRML V2.0 utf8\n"
    for x, col, face in ((3.74, clear, +1), (9.04, black, -1)):
        s += box(x, ymid, 0.5, 1.0, 2.1, 1.0, col)                       # body
        s += dome(x + face * 0.5, ymid, 0.5, 0.6, 1.0, col)              # lens, towards the key's centre
        for y in (-4.35, -2.10):
            s += box(x, y + (0.38 if y < ymid else -0.38), 0.15, 1.0, 0.35, 0.3, tin)    # end terminals
    xl = (5.83 + 8.08) / 2
    s += box(xl, -11.86, 0.4, 2.0, 1.25, 0.8, led)
    for x in (5.83, 8.08):
        s += box(x + (-0.2 if x < xl else 0.2), -11.86, 0.15, 0.35, 1.25, 0.3, tin)
    name = "Interruptor__ptico_Keychron_de_bajo_perfil.wrl"
    open(os.path.join(out, name), "w", encoding="ascii").write(s)
    print("wrote", os.path.join(out, name))
    # the keyboard's 185 0805 resistors (also an embedded Altium body): the part's own size instead of the pads' box
    r = "#VRML V2.0 utf8\n" + box(0.0, 0.0, 0.25, 2.0, 1.25, 0.5, (0.12, 0.12, 0.12))
    open(os.path.join(out, "Res_0805.wrl"), "w", encoding="ascii").write(r)
    print("wrote", os.path.join(out, "Res_0805.wrl"))


if __name__ == "__main__":
    main()
