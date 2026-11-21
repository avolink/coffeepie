#!/usr/bin/env python3
"""Quotation package for a fabricator / assembler (JLCPCB, PCBWay, ...).

    python tools/make_quote_package.py [--variant strip_test]

Writes, under commander/fabrication/:
    gerber/<project>_<rev>_QUOTE-ONLY/      Gerbers + Excellon drill files, and the same as a .zip
    bom/<project>_<rev>_bom_jlc.csv         parts list in the Comment / Designator / Footprint / LCSC layout
    position/<project>_<rev>_cpl_jlc.csv    placement in the Designator / Mid X / Mid Y / Layer / Rotation layout
    gerber/<project>_<rev>_QUOTE-ONLY/READ_ME_FIRST.txt

The files describe the board as it is today.  They are good for a PRICE: board size, layer count, finest
features, number and kind of parts.  They are NOT good for manufacture while the routing is incomplete, and
the package says so in its name and in its read-me.
"""
import csv
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if "--variant" in sys.argv:
    os.environ["CP_ROOT"] = os.path.normpath(os.path.join(HERE, "..", "..", "commander_" + sys.argv[sys.argv.index("--variant") + 1]))
sys.path.insert(0, HERE)
import cpmodel      # noqa: E402

ROOT, PRJ, REV = cpmodel.ROOT, cpmodel.PRJ, cpmodel.REV
COMMANDER = os.path.normpath(os.path.join(ROOT, "..", ".."))
KBIN = os.environ.get("KICAD_BIN", r"C:/Program Files/KiCad/10.0/bin")
KCLI = os.path.join(KBIN, "kicad-cli" + (".exe" if os.name == "nt" else ""))
NL = chr(10)
COPPER = {2: "F.Cu / B.Cu",
          4: "F.Cu sig / In1 GND / In2 5 V / B.Cu sig",
          6: "F.Cu sig / In1 GND / In2 sig / In3 power / In4 GND / B.Cu sig",
          8: "F.Cu sig / In1 GND / In2 sig / In3 power / In4 GND / In5 sig / In6 GND / B.Cu sig"}


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("FAILED: " + " ".join(cmd) + NL + r.stdout[-800:] + r.stderr[-800:])


def jlc_package(fp):
    """KiCad footprint name -> what JLC's BOM matcher understands.  'C_0402_1005Metric' is read by it as the imperial
    01005 (it takes '1005' for the size), so chip parts get their imperial code alone ('0402'); others stay as they are."""
    m = re.match(r"^(?:C|R|L|D|LED|Fuse|FB)_(\d{4})_\d{4}Metric", fp)
    if m:
        return m.group(1)
    if fp.startswith("Res "):                   # (the keyboard's Altium names: "Res 0805")
        return fp.split()[-1]
    return fp


def board_facts(txt):
    """(thickness mm, outline width, outline height) read from the board file: no pcbnew needed.  Only the board's
    own Edge.Cuts drawings count (an outline drawn inside a footprint, like the hub's card tongue, does not)."""
    import re
    m = re.search(r"\(thickness ([0-9.]+)\)", txt)
    xs, ys = [], []
    for item in txt.split(NL + "\t("):          # top-level items only
        if not item.startswith(("gr_line", "gr_arc", "gr_rect")) or '(layer "Edge.Cuts")' not in item:
            continue
        for p in re.finditer(r"\((?:start|mid|end) ([-0-9.]+) ([-0-9.]+)\)", item):
            xs.append(float(p.group(1)))
            ys.append(float(p.group(2)))
    return (float(m.group(1)) if m else None), (max(xs) - min(xs) if xs else 0), (max(ys) - min(ys) if ys else 0)


def main():
    pcb = PRJ + ".kicad_pcb"
    txt = open(os.path.join(ROOT, pcb), encoding="utf-8").read()
    thick, out_w, out_h = board_facts(txt)
    hub = cpmodel.VARIANT == "hub"
    kbd = cpmodel.VARIANT == "kbd"
    layers = 2 + len(set(re.findall(r'"In(\d+)\.Cu" (?:signal|power|mixed|jumper)', txt)))   # as the board file has them
    cu = ["F.Cu"] + [f"In{i}.Cu" for i in range(1, layers - 1)] + ["B.Cu"]
    kbd_open = kbd_drc = None
    if kbd:                                     # complete or not: read from what the build left behind
        import json
        try:
            kbd_open = json.load(open(os.path.join(ROOT, "build", "kbd_route.json"), encoding="utf-8"))["after"]
            d = json.load(open(os.path.join(ROOT, "build", "drc.json"), encoding="utf-8"))
            kbd_drc = (len(d.get("violations", [])), len(d.get("unconnected_items", [])))
        except (OSError, ValueError, KeyError):
            pass
    if kbd_drc is not None:
        kbd_open = kbd_drc[1]                   # KiCad's own count (DRC on the board as saved) is the one that counts
    ready = kbd and kbd_open == 0 and kbd_drc is not None and kbd_drc[1] == 0
    out = os.path.join(COMMANDER, "fabrication", "gerber", f"{PRJ}_{REV}" + ("_PROTOTYPE" if ready else "_QUOTE-ONLY"))
    for stale in ("_PROTOTYPE", "_QUOTE-ONLY"):
        if kbd:
            shutil.rmtree(os.path.join(COMMANDER, "fabrication", "gerber", f"{PRJ}_{REV}" + stale), ignore_errors=True)
            if os.path.exists(os.path.join(COMMANDER, "fabrication", "gerber", f"{PRJ}_{REV}" + stale + ".zip")):
                os.remove(os.path.join(COMMANDER, "fabrication", "gerber", f"{PRJ}_{REV}" + stale + ".zip"))
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    run([KCLI, "pcb", "export", "gerbers", "-o", out, "--layers",
         ",".join(cu + ["F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS", "Edge.Cuts"]),
         "--subtract-soldermask", "--no-x2", pcb])
    run([KCLI, "pcb", "export", "drill", "-o", out + os.sep, "--format", "excellon", "--excellon-units", "mm",
         "--excellon-separate-th", "--drill-origin", "absolute", pcb])

    # ---- parts list, placement ----
    bom_in = os.path.join(COMMANDER, "fabrication", "bom", f"{PRJ}_{REV}_bom.csv")
    bom_out = os.path.join(COMMANDER, "fabrication", "bom", f"{PRJ}_{REV}_bom_jlc.csv")
    lines = parts = 0
    with open(bom_in, encoding="utf-8", newline="") as f, open(bom_out, "w", encoding="utf-8", newline="") as g:
        w = csv.writer(g)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Description"])
        for row in csv.DictReader(f):
            if (row.get("populate") or "").strip().upper() == "DNP":
                continue
            refs = row["references"].split()
            w.writerow([row["value"], ",".join(refs), jlc_package(row["footprint"]), row.get("lcsc", ""), row.get("description", "")])
            lines += 1
            parts += len(refs)
    pos_in = os.path.join(COMMANDER, "fabrication", "position", f"{PRJ}_{REV}_placement.csv")
    cpl_out = os.path.join(COMMANDER, "fabrication", "position", f"{PRJ}_{REV}_cpl_jlc.csv")
    top = bottom = 0
    with open(pos_in, encoding="utf-8", newline="") as f, open(cpl_out, "w", encoding="utf-8", newline="") as g:
        w = csv.writer(g)
        w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
        for row in csv.DictReader(f):
            side = "bottom" if row["Side"].lower().startswith("b") else "top"
            top, bottom = top + (side == "top"), bottom + (side == "bottom")
            w.writerow([row["Ref"], row["Val"], row["Package"], row["PosX"] + "mm", row["PosY"] + "mm", row["Rot"], side])

    tracks = txt.count("(segment")
    # what is still open: the summary block of tools/report_open.py, if the build wrote one
    rep_path = os.path.join(ROOT, "build", "open_report.txt")
    still_open = "  (run tools/build.py for the list of open connections)"
    if os.path.exists(rep_path):
        head = open(rep_path, encoding="utf-8").read().split("nets:")[0].strip().splitlines()
        still_open = NL.join("  " + ln for ln in head)
    main_only = "" if cpmodel.VARIANT in ("strip", "hub") else """  - the memory bus (RK3566 to LPDDR4) is NOT routed: it needs the chip vendor's length-matched layout
  - the Ethernet head (RJ45, magnetics, PHY) is NOT routed: its isolation boundary has to be drawn by a person
"""
    if hub:
        outline = (f"a strip, {out_w:.1f} x {out_h:.1f} mm, plus an M.2 card tongue (19.85 mm wide, 4 mm long, Key M\n"
                   "                    notch) on its left end; milled")
        extra = """  card edge         M.2 Key M gold fingers on the left end: ENIG (hard gold if offered), fingers bevelled
                    20 deg, no copper or solder mask in the key notch - the card plugs into an M.2 socket
"""
    elif cpmodel.VARIANT == "strip":
        outline = f"a strip, about {out_w:.1f} x {out_h:.1f} mm, milled"
        extra = ""
    else:
        outline = (f"a column, about {out_w:.1f} x {out_h:.1f} mm (rounded corners), milled, with a small tab under\n"
                   "                    the M.2 socket; one RJ45 notch")
        extra = ""
    finest = ("USB5744 / USB2517 QFN (0.4 / 0.5 mm), 0.5 mm-pitch Type-C muxes, nine USB-C receptacles"
              if hub else "FCCSP-565 with 0.40 mm ball pitch, BGA-200 (0.65 x 0.8 mm), BGA-153 (0.5 mm), QFN 0.35 mm")
    readme = f"""{PRJ} {REV} - QUOTATION PACKAGE - NOT FOR MANUFACTURE

These files are for getting a PRICE. Do not let a fabricator build from them: the routing is not finished.

Board
  layers            {layers}, {thick if thick else "?"} mm, FR-4
  outline           {outline}
  copper            {COPPER[layers]}
  what to quote     smallest track / gap 0.09 / 0.09 mm, smallest via 0.25 mm pad / 0.15 mm hole,
                    {"impedance-controlled stack-up (USB 3 pairs)" if hub else "via-in-pad (filled, capped) under the 0.4 mm-pitch BGA, impedance-controlled stack-up"}
                    (the fine features are used under the {"QFN hubs" if hub else "BGA packages"} only; elsewhere tracks are 0.10 mm or
                    wider and vias 0.45 / 0.20 mm or larger)
{extra}Assembly
  parts placed      {parts} on {lines} BOM lines, both sides ({top} top, {bottom} bottom) - including DNP positions in the CPL
  finest packages   {finest}
  not in the BOM    manufacturer part numbers / LCSC numbers: values and packages only, so the assembler's
                    price for parts is an estimate until they are filled in
Files
  *.gbr / *.g*      copper, solder mask, paste, silkscreen, outline
  *.drl             plated and non-plated holes, millimetres, absolute origin
  ../../bom/{PRJ}_{REV}_bom_jlc.csv          parts list
  ../../position/{PRJ}_{REV}_cpl_jlc.csv     placement (rotations follow KiCad; JLCPCB will want some corrected)

Known not to be finished (see pcb/commander_mainboard/DESIGN_NOTES.md, section 0)
{main_only}  - routed by script, not reviewed by a layout engineer: differential pairs are coupled but neither
    impedance-verified nor length-tuned
  - {tracks} track segments are in the file; connections still open:
{still_open}
"""
    if kbd:
        state = ("every connection is made (KiCad: 0 unconnected); design-rule check: %d remarks, listed in "
                 "pcb/commander_keyboard/README.md" % kbd_drc[0]) if ready else (
                 "NOT complete: %s connections are still open - do not build from these files" % ("?" if kbd_open is None else kbd_open))
        readme = f"""{PRJ} {REV} - {"PROTOTYPE PACKAGE" if ready else "QUOTATION PACKAGE - NOT FOR MANUFACTURE"}

The keyboard of the Commander terminal: the prototyped Altium design (Teclado_V2), converted to KiCad, with the
Arduino Micro module replaced by an ATmega32U4 circuit soldered on the board.

State
  {state}
  the new copper was drawn by script and has not been reviewed by a layout engineer; the copper of the proven
  prototype (switch matrix, zones) is unchanged

Board
  layers            2, FR-4, 1 oz
  thickness         1.6 mm ASSUMED (the Altium file carries only its default stack-up) - confirm before ordering
  outline           about 315.1 x 135.0 mm, milled; 84 round switch holes and 104 slots / cut-outs inside
  finest features   track / gap 0.15 / 0.15 mm; vias 0.5 mm pad / 0.3 mm hole beside the QFN (elsewhere 0.6 / 0.3
                    and larger) - within the ordinary 2-layer service of JLCPCB / PCBWay
Assembly
  parts placed      {parts} on {lines} BOM lines: {top} on the top face (as in the prototype), {bottom} on the bottom face
                    (the ATmega32U4 circuit, where the Arduino module used to be) - so both faces are assembled
  finest package    QFN-44, 0.5 mm pitch (ATmega32U4-MU); USB-C receptacle, 16 pins
  to confirm        the 84 key positions T1..T84 are in the parts list and the placement file exactly as the Altium
                    design has them (one six-pad part each): tell the assembler whether that is a part they solder
                    or the plug-in switch that is fitted afterwards, as on the prototype
  not in the BOM    manufacturer / LCSC part numbers: values and packages only
  after assembly    the ATmega32U4 is delivered without the Arduino bootloader: it has to be programmed once through
                    the six ISP pads on the bottom face (see the README)
Files
  *.gbr / *.g*      copper, solder mask, paste, silkscreen, outline
  *.drl             plated and non-plated holes, millimetres, absolute origin
  ../../bom/{PRJ}_{REV}_bom_jlc.csv          parts list
  ../../position/{PRJ}_{REV}_cpl_jlc.csv     placement (rotations follow KiCad; JLCPCB will want some corrected)
"""
    open(os.path.join(out, "READ_ME_FIRST.txt"), "w", encoding="utf-8", newline=NL).write(readme)
    zpath = out + ".zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(out)):
            z.write(os.path.join(out, name), name)
    print(f"gerbers + drill : {out}  ({len(os.listdir(out))} files)")
    print(f"zip             : {zpath}  ({os.path.getsize(zpath) // 1024} kB)")
    print(f"parts list      : {bom_out}  ({lines} lines, {parts} parts)")
    print(f"placement       : {cpl_out}  ({top} top, {bottom} bottom)")


if __name__ == "__main__":
    main()
