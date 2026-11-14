#!/usr/bin/env python3
"""One-shot rebuild of the Commander mainboard project from src/netlist.

    python tools/build.py            (any Python 3.9+; KiCad 10 must be installed)

Set KICAD_BIN if KiCad is not in the default location.  Steps:
  1  regenerate the repetitive USB netlists, check the design model
  2  project file, custom footprints, symbol library, schematic sheets
  3  board (runs under KiCad's bundled Python: footprints, nets, first placement)
     then routing tranche 1 (tools/route.py; skip it with --no-route)
     (--keep-board skips both and only re-runs the checks and exports on the board that is on disk)
  4  ERC, netlist export, model / schematic / board cross-check, DRC
  5  exports into the repository layout:
        ../../schematics/                 schematic PDF
        ../../fabrication/bom/            preliminary BOM (CSV)
        ../../fabrication/position/       placement file (CSV) + assembly drawings (PDF)
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if "--variant" in sys.argv:                     # e.g.  build.py --variant strip_test  ->  ../commander_strip_test
    os.environ["CP_ROOT"] = os.path.normpath(os.path.join(HERE, "..", "..", "commander_" + sys.argv[sys.argv.index("--variant") + 1]))
sys.path.insert(0, HERE)
import cpmodel      # noqa: E402  (reads CP_ROOT)

ROOT = cpmodel.ROOT
COMMANDER = os.path.normpath(os.path.join(ROOT, "..", ".."))
KBIN = os.environ.get("KICAD_BIN", r"C:/Program Files/KiCad/10.0/bin")
EXE = ".exe" if os.name == "nt" else ""
KPY = os.path.join(KBIN, "python" + EXE)
KCLI = os.path.join(KBIN, "kicad-cli" + EXE)
PRJ = cpmodel.PRJ
REV = cpmodel.REV


FINDINGS = []           # checks that found something but must not stop the reports and exports that follow


def run(title, cmd, ok_codes=(0,), report_only=False):
    print(f"--- {title}", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode not in ok_codes:
        if report_only:
            FINDINGS.append(title)
            return
        raise SystemExit(f"FAILED ({r.returncode}): {title}")


def py(script, *args):
    return [sys.executable, os.path.join(HERE, script), *args]


def kpy(script, *args):
    return [KPY, os.path.join(HERE, script), *args]


def summarize(report):
    counts = {}
    with open(os.path.join(ROOT, report), encoding="utf-8") as f:
        for line in f:
            if line.startswith("["):
                k = line[1:line.index("]")]
                counts[k] = counts.get(k, 0) + 1
    return counts


def main():
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    for name, kind, what in (("sym-lib-table", "sym_lib_table", "lib/commander.kicad_sym"), ("fp-lib-table", "fp_lib_table", "lib/commander.pretty")):
        if not os.path.exists(os.path.join(ROOT, name)):
            with open(os.path.join(ROOT, name), "w", encoding="utf-8", newline="\n") as f:
                f.write('(%s\n  (version 7)\n  (lib (name "commander")(type "KiCad")(uri "${KIPRJMOD}/%s")(options "")(descr "Commander (generated)"))\n)\n' % (kind, what))
    if not os.path.exists(os.path.join(ROOT, ".gitignore")):
        with open(os.path.join(ROOT, ".gitignore"), "w", encoding="utf-8", newline="\n") as f:
            f.write("build/\n*-backups/\n*.kicad_prl\nfp-info-cache\n*.lck\n~*\n__pycache__/\n")
    for sub in ("schematics", os.path.join("fabrication", "bom"), os.path.join("fabrication", "position")):
        os.makedirs(os.path.join(COMMANDER, sub), exist_ok=True)

    sch_only = cpmodel.VARIANT in ("kbmcu", "hat")    # schematic only: a block for another PCB / a board not laid out yet
    if sch_only:
        run("design model check", py("cpmodel.py"))
        run("project file", py("gen_project.py"))
        run("symbols + schematic", py("gen_schematic.py"))
        run("ERC", [KCLI, "sch", "erc", "--format", "report", "--severity-all", "-o", "build/erc.rpt", PRJ + ".kicad_sch"], ok_codes=(0, 5))
        run("netlist export", [KCLI, "sch", "export", "netlist", "-o", "build/netlist.net", PRJ + ".kicad_sch"])
        run("schematic PDF", [KCLI, "sch", "export", "pdf", "-o", os.path.join(COMMANDER, "schematics", f"{PRJ}_{REV}_schematic.pdf"), PRJ + ".kicad_sch"])
        if cpmodel.VARIANT == "hat":
            run("BOM", py("gen_bom.py"))
        print("ERC:", summarize("build/erc.rpt") or "clean")
        return
    if cpmodel.VARIANT == "kbd":
        # The keyboard: its board is the Altium design converted to KiCad, with the Arduino Micro module replaced by
        # the parts of sheet kbd_mcu (tools/kbd_board.py).  --keep-board: only checks and exports.
        sch, pcb = PRJ + ".kicad_sch", PRJ + ".kicad_pcb"
        run("design model check", py("cpmodel.py"))
        run("project file", py("gen_project.py"))
        run("symbols + schematic", py("gen_schematic.py"))
        if "--keep-board" not in sys.argv:
            src = os.path.join(COMMANDER, "Teclado_V2", "Teclado_V2.PcbDoc")
            if os.path.exists(src):
                run("board: the Altium design converted to KiCad", kpy("kbd_board.py", "--stage", "import"))
            elif not os.path.exists(os.path.join(ROOT, "src", "altium_import.kicad_pcb")):
                raise SystemExit("neither the Altium source (%s) nor src/altium_import.kicad_pcb is there" % src)
            run("board: nets renamed, new parts placed, module removed", kpy("kbd_board.py", "--stage", "prepare"))
            run("board: the new parts connected (six passes in different orders, the best is kept: about half an hour)", kpy("kbd_board.py", "--stage", "route"))
            run("board: ground pads that the pours do not reach get a track or via", kpy("kbd_board.py", "--stage", "ground"))
        run("ERC", [KCLI, "sch", "erc", "--format", "report", "--severity-all", "-o", "build/erc.rpt", sch], ok_codes=(0, 5))
        run("netlist export", [KCLI, "sch", "export", "netlist", "-o", "build/netlist.net", sch])
        run("cross-check model / schematic / board", kpy("check_consistency.py", "build/netlist.net"), report_only=True)
        # (the pours are refilled by KiCad itself and saved: fills computed by the scripts can differ in detail)
        run("DRC", [KCLI, "pcb", "drc", "--refill-zones", "--save-board", "--format", "report", "--severity-all", "-o", "build/drc.rpt", pcb], ok_codes=(0, 5))
        run("DRC (json)", [KCLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", "build/drc.json", pcb], ok_codes=(0, 5))
        run("schematic PDF", [KCLI, "sch", "export", "pdf", "-o", os.path.join(COMMANDER, "schematics", f"{PRJ}_{REV}_schematic.pdf"), sch])
        pos = os.path.join(COMMANDER, "fabrication", "position")
        run("placement file", [KCLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                               "-o", os.path.join(pos, f"{PRJ}_{REV}_placement.csv"), pcb])
        run("assembly drawing, top", [KCLI, "pcb", "export", "pdf", "--mode-single",
                                      "--layers", "F.Cu,F.SilkS,F.Fab,Edge.Cuts", "-o", os.path.join(pos, f"{PRJ}_{REV}_top.pdf"), pcb])
        run("assembly drawing, bottom", [KCLI, "pcb", "export", "pdf", "--mode-single", "--mirror",
                                         "--layers", "B.Cu,B.SilkS,B.Fab,Edge.Cuts", "-o", os.path.join(pos, f"{PRJ}_{REV}_bottom.pdf"), pcb])
        run("BOM", py("gen_bom.py"))
        run("both boards in one view, for looking at only (pcb/commander_set)", kpy("make_set_view.py"), report_only=True)
        print()
        print("ERC:", summarize("build/erc.rpt") or "clean")
        print("DRC:", summarize("build/drc.rpt") or "clean")
        if FINDINGS:
            print("CHECKS WITH FINDINGS: " + "; ".join(FINDINGS))
            raise SystemExit(1)
        return
    run("USB bay netlists", py("gen_usb_netlists.py"))
    run("design model check", py("cpmodel.py"))
    run("project file", py("gen_project.py"))
    run("custom footprints", py("gen_footprints.py"))
    run("symbols + schematic", py("gen_schematic.py"))
    keep = "--keep-board" in sys.argv           # reuse the board on disk (already placed and routed)
    if not keep:
        # Place and route on a staging copy in build/, and swap it in only when it is finished: the board
        # someone has open in KiCad keeps showing the last complete version until then.
        stage = os.path.join(ROOT, "build", PRJ + ".kicad_pcb")
        shutil.copyfile(os.path.join(ROOT, PRJ + ".kicad_pro"), os.path.join(ROOT, "build", PRJ + ".kicad_pro"))
        os.environ["CP_PCB"] = stage
        run("board", kpy("gen_pcb.py"))
        if "--no-route" not in sys.argv:
            run("routing: strip / front / PoE, links to the column, BGA escapes, supply nets, column (about an hour)", kpy("route.py"))
        del os.environ["CP_PCB"]
        os.replace(stage, os.path.join(ROOT, PRJ + ".kicad_pcb"))

    sch, pcb = PRJ + ".kicad_sch", PRJ + ".kicad_pcb"
    run("ERC", [KCLI, "sch", "erc", "--format", "report", "--severity-all", "-o", "build/erc.rpt", sch], ok_codes=(0, 5))
    run("netlist export", [KCLI, "sch", "export", "netlist", "-o", "build/netlist.net", sch])
    run("cross-check model / schematic / board", kpy("check_consistency.py", "build/netlist.net"))
    run("DRC", [KCLI, "pcb", "drc", "--format", "report", "--severity-all", "-o", "build/drc.rpt", pcb], ok_codes=(0, 5))
    run("placement collision report", kpy("report_overlaps.py"))
    if "--no-route" not in sys.argv:
        run("DRC (json)", [KCLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", "build/drc.json", pcb], ok_codes=(0, 5))
        run("routing check", py("check_routing.py"), report_only=True)
        run("what is still open, by area and class (build/open_report.txt)", kpy("report_open.py"))
        run("USB links, net by net (build/usb_report.txt)", kpy("report_usb.py"))
    run("isolation check (PoE primary to everything else)", kpy("check_isolation.py"), report_only=True)
    run("chip clearance check (nothing under or through a big chip)", kpy("check_chips.py"), report_only=True)
    run("height report (nothing on the top face taller than the bay connectors)", kpy("report_heights.py"))

    out_sch = os.path.join(COMMANDER, "schematics", f"{PRJ}_{REV}_schematic.pdf")
    run("schematic PDF", [KCLI, "sch", "export", "pdf", "-o", out_sch, sch])
    pos = os.path.join(COMMANDER, "fabrication", "position")
    run("placement file", [KCLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                           "-o", os.path.join(pos, f"{PRJ}_{REV}_placement.csv"), pcb])
    run("assembly drawing, top", [KCLI, "pcb", "export", "pdf", "--mode-single",
                                  "--layers", "F.Cu,F.SilkS,F.Fab,F.CrtYd,Edge.Cuts,Dwgs.User,Cmts.User",
                                  "-o", os.path.join(pos, f"{PRJ}_{REV}_top.pdf"), pcb])
    run("assembly drawing, bottom", [KCLI, "pcb", "export", "pdf", "--mode-single",
                                     "--layers", "B.Cu,B.SilkS,B.Fab,B.CrtYd,Edge.Cuts,Dwgs.User",
                                     "-o", os.path.join(pos, f"{PRJ}_{REV}_bottom.pdf"), pcb])
    run("BOM", py("gen_bom.py"))

    print()
    print("ERC:", summarize("build/erc.rpt") or "clean")
    print("DRC:", summarize("build/drc.rpt"))
    print("placement:", open(os.path.join(ROOT, "build", "placement_report.txt"), encoding="utf-8").read().split("PARKED")[0].strip().replace("\n", " | "))
    if FINDINGS:
        print()
        print("CHECKS WITH FINDINGS (see the output above and build/routing_report.txt): " + "; ".join(FINDINGS))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
