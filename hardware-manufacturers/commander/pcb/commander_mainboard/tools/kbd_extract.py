#!/usr/bin/env python
"""Keyboard: reads the board that KiCad imported from the Altium design (Teclado_V2.PcbDoc) and writes

    src/netlist/02_kbd_common.net, 03_kbd_row1.net ... 08_kbd_row6.net     the key matrix as netlist source
    src/altium_net_map.json                                                 Altium net name -> net name used here
    src/keymap.csv                                                          which key sits on which row / column
    lib/commander.pretty/*.kicad_mod                                        the footprint the Altium board brought along

Run with the Python that comes with KiCad:
    kbd_extract.py <imported board.kicad_pcb>       (CP_ROOT = the commander_keyboard project)

The nets that went to a pin of the Arduino Micro module (U1 in the Altium design) take the ARDUINO pin name, so the
firmware written for the module runs unchanged on the ATmega32U4 that replaces it.
"""
import json
import os
import sys

import pcbnew
from pcbnew import ToMM

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpmodel                                  # noqa: E402

NL = chr(10)
# pin of the Arduino Micro footprint (A000053) -> Arduino pin name; checked against the pin names in Teclado_V2.SchDoc
ARDUINO = {1: "MOSI", 2: "SS_RXLED", 3: "D1_TX", 4: "D0_RX", 5: "RESET_N", 6: "GND", 7: "D2_SDA", 8: "D3_SCL", 9: "D4", 10: "D5",
           11: "D6", 12: "D7", 13: "D8", 14: "D9", 15: "D10", 16: "D11", 17: "D12", 18: "D13", 19: "ARD_3V3", 20: "AREF",
           21: "A0", 22: "A1", 23: "A2", 24: "A3", 25: "A4", 26: "A5", 29: "VCC5", 30: "RESET_N", 31: "GND", 32: "ARD_VIN",
           33: "MISO", 34: "SCK"}
ROWS = ["A0", "A1", "A2", "A3", "A4", "A5"]
COLUMN_PINS = (34, 33, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 2, 1)
VALUE = {"500": "500R_0805", "560": "560R_0805", "10k": "10K_0805", "1k": "1K_0805"}


def net_map(board):
    """Altium net name -> net name used in this project.  Asserts that every net of the board gets one."""
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def pad(ref, num):
        return next(p.GetNetname() for p in fps[ref].Pads() if p.GetNumber() == num)
    m = {"GND": "GND", "+5": "VCC5"}
    for p in fps["U1"].Pads():
        if p.GetNumber() and p.GetNetname():
            name = ARDUINO[int(p.GetNumber())]
            assert m.setdefault(p.GetNetname(), name) == name, (p.GetNumber(), p.GetNetname(), name)
    m[pad("J1", "1")] = "LED_EN"
    m[pad("Q1", "1")] = "LED_B"
    m[pad("Q1", "3")] = "LED_K"
    for t in fps:
        if t[0] == "T" and t[1:].isdigit():
            m[pad(t, "1")] = t + "_E"
            m[pad(t, "3")] = t + "_A"
    left = [str(n) for n in board.GetNetsByName().keys() if str(n) and str(n) not in m]
    assert not left, "Altium nets without a name here: %s" % left
    return m


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def pad(ref, num):
        return next(p.GetNetname() for p in fps[ref].Pads() if p.GetNumber() == num)
    m = net_map(board)
    keys = sorted((r for r in fps if r[0] == "T" and r[1:].isdigit()), key=lambda r: int(r[1:]))
    cols = [m[pad("U1", str(k))] for k in COLUMN_PINS]

    # which resistor belongs to which key: the one on its emitter net (to the row) and the one on its LED anode net
    res = sorted((r for r in fps if r[0] == "R" and r[1:].isdigit()), key=lambda r: int(r[1:]))
    by_net = {}
    for r in res:
        for p in fps[r].Pads():
            by_net.setdefault(p.GetNetname(), []).append(r)
    rows = {a: [] for a in ROWS}
    problems = []
    used = set()
    info = {}
    for t in keys:
        re_, ra_ = by_net.get(pad(t, "1"), []), by_net.get(pad(t, "3"), [])
        if len(re_) != 1 or len(ra_) != 1:
            problems.append("%s: expected one resistor on each of pads 1 and 3" % t)
            continue
        re_, ra_ = re_[0], ra_[0]
        row = [m[p.GetNetname()] for p in fps[re_].Pads() if m[p.GetNetname()] != t + "_E"][0]
        col = m[pad(t, "2")]
        if row not in rows or col not in cols:
            problems.append("%s: row %s / column %s is not a matrix line" % (t, row, col))
            continue
        if [m[pad(t, k)] for k in ("4", "5", "6")] != ["GND", "GND", "LED_K"]:
            problems.append("%s: pads 4, 5, 6 are not GND, GND, LED cathode" % t)
        if "VCC5" not in [m[p.GetNetname()] for p in fps[ra_].Pads()]:
            problems.append("%s: its LED resistor %s does not go to +5 V" % (t, ra_))
        rows[row].append(t)
        used |= {re_, ra_}
        info[t] = (re_, ra_, row, col, ToMM(fps[t].GetPosition().x), ToMM(fps[t].GetPosition().y))

    def two(r):
        ps = sorted(fps[r].Pads(), key=lambda p: p.GetNumber())
        return "%s %s %s %s" % (r, VALUE[fps[r].GetValue()], m[ps[0].GetNetname()], m[ps[1].GetNetname()])
    out = os.path.join(cpmodel.ROOT, "src", "netlist")
    os.makedirs(out, exist_ok=True)
    head = NL.join([
        "# GENERATED by tools/kbd_extract.py from the Altium design Teclado_V2 (board file) - do not edit by hand.",
        "# Each key is an optical switch: an infra-red LED and a phototransistor.",
        "#   LED            : +5 V - 560 ohm - LED - LED_K (switched to ground by Q1)",
        "#   phototransistor: collector on a COLUMN (10 k pull-up, read by the MCU),",
        "#                    emitter through 500 ohm on a ROW (driven low by the MCU to scan that row)",
        "# Rows and columns carry the name of the Arduino pin they go to.", ""])
    for k, a in enumerate(ROWS, 1):
        lines = [head, "SHEET kbd_row%d" % k, ""]
        for t in sorted(rows[a], key=lambda t_: info[t_][4]):
            re_, ra_, row, col = info[t][:4]
            lines += ["%s KEYSW_OPT 1=%s_E 2=%s 3=%s_A 4=GND 5=GND 6=LED_K" % (t, t, col, t), two(re_), two(ra_)]
        open(os.path.join(out, "%02d_kbd_row%d.net" % (k + 2, k)), "w", encoding="utf-8", newline=NL).write(NL.join(lines) + NL)
    rest = [r for r in res if r not in used]
    lines = ["# GENERATED by tools/kbd_extract.py from the Altium design Teclado_V2 - do not edit by hand.",
             "# Column pull-ups, and the transistor that switches the infra-red LEDs of all keys (driven by Arduino pin D0",
             "# through the jumper J1).", "SHEET kbd_common", ""]
    lines += [two(r) for r in rest]
    lines += ["Q1 NPN_BEC:MMBT2222A B=%s E=%s C=%s" % tuple(m[pad("Q1", k)] for k in ("1", "2", "3")),
              "J1 JUMPER2 1=%s 2=%s" % (m[pad("J1", "1")], m[pad("J1", "2")])]
    open(os.path.join(out, "02_kbd_common.net"), "w", encoding="utf-8", newline=NL).write(NL.join(lines) + NL)
    json.dump(dict(nets=m, columns=cols, rows=ROWS,
                   keys={t: dict(row=ROWS.index(v[2]) + 1, col=cols.index(v[3]) + 1, row_pin=v[2], col_pin=v[3],
                                 x=round(v[4], 2), y=round(v[5], 2)) for t, v in info.items()}),
              open(os.path.join(cpmodel.ROOT, "src", "altium_net_map.json"), "w", encoding="utf-8"), indent=1)

    # the matrix as a table: one line per row, the key (its reference on the board) in each of the 16 columns
    with open(os.path.join(cpmodel.ROOT, "src", "keymap.csv"), "w", encoding="utf-8", newline=NL) as f:
        f.write("row (Arduino pin)," + ",".join("col %d (%s)" % (k + 1, c) for k, c in enumerate(cols)) + NL)
        for k, a in enumerate(ROWS, 1):
            at = {cols.index(info[t][3]): t for t in rows[a]}
            f.write("row %d (%s)," % (k, a) + ",".join(at.get(n, "") for n in range(len(cols))) + NL)

    # the footprint that exists only in the Altium design: saved into the project library, so the project is complete
    lib = os.path.join(cpmodel.ROOT, "lib", "commander.pretty")
    os.makedirs(lib, exist_ok=True)
    saved = []
    for ref, name in (("T1", "KeySwitch_Keychron_LP_Optical"),):
        try:
            fp = pcbnew.FOOTPRINT(fps[ref])
            fp.SetOrientationDegrees(0)
            fp.SetPosition(pcbnew.VECTOR2I(0, 0))
            fp.SetFPID(pcbnew.LIB_ID("commander", name))
            fp.SetReference("REF**")
            for p in fp.Pads():
                p.SetNetCode(0)
            pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP).FootprintSave(lib, fp)
            saved.append(name)
        except Exception as e:              # noqa: BLE001
            problems.append("footprint %s not saved: %s" % (name, e))
    print("keys: %d in rows of %s   resistors: %d on keys, %d others   nets renamed: %d   footprints saved: %s"
          % (len(info), [len(rows[a]) for a in ROWS], len(used), len(rest), len(m), saved))
    for p in problems:
        print("  PROBLEM:", p)
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
