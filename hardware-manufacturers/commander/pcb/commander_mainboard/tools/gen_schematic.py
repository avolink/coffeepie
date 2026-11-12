#!/usr/bin/env python3
"""Generates the KiCad symbol library and the hierarchical schematic from the design model.

    python tools/gen_schematic.py

Outputs (all regenerated, never hand-edit):
    lib/commander.kicad_sym
    commander_mainboard.kicad_sch            root sheet (index)
    sheets/<sheet>.kicad_sch                 one per SHEET in src/netlist

Drawing style: "netlist schematic".  Every pin carries a global label with its net
name instead of drawn wires, so connectivity is explicit, greppable and ERC-checkable,
and the sheets can be regenerated after any netlist change without manual rework.
"""
import glob
import os
import re
import uuid

import cpmodel
from cpmodel import PARTS, ROOT

PROJECT = "commander_mainboard"
NS = uuid.UUID("6f1b7b0e-4c0a-4b54-9a3e-c0ffee9ec0de")
G = 1.27                  # schematic grid
PITCH = 2 * G             # pin pitch
CHAR = 1.02               # estimated width of one label character (mm) at 1.27 mm text
MAXROWS = 50              # pins per side before an IC is split into another unit

SHEET_TITLES = {
    "soc_misc": "RK3566 - SARADC, VCCIO4, VCCIO7",
    "soc_usb": "RK3566 - USB PHYs, VCCIO2",
    "soc_pmu": "RK3566 - oscillator, PLL, PMUIO",
    "soc_gmac": "RK3566 - RGMII (VCCIO6), CSI",
    "soc_video": "RK3566 - HDMI, DSI, eDP",
    "soc_gpio": "RK3566 - VCCIO5, VCCIO1, VCCIO3",
    "soc_ddr": "RK3566 - DDR PHY",
    "soc_power": "RK3566 - core supplies and ground",
    "lpddr4": "LPDDR4 memory",
    "hdmi": "micro HDMI output",
    "ethernet": "Gigabit Ethernet PHY, magnetics, RJ45",
    "pmic": "RK817-5 PMIC",
    "power": "5 V rail, service USB-C, VDD_CPU",
    "storage": "eMMC, microSD, EEPROM, service header",
    "poe": "PoE PD and isolated 5 V flyback (NEW)",
    "usb3_hub": "USB5744 hub and SuperSpeed bays 1-4 (NEW)",
    "usb2_hub": "USB2517 hub, Hi-Speed bays 5-9, keyboard link (NEW)",
    "battery": "Front battery port (USB-C) and PoE / battery 5 V selector (NEW)",
}


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def f(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def snap(x):
    return round(x / G) * G


FONT = "(effects (font (size 1.27 1.27)))"
FONT_HIDE = "(effects (font (size 1.27 1.27)) (hide yes))"


# --------------------------------------------------------------------------
# library symbols
# --------------------------------------------------------------------------
def _props(ref_prefix, value, fp, desc, ref_at, val_at):
    return (
        f'    (property "Reference" {q(ref_prefix)} (at {f(ref_at[0])} {f(ref_at[1])} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'    (property "Value" {q(value)} (at {f(val_at[0])} {f(val_at[1])} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'    (property "Footprint" {q(fp)} (at 0 0 0) {FONT_HIDE})\n'
        f'    (property "Datasheet" "" (at 0 0 0) {FONT_HIDE})\n'
        f'    (property "Description" {q(desc)} (at 0 0 0) {FONT_HIDE})\n'
    )


def _pin(num, name, x, y, ang, hide_name=False, length=PITCH):
    nm = "(effects (font (size 1.016 1.016)))"
    return (f'      (pin passive line (at {f(x)} {f(y)} {ang}) (length {f(length)}) '
            f'(name {q(name)} {nm}) (number {q(num)} {nm}))\n')


TWO_GFX = {
    # body drawn between x = -2.54 .. 2.54 on y = 0
    "R": '(rectangle (start -2.54 -1.016) (end 2.54 1.016) (stroke (width 0.254) (type default)) (fill (type none)))',
    "FB": '(rectangle (start -2.54 -1.016) (end 2.54 1.016) (stroke (width 0.254) (type default)) (fill (type outline)))',
    "F": '(rectangle (start -2.54 -1.016) (end 2.54 1.016) (stroke (width 0.254) (type default)) (fill (type none))) '
         '(polyline (pts (xy -2.54 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))',
    "C": '(polyline (pts (xy -0.508 -1.778) (xy -0.508 1.778)) (stroke (width 0.3048) (type default)) (fill (type none))) '
         '(polyline (pts (xy 0.508 -1.778) (xy 0.508 1.778)) (stroke (width 0.3048) (type default)) (fill (type none))) '
         '(polyline (pts (xy -2.54 0) (xy -0.508 0)) (stroke (width 0) (type default)) (fill (type none))) '
         '(polyline (pts (xy 0.508 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))',
    "L": '(arc (start -2.54 0) (mid -1.905 0.635) (end -1.27 0) (stroke (width 0.254) (type default)) (fill (type none))) '
         '(arc (start -1.27 0) (mid -0.635 0.635) (end 0 0) (stroke (width 0.254) (type default)) (fill (type none))) '
         '(arc (start 0 0) (mid 0.635 0.635) (end 1.27 0) (stroke (width 0.254) (type default)) (fill (type none))) '
         '(arc (start 1.27 0) (mid 1.905 0.635) (end 2.54 0) (stroke (width 0.254) (type default)) (fill (type none)))',
    "diode": '(polyline (pts (xy -1.27 1.27) (xy -1.27 -1.27) (xy 1.27 0) (xy -1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none))) '
             '(polyline (pts (xy 1.27 1.27) (xy 1.27 -1.27)) (stroke (width 0.254) (type default)) (fill (type none))) '
             '(polyline (pts (xy -2.54 0) (xy -1.27 0)) (stroke (width 0) (type default)) (fill (type none))) '
             '(polyline (pts (xy 1.27 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))',
    "tvs": '(polyline (pts (xy -1.27 1.016) (xy -1.27 -1.016) (xy 0 0) (xy -1.27 1.016)) (stroke (width 0.254) (type default)) (fill (type none))) '
           '(polyline (pts (xy 1.27 1.016) (xy 1.27 -1.016) (xy 0 0) (xy 1.27 1.016)) (stroke (width 0.254) (type default)) (fill (type none))) '
           '(polyline (pts (xy 0 1.27) (xy 0 -1.27)) (stroke (width 0.254) (type default)) (fill (type none))) '
           '(polyline (pts (xy -2.54 0) (xy -1.27 0)) (stroke (width 0) (type default)) (fill (type none))) '
           '(polyline (pts (xy 1.27 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))',
    "sw": '(circle (center -1.524 0) (radius 0.381) (stroke (width 0.254) (type default)) (fill (type none))) '
          '(circle (center 1.524 0) (radius 0.381) (stroke (width 0.254) (type default)) (fill (type none))) '
          '(polyline (pts (xy -1.905 1.016) (xy 1.905 1.016)) (stroke (width 0.254) (type default)) (fill (type none))) '
          '(polyline (pts (xy -2.54 0) (xy -1.905 0)) (stroke (width 0) (type default)) (fill (type none))) '
          '(polyline (pts (xy 1.905 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))',
    "xtal": '(rectangle (start -0.762 -1.524) (end 0.762 1.524) (stroke (width 0.254) (type default)) (fill (type none))) '
            '(polyline (pts (xy -1.524 -1.27) (xy -1.524 1.27)) (stroke (width 0.3048) (type default)) (fill (type none))) '
            '(polyline (pts (xy 1.524 -1.27) (xy 1.524 1.27)) (stroke (width 0.3048) (type default)) (fill (type none))) '
            '(polyline (pts (xy -2.54 0) (xy -1.524 0)) (stroke (width 0) (type default)) (fill (type none))) '
            '(polyline (pts (xy 1.524 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none)))',
}
TWO_GFX["led"] = TWO_GFX["diode"] + (
    ' (polyline (pts (xy 0 1.778) (xy 1.016 2.794)) (stroke (width 0) (type default)) (fill (type none)))'
    ' (polyline (pts (xy 1.016 1.778) (xy 2.032 2.794)) (stroke (width 0) (type default)) (fill (type none)))')
TWO_GFX["r"] = TWO_GFX["F"]
REFPFX = {"R": "R", "C": "C", "L": "L", "FB": "FB", "F": "F"}


def two_symbol_key(c):
    """Library symbol name + (left pad number, right pad number) for a two-terminal part."""
    if c.kind in ("R", "C", "L", "FB", "F"):
        return c.kind, ("1", "2")
    style = PARTS[c.part]["two"]
    if "A" in c.pins:                      # polarised: anode left, cathode right
        a = cpmodel.pads_for(c, "A")[0]
        k = cpmodel.pads_for(c, "K")[0]
        return f"{style.upper()}_AK", (a, k)
    return style.upper(), ("1", "2")


def lib_two(name, gfx, nums, refpfx):
    s = f'  (symbol {q(name)} (pin_numbers hide) (pin_names (offset 0) hide) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
    s += _props(refpfx, name, "", "two-terminal part", (-2.54, 2.286), (0.635, 2.286))
    s += f'    (symbol {q(name + "_0_1")} {gfx})\n'
    s += f'    (symbol {q(name + "_1_1")}\n'
    s += _pin(nums[0], "1" if name[-3:] != "_AK" else "A", -5.08, 0, 0)
    s += _pin(nums[1], "2" if name[-3:] != "_AK" else "K", 5.08, 0, 180)
    s += "    )\n  )\n"
    return s


def lib_tp():
    s = '  (symbol "TP" (pin_numbers hide) (pin_names (offset 0) hide) (exclude_from_sim no) (in_bom no) (on_board yes)\n'
    s += _props("TP", "TP", "TestPoint:TestPoint_Pad_D1.0mm", "test pad", (1.27, 1.27), (1.27, -1.27))
    s += '    (symbol "TP_0_1" (circle (center 0.762 0) (radius 0.762) (stroke (width 0.254) (type default)) (fill (type none))))\n'
    s += '    (symbol "TP_1_1"\n' + _pin("1", "1", -2.54, 0, 0, length=2.54) + "    )\n  )\n"
    return s


class IcSym:
    """Rectangular multi-unit symbol; rows are (pad_number, pin_name)."""

    def __init__(self, name, refpfx, fp, desc, units):
        self.name, self.refpfx, self.fp, self.desc = name, refpfx, fp, desc
        self.units = units                         # list of [ (pad, name, pin_id), ... ]
        self.geom = []                             # per unit: dict(w, left[], right[], h)
        for rows in units:
            half = (len(rows) + 1) // 2
            left, right = rows[:half], rows[half:]
            wl = max([len(r[1]) for r in left] or [1])
            wr = max([len(r[1]) for r in right] or [1])
            w = snap(max(12.7, (wl + wr) * 0.9 + 6.0))
            w = w if (round(w / G) % 2 == 0) else w + G     # keep pin ends on the 2.54 grid
            self.geom.append(dict(w=w, left=left, right=right, h=max(len(left), len(right)) * PITCH + PITCH))

    def pin_xy(self, u, pin_id):
        """Connection point of a pin relative to the unit origin, schematic coords (+y down), and its side."""
        g = self.geom[u]
        for i, r in enumerate(g["left"]):
            if r[0] == pin_id:
                return -g["w"] / 2 - PITCH, (i + 1) * PITCH, "L"
        for i, r in enumerate(g["right"]):
            if r[0] == pin_id:
                return g["w"] / 2 + PITCH, (i + 1) * PITCH, "R"
        raise KeyError(pin_id)

    def lib(self):
        s = f'  (symbol {q(self.name)} (pin_names (offset 0.762)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
        s += _props(self.refpfx, self.name, self.fp, self.desc, (-self.geom[0]["w"] / 2, 1.905), (-self.geom[0]["w"] / 2 + 12.7, 1.905))
        for u, g in enumerate(self.geom, 1):
            w, h = g["w"], g["h"]
            s += (f'    (symbol {q(f"{self.name}_{u}_1")}\n'
                  f'      (rectangle (start {f(-w / 2)} 0) (end {f(w / 2)} {f(-h)}) (stroke (width 0.254) (type default)) (fill (type background)))\n')
            for i, r in enumerate(g["left"]):
                s += _pin(r[0], r[1], -w / 2 - PITCH, -(i + 1) * PITCH, 0)
            for i, r in enumerate(g["right"]):
                s += _pin(r[0], r[1], w / 2 + PITCH, -(i + 1) * PITCH, 180)
            s += "    )\n"
        s += "  )\n"
        return s


def build_ic_symbols(d):
    """One library symbol per IC part type; the big BGAs are split into units by sheet."""
    syms = {}          # part -> IcSym
    unit_of = {}       # (ref, sheet) -> [unit indexes]
    for c in d.comps.values():
        if c.kind != "ic":
            continue
        pd = PARTS[c.part]
        names = d.pin_names[c.ref]
        if c.part in syms and pd.get("pins"):
            unit_of[c.ref] = {c.sheet: [0]}
            continue

        def rows_for(pin_ids):
            rows = []
            for pid in pin_ids:
                pads = cpmodel.pads_for(c, pid)
                for k, pad in enumerate(pads):
                    nm = names.get(pid, pid)
                    rows.append((pad, nm if len(pads) == 1 else f"{nm}.{k + 1}", pid))
            return rows

        units, umap = [], {}
        if pd.get("pins"):
            rows = rows_for([p for p, _ in pd["pins"]])
            for i in range(0, len(rows), 2 * MAXROWS):
                umap.setdefault(c.sheet, []).append(len(units))
                units.append(rows[i:i + 2 * MAXROWS])
        else:
            for sh in d.sheets:
                rows = rows_for([p for s, p in c.order if s == sh])
                for i in range(0, len(rows), 2 * MAXROWS):
                    umap.setdefault(sh, []).append(len(units))
                    units.append(rows[i:i + 2 * MAXROWS])
        refpfx = re.match(r"^\d?[A-Z]+", c.ref).group(0)
        syms[c.part] = IcSym(c.part, refpfx, c.fp, c.desc, units)
        unit_of[c.ref] = umap
    return syms, unit_of


# --------------------------------------------------------------------------
# sheet layout
# --------------------------------------------------------------------------
PAPERS = [("A3", 420.0, 297.0), ("A2", 594.0, 420.0), ("A1", 841.0, 594.0), ("A0", 1189.0, 841.0)]
MARGIN_L, MARGIN_T, MARGIN_R, MARGIN_B = 15.24, 30.48, 15.24, 30.48


def label_w(net):
    return len(net) * CHAR + 5.0


class Block:
    def __init__(self, kind, c, w, h, **kw):
        self.kind, self.c, self.w, self.h = kind, c, w, h
        self.__dict__.update(kw)
        self.x = self.y = 0.0


def layout(blocks, notes_h):
    """Column flow; returns the smallest paper on which everything fits."""
    for name, pw, ph in PAPERS:
        x, y = MARGIN_L, MARGIN_T + notes_h
        colw = 0.0
        ok = True
        top = MARGIN_T + notes_h
        def floor(cx, w):
            # columns that reach under the title block (bottom-right, 110 x 45 mm) stop above it
            return ph - (62.0 if cx + w > pw - 112.0 else MARGIN_B)

        for b in blocks:
            if b.h > ph - MARGIN_B - top:
                ok = False
                break
            if y + b.h > floor(x, max(colw, b.w)) and y > top:
                x += colw + 7.62
                y, colw = top, 0.0
            if x + b.w > pw - MARGIN_R or y + b.h > floor(x, b.w):
                ok = False
                break
            b.x, b.y = snap(x), snap(y)
            y += b.h
            colw = max(colw, b.w)
        if ok:
            return name, pw, ph
    raise RuntimeError("sheet does not fit on A0; split it")


def glabel(net, x, y, side, key):
    ang, just = (180, "right") if side == "L" else (0, "left")
    return (f'  (global_label {q(net)} (shape passive) (at {f(x)} {f(y)} {ang}) (fields_autoplaced yes)\n'
            f'    (effects (font (size 1.27 1.27)) (justify {just}))\n'
            f'    (uuid {q(uid("lbl", key))})\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at 0 0 0) {FONT_HIDE})\n  )\n')


def noconn(x, y, key):
    return f'  (no_connect (at {f(x)} {f(y)}) (uuid {q(uid("nc", key))}))\n'


def sym_inst(lib_id, x, y, unit, ref, value, fp, desc, dnp, pads, path, key, ref_at, val_at, in_bom=True,
             ref_just="left", val_just="left", val_hide=False):
    vh = " (hide yes)" if val_hide else ""
    s = (f'  (symbol (lib_id {q("commander:" + lib_id)}) (at {f(x)} {f(y)} 0) (unit {unit})\n'
         f'    (exclude_from_sim no) (in_bom {"yes" if in_bom else "no"}) (on_board yes) (dnp {"yes" if dnp else "no"})\n'
         f'    (uuid {q(uid("sym", key))})\n'
         f'    (property "Reference" {q(ref)} (at {f(ref_at[0])} {f(ref_at[1])} 0) (effects (font (size 1.27 1.27)) (justify {ref_just})))\n'
         f'    (property "Value" {q(value)} (at {f(val_at[0])} {f(val_at[1])} 0) (effects (font (size 1.27 1.27)) (justify {val_just}){vh}))\n'
         f'    (property "Footprint" {q(fp)} (at {f(x)} {f(y)} 0) {FONT_HIDE})\n'
         f'    (property "Datasheet" "" (at {f(x)} {f(y)} 0) {FONT_HIDE})\n'
         f'    (property "Description" {q(desc)} (at {f(x)} {f(y)} 0) {FONT_HIDE})\n')
    for p in pads:
        s += f'    (pin {q(p)} (uuid {q(uid("pin", key, p))}))\n'
    s += (f'    (instances (project {q(PROJECT)} (path {q(path)} (reference {q(ref)}) (unit {unit}))))\n'
          f'  )\n')
    return s


def sheet_notes(sheet):
    """The '#' comment header lines of the netlist file(s) that define this sheet -> on-sheet notes."""
    out = []
    for path in sorted(glob.glob(os.path.join(cpmodel.NETDIR, "*.net"))):
        txt = open(path, encoding="utf-8").read().splitlines()
        if not any(l.strip() == f"SHEET {sheet}" for l in txt):
            continue
        for l in txt:
            if l.startswith("SHEET"):
                break
            if l.startswith("#"):
                out.append(l[1:].strip())
    return out


def build_sheet(d, sheet, syms, unit_of, root_uuid, sheet_uuid, page, npages):
    path = f"/{root_uuid}/{sheet_uuid}"
    blocks = []
    for c, pins in d.sheet_comps(sheet):
        if c.kind == "ic":
            sym = syms[c.part]
            for u in unit_of[c.ref].get(sheet, []):
                g = sym.geom[u]
                lw = max([label_w(c.pins.get(r[2]) or "") for r in g["left"]] or [0])
                rw = max([label_w(c.pins.get(r[2]) or "") for r in g["right"]] or [0])
                blocks.append(Block("ic", c, snap(lw + g["w"] + 2 * PITCH + rw + 5.08), snap(g["h"] + 3 * PITCH), u=u, lw=snap(lw)))
        else:
            nets = list(c.pins.values())
            lw = label_w(nets[0] or "") if nets else 0
            rw = label_w(nets[1] or "") if len(nets) > 1 else 0
            blocks.append(Block("two", c, snap(lw + 10.16 + rw + 2.54), 3 * PITCH if c.kind != "TP" else 2 * PITCH, lw=snap(lw)))
    # ICs first (tallest first), then two-terminal parts in netlist order
    ics = sorted([b for b in blocks if b.kind == "ic"], key=lambda b: -b.h)
    twos = [b for b in blocks if b.kind == "two"]
    wmax = max([b.w for b in twos] or [0])
    for b in twos:
        b.w = wmax                                   # uniform column width for the passive grid
    notes = sheet_notes(sheet)
    notes_h = snap(len(notes) * 2.54 + 5.08) if notes else 0
    paper, pw, ph = layout(ics + twos, notes_h)

    body, libs_used = "", set()
    if notes:
        txt = "\\n".join(n.replace("\\", "\\\\").replace('"', "'") for n in notes)
        body += (f'  (text "{txt}" (exclude_from_sim no) (at {f(MARGIN_L)} {f(MARGIN_T - 5.08)} 0)\n'
                 f'    (effects (font (size 1.524 1.524)) (justify left top)) (uuid {q(uid("note", sheet))}))\n')
    for b in ics + twos:
        c = b.c
        if b.kind == "ic":
            sym = syms[c.part]
            g = sym.geom[b.u]
            ox = snap(b.x + b.lw + PITCH + g["w"] / 2)
            oy = snap(b.y + 2 * PITCH)
            libs_used.add(c.part)
            pads = [r[0] for uu in sym.units for r in uu]
            unit = b.u + 1
            # all units of one symbol must carry the same value, or KiCad reports annotation errors
            body += sym_inst(c.part, ox, oy, unit, c.ref, c.value, c.fp, c.desc, c.dnp, pads, path,
                             (c.ref, unit), (ox - g["w"] / 2, oy - 3.175), (ox - g["w"] / 2 + 10.16, oy - 3.175))
            for r in g["left"] + g["right"]:
                px, py, side = sym.pin_xy(b.u, r[0])
                net = c.pins.get(r[2])
                if net is None:
                    body += noconn(ox + px, oy + py, (c.ref, r[0]))
                else:
                    body += glabel(net, ox + px, oy + py, side, (c.ref, r[0]))
        else:
            ox = snap(b.x + b.lw + 5.08)
            oy = snap(b.y + 2 * PITCH)
            if c.kind == "TP":
                libs_used.add("TP")
                body += sym_inst("TP", ox, oy, 1, c.ref, "TP", c.fp, c.desc, False, ["1"], path, (c.ref, 1),
                                 (ox + 2.54, oy), (ox + 2.54, oy + 1.27), in_bom=False, val_hide=True)
                body += glabel(c.pins["1"], ox - 2.54, oy, "L", (c.ref, "1"))
                continue
            name, nums = two_symbol_key(c)
            libs_used.add(name)
            value = c.value if not c.dnp else "DNP"
            body += sym_inst(name, ox, oy, 1, c.ref, value, c.fp, c.desc or name, c.dnp, list(nums), path, (c.ref, 1),
                             (ox - 0.762, oy - 2.54), (ox + 0.762, oy - 2.54), ref_just="right")
            pin_ids = list(c.pins.keys())
            if "A" in c.pins:
                pin_ids = ["A", "K"]
            for pid, px, side in ((pin_ids[0], -5.08, "L"), (pin_ids[1], 5.08, "R")):
                net = c.pins[pid]
                if net is None:
                    body += noconn(ox + px, oy, (c.ref, pid))
                else:
                    body += glabel(net, ox + px, oy, side, (c.ref, pid))
    title = SHEET_TITLES.get(sheet, sheet)
    head = (f'(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")\n'
            f'  (uuid {q(sheet_uuid)})\n  (paper {q(paper)})\n'
            f'  (title_block (title {q("Commander mainboard - " + title)}) (rev "A0") (company "Coffee Pie / Grupo 3P1 Colombia")\n'
            f'    (comment 1 "Codec Terminal, model Commander: RK3566 + PoE PD + USB hubs on one PCB")\n'
            f'    (comment 2 "Generated from src/netlist - edit there and re-run tools/build.py")\n'
            f'    (comment 3 "CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum"))\n')
    return head, body, libs_used, paper


def main():
    d = cpmodel.load()
    if d.errors:
        for e in d.errors:
            print("ERROR", e)
        raise SystemExit(1)
    syms, unit_of = build_ic_symbols(d)

    # ---- library ----
    lib = {}
    for kind in ("R", "C", "L", "FB", "F"):
        lib[kind] = lib_two(kind, TWO_GFX[kind], ("1", "2"), REFPFX[kind])
    for c in d.comps.values():
        if c.kind == "two":
            name, nums = two_symbol_key(c)
            if name not in lib:
                style = PARTS[c.part]["two"]
                pfx = re.match(r"^\d?[A-Z]+", c.ref).group(0)
                lib[name] = lib_two(name, TWO_GFX[style], nums, pfx)
    lib["TP"] = lib_tp()
    for part, s in syms.items():
        lib[part] = s.lib()
    os.makedirs(os.path.join(ROOT, "lib"), exist_ok=True)
    with open(os.path.join(ROOT, "lib", "commander.kicad_sym"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write('(kicad_symbol_lib (version 20231120) (generator "kicad_symbol_editor") (generator_version "8.0")\n')
        for name in lib:
            fh.write(lib[name])
        fh.write(")\n")

    def embedded(names):
        out = "  (lib_symbols\n"
        for n in sorted(names):
            out += lib[n].replace(f'  (symbol {q(n)} ', f'  (symbol {q("commander:" + n)} ', 1).replace("\n  ", "\n    ")
        return out + "  )\n"

    # ---- sub-sheets ----
    root_uuid = uid("root")
    os.makedirs(os.path.join(ROOT, "sheets"), exist_ok=True)
    info = []
    for i, sheet in enumerate(d.sheets):
        su = uid("sheet", sheet)
        head, body, used, paper = build_sheet(d, sheet, syms, unit_of, root_uuid, su, i + 2, len(d.sheets) + 1)
        with open(os.path.join(ROOT, "sheets", f"{sheet}.kicad_sch"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(head + embedded(used) + body + ")\n")
        n = sum(1 for c, _ in d.sheet_comps(sheet))
        info.append((sheet, su, paper, n))
        print(f"  sheets/{sheet}.kicad_sch  {paper}  {n} parts")

    # ---- root ----
    s = (f'(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")\n'
         f'  (uuid {q(root_uuid)})\n  (paper "A3")\n'
         f'  (title_block (title "Commander mainboard - index") (rev "A0") (company "Coffee Pie / Grupo 3P1 Colombia")\n'
         f'    (comment 1 "Codec Terminal, model Commander: RK3566 + PoE PD + USB hubs on one PCB")\n'
         f'    (comment 2 "Reference design: Radxa ZERO 3E V1.2 (sheets marked NEW are Commander additions)")\n'
         f'    (comment 3 "CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum"))\n'
         f'  (lib_symbols)\n')
    s += ('  (text "COMMANDER MAINBOARD - rev A0 (for audit)\\n\\n'
          'Sheets 2-15 follow the Radxa ZERO 3E V1.2 schematic (component references kept so the two can be compared line by line).\\n'
          'Sheets marked NEW replace the PoE HAT, the single USB3 Type-C port and the 40-pin header.\\n'
          'All nets are joined by global labels: search a net name to find every pin on it."\n'
          '    (exclude_from_sim no) (at 20.32 22.86 0) (effects (font (size 2.032 2.032)) (justify left top)) '
          f'(uuid {q(uid("rootnote"))}))\n')
    x0, y0, w, h, cols = 20.32, 55.88, 86.36, 20.32, 4
    for i, (sheet, su, paper, n) in enumerate(info):
        x = x0 + (i % cols) * (w + 10.16)
        y = y0 + (i // cols) * (h + 15.24)
        s += (f'  (sheet (at {f(x)} {f(y)}) (size {f(w)} {f(h)}) (fields_autoplaced yes)\n'
              f'    (stroke (width 0.1524) (type solid)) (fill (color 255 255 220 1.0))\n'
              f'    (uuid {q(su)})\n'
              f'    (property "Sheetname" {q(sheet)} (at {f(x)} {f(y - 0.7)} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))\n'
              f'    (property "Sheetfile" {q("sheets/" + sheet + ".kicad_sch")} (at {f(x)} {f(y + h + 0.6)} 0) (effects (font (size 1.27 1.27)) (justify left top)))\n'
              f'    (instances (project {q(PROJECT)} (path {q("/" + root_uuid)} (page {q(str(i + 2))}))))\n'
              f'  )\n')
        label = SHEET_TITLES.get(sheet, sheet).replace('"', "'") + "\\n" + f"{n} parts, {paper}"
        s += (f'  (text "{label}" (exclude_from_sim no) '
              f'(at {f(x + 2.54)} {f(y + 5.08)} 0) (effects (font (size 1.27 1.27)) (justify left top)) (uuid {q(uid("st", sheet))}))\n')
    s += '  (sheet_instances (path "/" (page "1")))\n)\n'
    with open(os.path.join(ROOT, f"{PROJECT}.kicad_sch"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s)
    print(f"  {PROJECT}.kicad_sch  (root, {len(info)} sheets)")
    print(f"  lib/commander.kicad_sym  {len(lib)} symbols")


if __name__ == "__main__":
    main()
