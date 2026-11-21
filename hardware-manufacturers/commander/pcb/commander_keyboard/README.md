# Commander keyboard (KiCad 10), revision K1

The keyboard of the Commander terminal as a KiCad project: the prototyped Altium design **Teclado_V2**
(84 Keychron low-profile optical switches, 6 x 16 matrix) converted to KiCad, with the hand-soldered
**Arduino Micro module replaced by a microcontroller soldered on the board** - since 2026-11-19 a **Raspberry Pi
RP2040** (LCSC C2040) with a 2 MB QSPI flash (GD25Q16E), a 12 MHz crystal and a 3.3 V LDO (ME6211), so that the
keyboard runs **QMK and VIA** as they are (`firmware/qmk/`, see *Firmware* below). Before: the STC8H8K64U
(2026-11-15, needed a firmware of its own) and the ATmega32U4 of the Arduino (2026-11-14); both boards are in git
history.

**Status (2026-11-19, RP2040 rebuild): 3 connections still open - finish them by hand in KiCad before ordering.**

| Check | Result |
|---|---|
| ERC | clean |
| KiCad DRC: unconnected | **4**: `A1` (a short top-layer piece north-west of the chip not joined to its row), `D0_RX` (U201 pin 2), `QSPI_SD3` (U201 pin 51 to the flash's pin 7), and the ground pad 2 of SW201 (the BOOTSEL button) off the pour |
| KiCad DRC: other remarks | 17 dangling tracks / 11 dangling vias (left-overs of the STC's copper, cut back at the edge of the area that was cleared: delete them with KiCad's *Cleanup Tracks & Vias*), 4 "starved thermal"; the rest are in the prototype's own copper - 3 hole clearances and 10 copper-to-edge (see *Found in the prototype's design*). No clearance violation, no short. |

The routing round the RP2040 (QFN-56, 0.4 mm pitch, 24 matrix lines arriving from every side) was made by
`../commander_mainboard/tools/kbd_rp2040_board.py` (stages plan / edit / route / repair / promote): *plan* picks the
GPIO for each line so that nothing crosses (written into `src/netlist/01_kbd_mcu.net`), *edit* clears the STC's area
and places the new parts, *route* and *repair* route it; every run leaves about three nets open, a different three
each time. The board before it: `build/kbd_before_rp2040.kicad_pcb`.

The fabrication files are in `../../fabrication/gerber/commander_keyboard_revK1_PROTOTYPE/` (+ BOM and placement
in `../../fabrication/bom` and `/position`).

**This board file is the master.** For changes use `build.py --variant keyboard --keep-board` (checks and exports
only) or KiCad itself.

How the STC8H8K64U board of 2026-11-15 was finished (KiCad's Python, `CP_ROOT` = this folder, tools in
`../commander_mainboard/tools/`; history - the matrix copper outside the chip's area is still from it):

```
kbd_board.py --stage route      (CP_VARIANT_FROM=12: orders 13..24; best: 36 of 37 nets)
kbd_board.py --stage ground
kbd_fix_net.py    <in> <out> D10 105 118 D9,D6,D12,D5,D4,D13,D8     D10 west first, the west-row bundle re-laid
kbd_fix_ground.py <in> <out> C209.2 RESET_N,D0_RX,D7,MOSI           C209's ground off its pour island
kbd_fix_net.py    <in> <out> MOSI 146 160 SS_RXLED,RESET_N,D0_RX,D7,MISO,SCK
```

## What was taken over, what is new

| | |
|---|---|
| **Unchanged from the prototype** | outline (315.05 x 135.01 mm, 188 cut-outs: two 6 x 1.6 mm slots per switch and 20 stabiliser openings), the 84 switches and their 168 resistors, 16 column pull-ups, the LED switch (Q1, R185, jumper J1), every track and copper zone of the matrix. Nothing was moved or re-routed. |
| **Removed** | the Arduino Micro module (U1, bottom face) and the 58 short tracks (165 mm) that led from its pads to the first via; the west part of the +5 V track that fed its supply pin |
| **Corrected** | the 113 mechanical holes of the switches (84 x 4.0 mm, 29 x 2.0 mm) came out of the conversion as vias without a copper ring, 42 of them carrying the net of a track that passes nearby; they are now non-plated holes without a net |
| **New, bottom face, where the module was** | RP2040 (QFN-56, LCSC C2040), GD25Q16E 2 MB QSPI flash (SOIC-8), 12 MHz crystal (C9002) with 1 k / 2 x 22 pF, ME6211 3.3 V LDO, 27 ohm USB series resistors, 100 nF / 1 uF / 4.7 uF decoupling, BOOTSEL button (1 k to the flash's chip select); no reset circuit, no SWD pads: the chip is programmed over the USB-C |
| **Changed for 3.3 V** | the 16 column pull-ups (R169..R184) hang on the LDO's 3.3 V (their supply track cut off the 5 V bus); Q1's base resistor R185 is 330 ohm instead of 1 k, so that a 3.3 V output still drives Q1 hard |
| **New, bottom face, left edge** | USB-C receptacle (16-pin, USB 2.0, 5.1 k on both CC pins), USBLC6-2 ESD array, 750 mA resettable fuse, 4.7 uF |

The matrix nets carry the **Arduino pin names** the prototype used (`A0`..`A5` rows, `D2`..`D13`, `MISO`, `SCK`,
`MOSI`, `SS` columns, `D0` LED enable): they name the lines of the matrix; which RP2040 pin each one reaches is in
the table below. `src/keymap.csv` lists which switch (T1..T84) sits on which row and column.

## Firmware: QMK / VIA on the RP2040

`firmware/qmk/coffeepie/commander/` is a QMK keyboard (copy it to `keyboards/coffeepie/commander` in a QMK checkout;
`qmk compile -kb coffeepie/commander -km via`), written by `../commander_mainboard/tools/kbd_qmk.py` from the board
(layout from the switch positions) and the pin table. `firmware/qmk/commander_via.json` is the VIA definition. The
matrix is optical, so it is a custom "lite" matrix (`matrix.c`): drive a row low, wait ~30 us for the LEDs and
photo-transistors to settle, read the columns. **Untested:** whether a lit (pressed) key reads low or high on its
column - `OPTICAL_PRESSED_WHEN_LIT` in `config.h` flips it.

| Matrix line (net) | Role | RP2040 pin | GPIO |
|---|---|---|---|
| A0, A1, A2, A3, A4, A5 | rows (outputs) | 32, 34, 3, 36, 37, 38 | GP21, GP22, GP1, GP24, GP25, GP26 |
| MOSI, SCK, MISO, SS_RXLED | columns | 13, 4, 5, 6 | GP10, GP2, GP3, GP4 |
| D2_SDA, D3_SCL, D4, D5 | columns | 8, 9, 11, 12 | GP6, GP7, GP8, GP9 |
| D6, D7, D8, D9 | columns | 17, 14, 27, 28 | GP14, GP11, GP16, GP17 |
| D10, D11, D12, D13 | columns | 35, 29, 30, 31 | GP23, GP18, GP19, GP20 |
| D0_RX | infra-red LED enable (to Q1 through J1) | 2 | GP0 |
| PWRKEY_DRV | power-key output (gate of Q201, 100 k pull-down) | 15 | GP12 |
| USB D- / D+ | USB | 46 / 47 | - |
| QSPI | program flash U204 | 51..56 | - |

The authoritative table is the one in `src/netlist/01_kbd_mcu.net` (written by `kbd_rp2040_board.py --stage plan`);
QMK's column order follows the matrix (`src/keymap.csv`), not this table's grouping. Spare: GPIO5, 13, 15, 27, 28,
29. The column inputs keep the prototype's 10 k pull-ups, now to 3.3 V: **the RP2040 takes no 5 V on any pin.**

### The power key (2026-11-18)

T16 - top row, last column (row `A0`, column `MOSI`), the orange power keycap - is the Commander's power button.
`src/netlist/09_kbd_powerkey.net`:

- **T16's infra-red LED is on row A0, not on LED_K** (an `OVERRIDE` of the generated row file): it lights while `A0`
  is low and only then. In the normal scan nothing changes except that the firmware waits ~30 us after driving `A0`
  low before reading the columns (the LED and photo-transistor need that to settle).
- **Power-key output:** while T16 is pressed, set `PWRKEY_DRV` (GP12) high: Q201 pulls `PWR_KEY_N`, which is
  the mainboard's RK817 `PMIC_PWRON`, to ground. Mirror the key, debounced; don't time anything - the RK817 does
  (press: on; short press while on: power-key event for the OS; ~6 s held: off). Whether T16 also sends a keycode is a
  firmware choice (it should not, normally).
- **Standby:** the keyboard stays powered while the board is off (its 5 V is the mainboard's VCC5V_BUS). When USB is
  suspended / not configured: `D0` low (all other LEDs off) and only T16 is read (`A0` low, read `MOSI`) - that is
  what the QMK `matrix.c` does. (The RP2040 draws a few mA doing this, more than the STC's planned 35 uA
  power-down; a deeper sleep would be a firmware improvement.) Keep the watchdog on: a hung keyboard means no power button (for service, short the two pins
  of the mainboard's J22).
- **Power-key cable J202** (JST-SH 2, bottom face, next to the USB-C J201): 1 power key (`PWR_KEY_N`), 2 GND - to
  the mainboard's J22 (the same part), a 2-way JST-SH cable. **USB stays a standard USB-C** (J201, fitted), so that
  after the Commander's life the keyboard can be reused on its own as a plain USB keyboard: J202 then stays empty and
  the firmware treats T16 as an ordinary key (detect it: no host activity on the power key, or a firmware setting).

**USB-C mid-mount (2026-11-19):** J201 is now the HCTL HC-TYPE-C-16P-CB1.6 (LCSC C2894902, as on the numpad /
touchpad), sunk in a notch of the left edge with its pads on the bottom face: flush with the top face (the keycaps),
1.6 mm below the bottom (the old top-mount stood 3.2 mm below). Notch 9.50 x 6.60 mm, R0.5 inner corners, centred on
the receptacle (y 160, edge at x -0.39); its pad row sits 7.35 mm in from the edge. `commander_keyboard.kicad_dru`
lets those pads come to 0.15 mm of the notch (the maker's layout). The area was checked: only J201's own fan-out
copper and the ground pours are there.

**On the board (2026-11-19, `tools/kbd_powerkey_board.py`, stages edit / route / route_more / promote; the board
before it: `build/kbd_before_powerkey.kicad_pcb`):** T16 pad 6 off LED_K onto A0 (routed to R31); U201 pin 24 on
PWRKEY_DRV; J201 swapped for the mid-mount (bottom face, notch cut, old fan-out re-routed; A6 (D+) changes layers
through a 0.5 / 0.3 via right behind its pad, as D+ / D- alternate along the row; J201's pads have mask margin 0 and
solid ground joints: the board's 0.1 mm mask opening leaves no web on a 0.5 mm row); Q201 / R207 by the
microcontroller (136.5, 154.5), J202 at the left edge above J201 (2.6, 144.5), ED201 beside it; PWR_KEY_N runs the
135 mm from Q201 to J202. DRC: 0 unconnected, the same 45 violations as before (none new).

## How the project is built

Everything is generated by the tools of the mainboard project (`../commander_mainboard/tools/`):

```
python ../commander_mainboard/tools/build.py --variant keyboard            # all of it, about an hour
python ../commander_mainboard/tools/build.py --variant keyboard --keep-board   # checks and exports only
python ../commander_mainboard/tools/make_quote_package.py --variant keyboard   # Gerbers, drill, BOM, placement
```

| Source | What it is |
|---|---|
| `src/altium_import.kicad_pcb` | the Altium board as KiCad converts it (`kicad-cli pcb import --format altium`); the base of the board |
| `src/netlist/01_kbd_mcu.net` | the microcontroller circuit (RP2040) - **edit this to change the new circuit** |
| `src/netlist/10_kbd_3v3.net` | the column pull-ups moved to 3.3 V, R185's new value (`OVERRIDE`s) |
| `firmware/qmk/` | the QMK keyboard and the VIA definition (`tools/kbd_qmk.py`) |
| `src/netlist/02..08_*.net` | the matrix, written by `tools/kbd_extract.py` from the Altium board (generated, do not edit) |
| `src/altium_net_map.json`, `src/keymap.csv` | Altium net name -> name used here; the key matrix as a table |
| `lib/commander.pretty/` | the switch footprint (from the Altium board) and the ISP pads |

`tools/kbd_board.py` makes the board in five stages, each a process of its own:

| Stage | What it does |
|---|---|
| *import* | converts `commander/Teclado_V2/Teclado_V2.PcbDoc` (skipped when the Altium file is not there: `src/altium_import.kicad_pcb` is then used as it is) |
| *prepare* | nets renamed, mechanical holes made non-plated, module and its stubs removed, new parts placed at hand-planned positions (`FIXED` in the script) |
| *route* | every chip pin gets a fixed piece of track with a via (two staggered rows round the chip), then the nets are routed (chip pin 24 first); twelve passes that take the lines in different orders, the best is kept |
| *repair* | for a net that is still open: the router's tracks round its stuck end are taken out, it is routed first, then the others again; a round that makes things worse is undone |
| *ground* | every ground pad or via that the pours do not reach gets a track or via to them |

The schematic (8 sheets) is generated from the netlists, and `check_consistency.py` compares model,
schematic and board pad by pad.

**Hand edits in KiCad are overwritten by a rebuild.** Once someone finishes or tidies the routing by hand,
stop regenerating the board (`--keep-board`) and use *Update PCB from Schematic* for later changes.

## The circuit round the microcontroller

- Supply: USB VBUS -> 750 mA resettable fuse -> `VCC5`. The 84 infra-red LEDs take about 6.7 mA each
  (560 ohm from 5 V), **0.56 A with all of them on**, which is why the fuse is 750 mA and not the Arduino's
  500 mA. The LEDs are switched together by Q1 from pin `D0`; whether the firmware keeps them on all the time
  or pulses them decides the real consumption. A USB 2.0 port guarantees 0.5 A; the mainboard's keyboard port
  must be allowed to give more, or the firmware must pulse the LEDs.
- 3.3 V: ME6211 LDO from `VCC5` (4.7 uF in and out) for the RP2040, the flash and the column pull-ups (about
  35 mA). The LEDs stay on 5 V.
- Core 1.1 V: the RP2040's own regulator (VREG_VOUT to both DVDD pins, 1 uF + 100 nF).
- Clock: 12 MHz crystal, 1 k in series with XOUT and 22 pF each side, as on the Raspberry Pi Pico.
- USB: device, full speed. 27 ohm in series at the chip, ESD array at the receptacle.
- TESTEN to ground; RUN left to its internal pull-up (no reset circuit); SWD pins left open.

## Programming: over the USB-C, no adapter

(Unchanged by the power key: J201 stays the keyboard's USB-C, to the mainboard in the Commander and to any PC later.)

The RP2040 has a USB boot loader in ROM. Hold the BOOTSEL button SW201 (bottom face; pulls the flash's chip select
low through 1 k) while plugging the USB cable in: the keyboard appears as a USB drive "RPI-RP2"; copy the QMK `.uf2`
file onto it. Once QMK runs, its `QK_BOOT` key (layer 1) does the same without the button. VIA changes the keymap
live, no flashing. That also keeps the keyboard repairable in the field.

## Assumptions to confirm before ordering

1. **Board thickness 1.6 mm.** The Altium file carries only its default stack-up, not the thickness that was
   ordered. If the prototype was thinner (the switches or the case may need that), say so.
2. **Position of the USB-C receptacle**: left edge, 12.5 mm above the bottom edge, plug entering from
   the left. The module's own micro-USB is gone with the module, so this is a new mechanical decision; the
   spot was chosen because the bottom-left corner is free of switches. It can be moved by changing `USB_Y`
   (or the edge) in `tools/kbd_board.py`.
3. **Parts on the bottom face** need a second assembly pass at the assembler (the module was hand-soldered
   there before). Height: the receptacle is 3.2 mm, everything else under 1 mm.
4. **Pin roles of the switch footprint** (which pad is LED anode, collector, ...) are inferred from the
   circuit around it, and are used only for the schematic symbol; the copper is the prototype's.
5. The value "500" on 84 resistors was read as 500 ohm (the BOM calls them `500R_0805`; 499 or 510 ohm are
   the values one can buy).

## Found in the prototype's design while converting it

These are in the Altium file itself; KiCad's checks show them. None was introduced by the conversion.

1. **One connection is missing in the LED net.** The copper strip that collects the LED cathodes of the two
   bottom-left keys (T75, T76; bottom face, x 9.3..57.5 mm, y 138.5 mm) ends 1.8 mm short of the via that
   leads on to the rest of the net (at x 59.6 mm). In the Altium file the two pieces carry the same net name
   but do not touch. **The KiCad board joins them with a short track.** If those two keys work on the
   prototype, they do it through something that is not in the design file - worth a look at the board.
2. **Two tracks run tangent to a 2 mm locating hole** (nets `T82_A` and `T84_A`, near x 253 / 291 mm,
   y 141.6 mm): the drill can cut into them. Left as they are; move the tracks 0.3 mm in a later revision.
3. **Copper closer than 0.2 mm to the board edge in 10 places** (a via on the bottom edge at x 196.7 mm,
   tracks of `A0`, `A3`, `A4`, `SCK`, `D7` along the edges). Left as they are; a fabricator may ask about them.
4. The 113 round holes of the switches were pads without a copper ring in Altium, 42 of them carrying the net
   of a nearby track. In KiCad they are plain non-plated holes now.
5. Q1 (MMBT2222A) switches all 84 LEDs through a 1 k base resistor: about 4 mA of base current for 0.56 A
   of collector current. It works on the prototype, so nothing was changed, but the transistor is not driven
   into saturation; a logic-level MOSFET in the same footprint would run cooler.
