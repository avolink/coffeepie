#!/usr/bin/env python
"""Every board in one KiCad file, as they sit in the case:  ../commander_assembly/commander_assembly.kicad_pcb

The module boards (battery, touchpad, numpad, tray, battery bar) are added by add_modules() below: see the note
there.  Set CP_ASSEMBLY_OUT to write somewhere else (for trying things out).

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/make_assembly_view.py

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
OUT_DIR = os.path.join(PCB, "commander_assembly")
OUT = os.environ.get("CP_ASSEMBLY_OUT") or os.path.join(OUT_DIR, "commander_assembly.kicad_pcb")
OVERALL = (346.98, 170.05)          # mm, the user's layout sketch (only the width is kept: see above)
GAP = float(os.environ.get("CP_SET_GAP", "11.0"))     # mm between the hub board and the keyboard (was 1: 10 mm more room)


def outline_bbox(board):
    ps = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ps, True)
    bb = ps.BBox()
    return ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom())


def copy(item):
    d = item.Duplicate()
    return d.Cast() if hasattr(d, "Cast") else d


def merge(mb, src, prefix, off, out=None, skip=None):
    """Copy every part, track, zone and drawing of board `src` into `mb`, moved by `off`, references and nets
    prefixed so that they stay apart from the mainboard's.  The new items are appended to `out` if given; drawings for
    which skip(drawing) is true are left out."""
    out = [] if out is None else out
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
        out.append(f2)
        nfp += 1
    for t in src.GetTracks():
        t2 = copy(t)
        mb.Add(t2)
        n = net_of(t)
        if n is not None:
            t2.SetNet(n)
        t2.Move(off)
        out.append(t2)
        ntr += 1
    for z in src.Zones():
        z2 = pcbnew.ZONE(z)
        mb.Add(z2)
        n = net_of(z)
        if n is not None:
            z2.SetNet(n)
        z2.Move(off)
        out.append(z2)
        nz += 1
    for d in src.GetDrawings():
        if skip is not None and skip(d):
            continue
        d2 = copy(d)
        mb.Add(d2)
        d2.Move(off)
        out.append(d2)
        nd += 1
    return nfp, ntr, nz, nd


def trim_hub_outline(mb, items, tab_right, clear=0.3):
    """In the case the hub's card tongue rests in J41, above the mainboard's tab, and the hub's body starts at x 73.0
    over the tab's last 0.9 mm.  KiCad puts every board of this file in one plane, and its 3D viewer drops a board
    outline that overlaps another: the hub did not show.  So here (this view only) the hub's outline starts just
    right of the tab: the tongue's edge lines (in the card-edge footprint and on the board) move to Dwgs.User, still
    visible, and the hub's top and bottom edges are cut back to x = tab_right + clear and closed there."""
    xc = FromMM(tab_right + clear)
    edges = [it for it in items if isinstance(it, pcbnew.PCB_SHAPE) and it.GetLayer() == pcbnew.Edge_Cuts]
    moved = cut = 0
    for fp in [it for it in items if isinstance(it, pcbnew.FOOTPRINT)]:
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                g.SetLayer(pcbnew.Dwgs_User)
                moved += 1
    ys = []
    for s in edges:
        a, b = s.GetStart(), s.GetEnd()
        if max(a.x, b.x) <= xc:                     # wholly left of the cut: part of the tongue's closure
            s.SetLayer(pcbnew.Dwgs_User)
            moved += 1
        elif min(a.x, b.x) < xc and s.GetShape() == pcbnew.SHAPE_T_SEGMENT and a.y == b.y:
            if a.x < b.x:
                s.SetStart(VECTOR2I(xc, a.y))
            else:
                s.SetEnd(VECTOR2I(xc, b.y))
            ys.append(a.y)
            cut += 1
    if len(ys) == 2:
        s = pcbnew.PCB_SHAPE(mb)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(VECTOR2I(xc, min(ys)))
        s.SetEnd(VECTOR2I(xc, max(ys)))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.1))
        mb.Add(s)
    print("hub outline for the 3D view: %d tongue edge items to Dwgs.User, %d edges cut back, closed at x %.2f%s"
          % (moved, cut, ToMM(xc), "" if len(ys) == 2 else "  (NOT closed: expected 2 edges, found %d)" % len(ys)))


def hub_stale_note(d):
    """Two User.Comments notes the hub project kept from the days it was part of the mainboard ("COMMANDER MAINBOARD
    rev A1 ..." and the PoE "ISOLATION BARRIER" note): they sit off the hub's outline and describe the mainboard,
    which has its own isolation note.  In this view they lay over the keyboard: left out here (the hub project keeps
    them)."""
    if d.GetLayer() != pcbnew.Cmts_User or not hasattr(d, "GetText"):
        return False
    return d.GetText().startswith(("COMMANDER MAINBOARD", "ISOLATION BARRIER"))


def main():
    mb = pcbnew.LoadBoard(MAIN)
    hb = pcbnew.LoadBoard(HUB)
    kb = pcbnew.LoadBoard(KBD)
    mx0, my0, mx1, my1 = outline_bbox(mb)
    hx0, hy0, hx1, hy1 = outline_bbox(hb)
    kx0, ky0, kx1, ky1 = outline_bbox(kb)
    # the hub board is drawn in the mainboard's coordinates: it goes in unmoved, card edge in J41
    hub_items = []
    n = merge(mb, hb, "HUB_", VECTOR2I(0, 0), hub_items, skip=hub_stale_note)
    print("hub board: %d parts, %d tracks / vias, %d zones, %d drawings" % n)
    trim_hub_outline(mb, hub_items, mx1)
    # keyboard: right edge as in the sketch; top edge GAP below the hub board (in the sketch the keyboard is 18 mm
    # higher, which would put it on top of the hub board: that is 21.7 mm deep).  With 1 mm the 3D viewer did not
    # show the keyboard; 11 mm since 2026-11-17.
    dx, dy = mx0 + OVERALL[0] - kx1, hy1 + GAP - ky0
    off = VECTOR2I(FromMM(dx), FromMM(dy))
    nfp, ntr, nz, nd = merge(mb, kb, "KB_", off)
    note = pcbnew.PCB_TEXT(mb)
    note.SetText("VIEW / FIT CHECK ONLY - each board is made from its own project (pcb/commander_*):\n"
                 "mainboard 6 layers 1.2 mm, hub 6 layers 0.8 mm, keyboard 2 layers 1.6 mm;\n"
                 "battery, numpad, touchpad 2 layers 1.6 mm, tray 2 layers 0.8 mm, bar BMS 4 layers 1.6 mm, bar contacts 1.0 mm")
    note.SetLayer(pcbnew.Cmts_User)
    note.SetTextSize(VECTOR2I(FromMM(3), FromMM(3)))
    note.SetTextThickness(FromMM(0.4))
    note.SetPosition(VECTOR2I(FromMM(mx0 + 150), FromMM(my0 - 14)))
    mb.Add(note)

    print("keyboard placed at offset (%.2f, %.2f) mm: %d parts, %d tracks / vias, %d zones, %d drawings" % (dx, dy, nfp, ntr, nz, nd))
    ext = add_modules(mb, ky1 + dy)
    os.makedirs(OUT_DIR, exist_ok=True)
    pcbnew.SaveBoard(OUT, mb, True)
    shutil.copyfile(os.path.splitext(MAIN)[0] + ".kicad_pro", os.path.join(OUT_DIR, "commander_assembly.kicad_pro"))
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
    # 3D bodies the boards find at ${KIPRJMOD}/lib/3d: our own small .wrl models (mid-mount USB-C, pogo pins) are
    # copied so that they resolve here too.  Vendor STEP files (the hub's Amphenol bays) are kept out of git and
    # are not copied: those parts show without a body in this view.
    wrl = 0
    for prj in sorted(os.listdir(PCB)):
        d3 = os.path.join(PCB, prj, "lib", "3d")
        if prj == os.path.basename(OUT_DIR) or not os.path.isdir(d3):
            continue
        for f in os.listdir(d3):
            if f.lower().endswith(".wrl"):
                os.makedirs(os.path.join(OUT_DIR, "lib", "3d"), exist_ok=True)
                shutil.copyfile(os.path.join(d3, f), os.path.join(OUT_DIR, "lib", "3d", f))
                wrl += 1
    print("3D models copied to lib/3d: %d" % wrl)
    x0, y0 =min(mx0, hx0, kx0 + dx), min(my0, hy0, ky0 + dy)
    x1, y1 = max([mx1, hx1, kx1 + dx] + [e[2] for e in ext]), max([my1, hy1, ky1 + dy] + [e[3] for e in ext])
    print("together: %.2f x %.2f mm  ->  %s" % (x1 - x0, y1 - y0, OUT))


# ------------------------------------------------------------------------------------------------ the module boards
# The boards built by tools/small_board.py carry their place in the chassis model (SPEC X0 / Y0 / Z0: chassis X = depth
# rear -> front, Y = length left -> right, z up).  Board (x, y) -> chassis (X0 + x, Y0 + h - y); the mainboard frame of
# this file is chassis X = y - 46.66, Y = x - 35.64.  So a module board goes in turned by 90 degrees:
#     set x = Y0 + h - y + 35.64,   set y = X0 + x + 46.66
# The tray carrier's SPEC is placed for the drawer pulled OUT (as the chassis model has it), the numpad / touchpad
# modules for the drawer closed: here the carrier is drawn closed too (TRAY_TRAVEL toward -Y), so that its pogo
# blocks J2 / J3 lie on the modules' contact pads J40 (touchpad / numpad, both at set (232.55 / 303.99, 179.63)).
# Boards that lie UNDER the top level (battery under the keyboard, the tray's modules and carrier) would hide
# each other in a top view: they are drawn in a row below the keyboard, at their true position along the case length
# (set x), and their real place is marked by a dashed outline with a label.  The battery bar's BMS has its real place
# free in this view (it clips to the front, left end) and goes in where it is.
MOD_FRAME = (35.64, 46.66)
TRAY_TRAVEL = 155.0     # mm, the drawer's travel (tray J2 open at chassis Y 351.91, touchpad J40 at 196.91)
SHIFT_Y = {"commander_tray": -TRAY_TRAVEL}
ROW_GAP = 20.0          # mm between the keyboard and the row of lower-level boards
# project, prefix, label, where ("real" = in place, "row" = in the row + dashed outline), top-view outline override
MODULES = [
    ("commander_battery", "BAT_", "BATTERY MODULE (6 x AAA) - under the keyboard, z 8.1", "row", None),
    ("commander_touchpad", "TCH_", "TOUCHPAD MODULE - in the tray, under the keyboard", "row", None),
    ("commander_numpad", "NUM_", "NUMPAD MODULE - in the tray, under the keyboard", "row", None),
    ("commander_tray", "TRAY_", "TRAY CARRIER - drawer closed, under the modules' contact edge", "row", None),
    ("commander_bar_bms", "BAR_", "FRONT BATTERY BAR - BMS board (left end cap)", "real", None),
    # the contact board stands upright at Y 21.0-22.0 (its 8.6 mm is height): laid flat in the row
    ("commander_bar_contacts", "BARC_", "BAR CONTACT BOARD - upright in the bar, laid flat here", "row", ("Y", 21.0, 1.0)),
]


def spec_of(prj):
    """SPEC of a module board (small_board.py), without running it: its X0 / Y0 / w / h."""
    import re as _re
    variant = {"commander_battery": "batt", "commander_touchpad": "touch", "commander_numpad": "numpad",
               "commander_tray": "tray", "commander_bar_bms": "bar", "commander_bar_contacts": "barcon"}[prj]
    txt = open(os.path.join(HERE, "small_board.py"), encoding="utf-8").read()
    i = txt.index('"%s": dict(' % variant)
    nxt = _re.search(r'\n    "[a-z]+": dict\(', txt[i + 1:])
    body = txt[i: i + 1 + nxt.start()] if nxt else txt[i:]
    get = lambda k: float(_re.search(r"(?<![\w.])%s=([\d.]+)" % k, body).group(1))     # noqa: E731
    return dict(w=get("w"), h=get("h"), X0=get("X0"), Y0=get("Y0"), Z0=get("Z0"))


def turn_and_place(items, b0, tx, ty):
    """Board items (just merged, unmoved): local origin = the board outline's top-left b0, turned so that local +x
    runs along set +y and local +y along set -x, then moved to (tx, ty)."""
    rot = pcbnew.EDA_ANGLE(ROT_SIGN * 90.0, pcbnew.DEGREES_T)
    o = VECTOR2I(0, 0)
    for it in items:
        it.Move(VECTOR2I(-FromMM(b0[0]), -FromMM(b0[1])))
        it.Rotate(o, rot)
        it.Move(VECTOR2I(FromMM(tx), FromMM(ty)))


def _rot_sign():
    """KiCad's sense of a positive rotation (y points down on the board): pick the one that sends (1, 0) to (0, 1)."""
    s = pcbnew.PCB_SHAPE(None)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(0, 0))
    s.SetEnd(VECTOR2I(FromMM(1), 0))
    s.Rotate(VECTOR2I(0, 0), pcbnew.EDA_ANGLE(90.0, pcbnew.DEGREES_T))
    return 1.0 if s.GetEnd().y > 0 else -1.0


ROT_SIGN = None


def merge_items(mb, src, prefix):
    """merge() without a move, returning the new items (so that they can be turned)."""
    out = []
    merge(mb, src, prefix, VECTOR2I(0, 0), out)
    return out


def label(mb, text, x, y, size=2.0):
    t = pcbnew.PCB_TEXT(mb)
    t.SetText(text)
    t.SetLayer(pcbnew.Cmts_User)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.13))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
    t.SetPosition(VECTOR2I(FromMM(x), FromMM(y)))
    mb.Add(t)


def dashed_rect(mb, x0, y0, x1, y1):
    s = pcbnew.PCB_SHAPE(mb)
    s.SetShape(pcbnew.SHAPE_T_RECT)
    s.SetStart(VECTOR2I(FromMM(x0), FromMM(y0)))
    s.SetEnd(VECTOR2I(FromMM(x1), FromMM(y1)))
    s.SetLayer(pcbnew.Cmts_User)
    try:
        s.SetStroke(pcbnew.STROKE_PARAMS(FromMM(0.3), pcbnew.LINE_STYLE_DASH))
    except (AttributeError, TypeError):
        s.SetWidth(FromMM(0.3))
    mb.Add(s)


def add_modules(mb, kb_bottom):
    global ROT_SIGN
    ROT_SIGN = _rot_sign()
    row_y = kb_bottom + ROW_GAP
    label(mb, "LOWER LEVEL - boards that lie under the keyboard / hub or in the tray, drawn here at their true position "
              "along the case; dashed outlines above = where they really are", 75.0, row_y - 6.0, 2.5)
    ext = []
    # boards in their real place first; a row board then steps down past anything it would overlap
    for prj, prefix, text, where, flat in sorted(MODULES, key=lambda m: m[3] != "real"):
        path = os.path.join(PCB, prj, prj + ".kicad_pcb")
        if not os.path.exists(path):
            print("%s: no board yet, skipped" % prj)
            continue
        s = spec_of(prj)
        s["Y0"] += SHIFT_Y.get(prj, 0.0)
        src = pcbnew.LoadBoard(path)
        b0 = outline_bbox(src)
        items = merge_items(mb, src, prefix)
        sx = s["Y0"] + s["h"] + MOD_FRAME[0]           # set x of the board's local y = 0 edge (local y runs to -x)
        real = (s["Y0"] + MOD_FRAME[0], s["X0"] + MOD_FRAME[1], s["Y0"] + s["h"] + MOD_FRAME[0], s["X0"] + s["w"] + MOD_FRAME[1])
        if flat:                                        # an upright board: its real top view is a thin strip
            real = (flat[1] + MOD_FRAME[0], real[1], flat[1] + flat[2] + MOD_FRAME[0], real[3])
        if where == "real":
            ty = s["X0"] + MOD_FRAME[1]
        else:
            ty = row_y
            moved = True
            while moved:
                moved = False
                for e in ext:
                    if sx - s["h"] < e[2] + 2 and e[0] < sx + 2 and ty < e[3] + 14 and e[1] < ty + s["w"] + 2:
                        ty, moved = e[3] + 14.0, True   # (clear of the board above and its label)
            dashed_rect(mb, *real)
            label(mb, text.split(" - ")[0], real[0] + 1.0, real[1] + 3.0, 1.6)
        turn_and_place(items, b0, sx, ty)
        bx = (sx - s["h"], ty, sx, ty + s["w"])
        name, _, where_txt = text.partition(" - ")
        label(mb, "%s\n%s\n[%s, z %.1f]" % (name, where_txt, prj, s["Z0"]), bx[0], bx[3] + 3.0, 1.6)
        ext.append(bx)
        print("%-24s %-5s %3d items, set x %.1f-%.1f y %.1f-%.1f" % (prj, where, len(items), bx[0], bx[2], bx[1], bx[3]))
    return ext


if __name__ == "__main__":
    sys.exit(main())
