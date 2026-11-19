"""kbd_qmk.py (KiCad's Python, CP_ROOT = commander_keyboard) - writes the QMK keyboard definition of the Commander
keyboard (RP2040, since 2026-11-19) into firmware/qmk/ of the keyboard project:

  firmware/qmk/coffeepie/commander/     copy this folder to qmk_firmware/keyboards/coffeepie/commander, then
                                        qmk compile -kb coffeepie/commander -km via
  firmware/qmk/commander_via.json       VIA's definition (VIA: Settings > "Show Design tab", Design > Load)

Sources: src/keymap.csv (which switch T1..T84 is on which row / column line), build/kbd_rp_plan.json (which RP2040
GPIO each line has, from kbd_rp2040_board.py --stage plan) and the switch positions on the board (key units of
19.0 mm, widths from the spacing).
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew                                   # noqa: E402
from pcbnew import ToMM                         # noqa: E402

import cpmodel                                  # noqa: E402

ROOT = cpmodel.ROOT
OUT = os.path.join(ROOT, "firmware", "qmk")
KB = os.path.join(OUT, "coffeepie", "commander")
PITCH = 19.0
VID, PID = "0x4350", "0x4B42"                   # ("CP", "KB")

ROW_LINES = ["A0", "A1", "A2", "A3", "A4", "A5"]
COL_LINES = ["SCK", "MISO", "D13", "D12", "D11", "D10", "D9", "D8", "D7", "D6", "D5", "D4", "D3_SCL", "D2_SDA",
             "SS_RXLED", "MOSI"]
# default layer: a 75 % layout (84 keys); T16 is the Commander's power key (hardware: PWRKEY_DRV, see matrix.c)
BASE = {
    1: "KC_ESC", 2: "KC_F1", 3: "KC_F2", 4: "KC_F3", 5: "KC_F4", 6: "KC_F5", 7: "KC_F6", 8: "KC_F7", 9: "KC_F8",
    10: "KC_F9", 11: "KC_F10", 12: "KC_F11", 13: "KC_F12", 14: "KC_PSCR", 15: "KC_DEL", 16: "KC_NO",
    17: "KC_GRV", 18: "KC_1", 19: "KC_2", 20: "KC_3", 21: "KC_4", 22: "KC_5", 23: "KC_6", 24: "KC_7", 25: "KC_8",
    26: "KC_9", 27: "KC_0", 28: "KC_MINS", 29: "KC_EQL", 30: "KC_BSPC", 31: "KC_HOME",
    32: "KC_TAB", 33: "KC_Q", 34: "KC_W", 35: "KC_E", 36: "KC_R", 37: "KC_T", 38: "KC_Y", 39: "KC_U", 40: "KC_I",
    41: "KC_O", 42: "KC_P", 43: "KC_LBRC", 44: "KC_RBRC", 45: "KC_BSLS", 46: "KC_PGUP",
    47: "KC_CAPS", 48: "KC_A", 49: "KC_S", 50: "KC_D", 51: "KC_F", 52: "KC_G", 53: "KC_H", 54: "KC_J", 55: "KC_K",
    56: "KC_L", 57: "KC_SCLN", 58: "KC_QUOT", 59: "KC_ENT", 60: "KC_PGDN",
    61: "KC_LSFT", 62: "KC_Z", 63: "KC_X", 64: "KC_C", 65: "KC_V", 66: "KC_B", 67: "KC_N", 68: "KC_M",
    69: "KC_COMM", 70: "KC_DOT", 71: "KC_SLSH", 72: "KC_RSFT", 73: "KC_UP", 74: "KC_END",
    75: "KC_LCTL", 76: "KC_LGUI", 77: "KC_LALT", 78: "KC_SPC", 79: "KC_RALT", 80: "MO(1)", 81: "KC_RCTL",
    82: "KC_LEFT", 83: "KC_DOWN", 84: "KC_RGHT",
}
FN = {1: "QK_BOOT", 2: "KC_BRID", 3: "KC_BRIU", 8: "KC_MPRV", 9: "KC_MPLY", 10: "KC_MNXT", 11: "KC_MUTE",
      12: "KC_VOLD", 13: "KC_VOLU", 15: "KC_INS"}


def matrix_of():
    """T number -> (row, col) from src/keymap.csv."""
    out = {}
    rows = list(csv.reader(open(os.path.join(ROOT, "src", "keymap.csv"), encoding="utf-8")))
    for r, row in enumerate(rows[1:]):
        for c, cell in enumerate(row[1:]):
            if cell.strip():
                out[int(cell.strip()[1:])] = (r, c)
    return out


def positions():
    b = pcbnew.LoadBoard(os.path.join(ROOT, cpmodel.PRJ + ".kicad_pcb"))
    keys = {}
    for f in b.GetFootprints():
        r = f.GetReference()
        if r.startswith("T") and r[1:].isdigit():
            keys[int(r[1:])] = (ToMM(f.GetPosition().x), ToMM(f.GetPosition().y))
    x0 = min(x for x, y in keys.values()) - PITCH / 2          # (the leftmost key of the 1 u rows)
    x0 = min(x for k, (x, y) in keys.items() if k <= 31) - PITCH / 2
    y0 = min(y for x, y in keys.values())
    rows = {}
    for k, (x, y) in keys.items():
        rows.setdefault(int(round((y - y0) / PITCH)), []).append((k, (x - x0) / PITCH))
    out = {}
    for ry, ks in rows.items():
        left = 0.0
        for k, c in sorted(ks, key=lambda t: t[1]):
            if c - left > 0.75:                 # a gap (the space bar row's right half starts after the space bar)
                pass
            w = round(2 * (c - left) * 4) / 4
            if w < 1.0 or w > 7.0:              # not adjacent to the key before: a 1 u key centred on c
                w, left = 1.0, c - 0.5
            out[k] = dict(x=round(left, 2), y=float(ry), w=w)
            left += w
    return out


def main():
    plan = json.load(open(os.path.join(ROOT, "build", "kbd_rp_plan.json")))
    gp = {n: "GP" + g[4:] for n, g in plan["gpio"].items()}
    mat = matrix_of()
    pos = positions()
    assert len(mat) == 84 and len(pos) == 84, (len(mat), len(pos))
    os.makedirs(os.path.join(KB, "keymaps", "default"), exist_ok=True)
    os.makedirs(os.path.join(KB, "keymaps", "via"), exist_ok=True)
    layout = [dict(label="T%d" % k, matrix=list(mat[k]), x=pos[k]["x"], y=pos[k]["y"], **({"w": pos[k]["w"]} if pos[k]["w"] != 1 else {}))
              for k in sorted(mat)]
    kj = {
        "manufacturer": "Coffee Pie",
        "keyboard_name": "Commander keyboard",
        "maintainer": "coffeepie",
        "processor": "RP2040",
        "bootloader": "rp2040",
        "usb": {"vid": VID, "pid": PID, "device_version": "1.0.0"},
        "matrix_size": {"rows": 6, "cols": 16},
        "features": {"bootmagic": True, "extrakey": True, "mousekey": True, "nkro": True},
        "layouts": {"LAYOUT": {"layout": layout}},
    }
    json.dump(kj, open(os.path.join(KB, "keyboard.json"), "w", encoding="utf-8", newline="\n"), indent=4)
    open(os.path.join(KB, "rules.mk"), "w", newline="\n").write(
        "# the optical matrix is scanned by matrix.c (infra-red LEDs, phototransistors, power key)\n"
        "CUSTOM_MATRIX = lite\nSRC += matrix.c\n")
    cfg = ["#pragma once", "",
           "/* Commander keyboard, RP2040 (written by pcb/commander_mainboard/tools/kbd_qmk.py - pins from the board's",
           " * GPIO plan, build/kbd_rp_plan.json).  Net names are the Arduino pin names of the prototype. */", "",
           "/* program flash: GigaDevice GD25Q16E (2 MB) - its boot stage 2 */",
           "#define RP2040_FLASH_GD25Q64CS", "",
           "/* rows A0..A5: driven low one at a time */",
           "#define MATRIX_ROW_PINS { %s }" % ", ".join(gp[n] for n in ROW_LINES),
           "/* columns (" + " ".join(COL_LINES) + "): 10 k pull-ups to 3.3 V on the board */",
           "#define MATRIX_COL_PINS { %s }" % ", ".join(gp[n] for n in COL_LINES), "",
           "/* the infra-red LEDs of all keys: high = on (Q1 through the jumper J1, net D0_RX) */",
           "#define OPTICAL_LED_EN_PIN %s" % gp["D0_RX"],
           "/* the Commander's power key output (Q201 pulls the mainboard's PMIC_PWRON low while it is high) */",
           "#define POWER_KEY_PIN %s" % gp["PWRKEY_DRV"],
           "/* T16 (top row, last key) is the power key: matrix row 0, column 15 */",
           "#define POWER_KEY_ROW 0", "#define POWER_KEY_COL 15", "",
           "/* phototransistor settling time after a row is driven low, microseconds */",
           "#define OPTICAL_SETTLE_US 30",
           "/* 1: a pressed key lets the light through (its column reads low).  If every key reads pressed at rest,",
           " *    the switches work the other way round: set 0. */",
           "#define OPTICAL_PRESSED_WHEN_LIT 1", ""]
    open(os.path.join(KB, "config.h"), "w", newline="\n").write("\n".join(cfg))
    open(os.path.join(KB, "matrix.c"), "w", newline="\n").write(MATRIX_C)

    def keymap(layers, extra=""):
        out = ["// Commander keyboard - written by pcb/commander_mainboard/tools/kbd_qmk.py", "#include QMK_KEYBOARD_H", "",
               "const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {"]
        for i, lay in enumerate(layers):
            rows = {}
            for k in sorted(mat):
                rows.setdefault(int(pos[k]["y"]), []).append(lay.get(k, "KC_TRNS" if i else "KC_NO"))
            body = ",\n        ".join(", ".join(v) for _, v in sorted(rows.items()))
            out.append("    [%d] = LAYOUT(\n        %s\n    )," % (i, body))
        out.append("};")
        return "\n".join(out) + "\n" + extra
    open(os.path.join(KB, "keymaps", "default", "keymap.c"), "w", newline="\n").write(keymap([BASE, FN]))
    open(os.path.join(KB, "keymaps", "via", "keymap.c"), "w", newline="\n").write(keymap([BASE, FN, {}, {}]))
    open(os.path.join(KB, "keymaps", "via", "rules.mk"), "w", newline="\n").write("VIA_ENABLE = yes\n")
    # VIA definition (v3): the layout in KLE form, "row,col" on each key
    kle = []
    for ry in sorted({int(pos[k]["y"]) for k in pos}):
        row, cx = [], 0.0
        for k in sorted((k for k in pos if int(pos[k]["y"]) == ry), key=lambda k: pos[k]["x"]):
            p = {}
            if abs(pos[k]["x"] - cx) > 1e-6:
                p["x"] = round(pos[k]["x"] - cx, 2)
            if pos[k]["w"] != 1:
                p["w"] = pos[k]["w"]
            if p:
                row.append(p)
            row.append("%d,%d" % mat[k])
            cx = pos[k]["x"] + pos[k]["w"]
        kle.append(row)
    via = {"name": "Commander keyboard", "vendorId": VID, "productId": PID, "matrix": {"rows": 6, "cols": 16},
           "keycodes": ["qmk_lighting"], "menus": [], "layouts": {"keymap": kle}}
    json.dump(via, open(os.path.join(OUT, "commander_via.json"), "w", encoding="utf-8", newline="\n"), indent=2)
    open(os.path.join(KB, "readme.md"), "w", newline="\n").write(README % dict(
        pins="\n".join("| %s | %s |" % (n, gp[n]) for n in ROW_LINES + COL_LINES + ["D0_RX", "PWRKEY_DRV"])))
    print("QMK keyboard written to", KB)
    print("VIA definition:", os.path.join(OUT, "commander_via.json"))


MATRIX_C = r"""// Commander keyboard: the optical matrix (written by pcb/commander_mainboard/tools/kbd_qmk.py)
//
// Each key is an infra-red LED and a phototransistor.  The LEDs of all keys are switched together by Q1
// (OPTICAL_LED_EN_PIN, about 0.56 A); the phototransistors' emitters sit on the rows (driven low to scan a row),
// their collectors on the columns (10 k pull-ups to 3.3 V).  T16's LED is not on Q1 but on row 0 itself: it lights
// whenever row 0 is scanned, so T16 - the Commander's power key - is read even with the other LEDs off.
//
// The LEDs are on only while the USB host has configured the keyboard; otherwise (the Commander off, or USB
// suspended) only T16 is read, and POWER_KEY_PIN follows it in hardware terms: high while T16 is down.
#include "quantum.h"
#include "matrix.h"
#include <hal.h> // (ChibiOS: USBD1.state - USB_ACTIVE once the host has configured the keyboard)

static const pin_t row_pins[MATRIX_ROWS] = MATRIX_ROW_PINS;
static const pin_t col_pins[MATRIX_COLS] = MATRIX_COL_PINS;
static bool        leds_on               = false;

static void leds(bool on) {
    if (on != leds_on) {
        gpio_write_pin(OPTICAL_LED_EN_PIN, on);
        leds_on = on;
        wait_us(200); // (the LEDs and phototransistors settle)
    }
}

void matrix_init_custom(void) {
    gpio_set_pin_output(OPTICAL_LED_EN_PIN);
    gpio_write_pin_low(OPTICAL_LED_EN_PIN);
    gpio_set_pin_output(POWER_KEY_PIN);
    gpio_write_pin_low(POWER_KEY_PIN);
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        gpio_set_pin_output(row_pins[r]);
        gpio_write_pin_high(row_pins[r]);
    }
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        gpio_set_pin_input(col_pins[c]); // (the board has the pull-ups)
    }
}

static matrix_row_t read_row(uint8_t r) {
    gpio_write_pin_low(row_pins[r]);
    wait_us(OPTICAL_SETTLE_US);
    matrix_row_t v = 0;
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        bool lit = !gpio_read_pin(col_pins[c]);
        if (lit == (OPTICAL_PRESSED_WHEN_LIT != 0)) v |= (matrix_row_t)1 << c;
    }
    gpio_write_pin_high(row_pins[r]);
    return v;
}

bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    leds(USBD1.state == USB_ACTIVE);
    bool changed = false;
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        matrix_row_t v = 0;
        if (leds_on) {
            v = read_row(r);
        } else if (r == POWER_KEY_ROW) {
            v = read_row(r) & ((matrix_row_t)1 << POWER_KEY_COL); // only T16 has its light
        }
        if (current_matrix[r] != v) {
            current_matrix[r] = v;
            changed           = true;
        }
    }
    gpio_write_pin(POWER_KEY_PIN, (current_matrix[POWER_KEY_ROW] >> POWER_KEY_COL) & 1);
    return changed;
}
"""

README = """# Commander keyboard (QMK)

The Commander's 84-key optical keyboard (pcb/commander_keyboard), Raspberry Pi RP2040 since 2026-11-19.

* Keyboard maintainer: Coffee Pie
* Hardware: pcb/commander_keyboard (KiCad), RP2040 + GD25Q16E flash, Keychron low-profile optical switches

Build (copy this folder to `qmk_firmware/keyboards/coffeepie/commander` first):

    qmk compile -kb coffeepie/commander -km via

Flashing: hold the BOOTSEL button (SW201, bottom face) while plugging in the USB-C cable - the board shows up as a
drive called RPI-RP2; copy the .uf2 file onto it.  Later: Fn + Esc (QK_BOOT), or hold Esc while plugging in
(bootmagic).

VIA: VIA does not know this keyboard yet - in VIA, Settings > "Show Design tab", then Design > Load
`../commander_via.json`.

The optical matrix is scanned by `matrix.c`: the infra-red LEDs (Q1) are on only while the USB host has configured
the keyboard; otherwise only T16 - the Commander's power key, wired to the mainboard's power-key line through Q201 -
is read.  `OPTICAL_PRESSED_WHEN_LIT` in config.h sets which way the switches work (not yet checked on a board).

| Line (net) | GPIO |
|---|---|
%(pins)s

All files here are written by `pcb/commander_mainboard/tools/kbd_qmk.py` from the board.
"""

if __name__ == "__main__":
    main()
