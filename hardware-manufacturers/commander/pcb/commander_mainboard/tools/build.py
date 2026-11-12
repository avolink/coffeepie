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
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
COMMANDER = os.path.normpath(os.path.join(ROOT, "..", ".."))
KBIN = os.environ.get("KICAD_BIN", r"C:/Program Files/KiCad/10.0/bin")
EXE = ".exe" if os.name == "nt" else ""
KPY = os.path.join(KBIN, "python" + EXE)
KCLI = os.path.join(KBIN, "kicad-cli" + EXE)
PRJ = "commander_mainboard"
REV = "revA1"


def run(title, cmd, ok_codes=(0,)):
    print(f"--- {title}")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode not in ok_codes:
        raise SystemExit(f"FAILED ({r.returncode}): {title}")


def py(script, *args):
    return [sys.executable, os.path.join("tools", script), *args]


def kpy(script, *args):
    return [KPY, os.path.join("tools", script), *args]


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
    for sub in ("schematics", os.path.join("fabrication", "bom"), os.path.join("fabrication", "position")):
        os.makedirs(os.path.join(COMMANDER, sub), exist_ok=True)

    run("USB bay netlists", py("gen_usb_netlists.py"))
    run("design model check", py("cpmodel.py"))
    run("project file", py("gen_project.py"))
    run("custom footprints", py("gen_footprints.py"))
    run("symbols + schematic", py("gen_schematic.py"))
    keep = "--keep-board" in sys.argv           # reuse the board on disk (already placed and routed)
    if not keep:
        run("board", kpy("gen_pcb.py"))
    if not keep and "--no-route" not in sys.argv:
        run("routing, tranche 1 (several minutes)", kpy("route.py"))

    sch, pcb = PRJ + ".kicad_sch", PRJ + ".kicad_pcb"
    run("ERC", [KCLI, "sch", "erc", "--format", "report", "--severity-all", "-o", "build/erc.rpt", sch], ok_codes=(0, 5))
    run("netlist export", [KCLI, "sch", "export", "netlist", "-o", "build/netlist.net", sch])
    run("cross-check model / schematic / board", kpy("check_consistency.py", "build/netlist.net"))
    run("DRC", [KCLI, "pcb", "drc", "--format", "report", "--severity-all", "-o", "build/drc.rpt", pcb], ok_codes=(0, 5))
    run("placement collision report", kpy("report_overlaps.py"))
    if "--no-route" not in sys.argv:
        run("DRC (json)", [KCLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", "build/drc.json", pcb], ok_codes=(0, 5))
        run("routing check", py("check_routing.py"))
    run("isolation check (PoE primary to everything else)", kpy("check_isolation.py"))

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


if __name__ == "__main__":
    main()
