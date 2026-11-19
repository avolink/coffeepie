# Commander keyboard (KiCad 10), revision K1

The keyboard of the Commander terminal as a KiCad project: the prototyped Altium design **Teclado_V2**
(84 Keychron low-profile optical switches, 6 x 16 matrix) converted to KiCad, with the hand-soldered
**Arduino Micro module replaced by a microcontroller soldered on the board** - since 2026-11-15 an **STC8H8K64U**
(5 V, USB without crystal, about 0.35 USD in volume) instead of the ATmega32U4 (about 3.30 USD), for the cost target.
**The firmware has to be rewritten for it** (8051 core; see *Firmware* below).

**Status (2026-11-15, STC8H8K64U rebuild): every connection made.** Ready for a prototype order once the
assumptions at the end of this file are confirmed (board thickness, USB-C position), someone has looked over the new
copper, and the new firmware exists.

| Check | Result |
|---|---|
| ERC | clean |
| Model / schematic / board | identical, pad by pad (960 pads) |
| KiCad DRC: unconnected | **0** |
| KiCad DRC: other remarks | on the new copper: 2 "starved thermal" (C204 / C206 reach the pour with one spoke - they also have a track) and a few dangling stubs / single-layer vias beside the chip (harmless); the rest are in the prototype's own copper - 3 hole clearances and 10 copper-to-edge (see *Found in the prototype's design*) |

(The 2026-11-14 build with the ATmega32U4 had 989 pads; that board is in git history.)

The fabrication files are in `../../fabrication/gerber/commander_keyboard_revK1_PROTOTYPE/` (+ BOM and placement
in `../../fabrication/bom` and `/position`).

**This board file is now the master.** The last three connections were made by targeted fixes after the routing
run (below); a full rebuild would route again from scratch and need them again. For changes use
`build.py --variant keyboard --keep-board` (checks and exports only) or KiCad itself.

How the board was finished (KiCad's Python, `CP_ROOT` = this folder, tools in `../commander_mainboard/tools/`):

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
| **New, bottom face, where the module was** | STC8H8K64U-45I-LQFP32 (LCSC C5210757), 22 ohm USB series resistors, 1 uF on UCAP, 3 x 100 nF + 4.7 uF decoupling, BOOT button with pull-up (no crystal, no reset circuit, no ISP pads: the chip is programmed over the USB-C) |
| **New, bottom face, left edge** | USB-C receptacle (16-pin, USB 2.0, 5.1 k on both CC pins), USBLC6-2 ESD array, 750 mA resettable fuse, 4.7 uF |

The matrix nets carry the **Arduino pin names** the prototype used (`A0`..`A5` rows, `D2`..`D13`, `MISO`, `SCK`,
`MOSI`, `SS` columns, `D0` LED enable): they name the lines of the matrix; which STC pin each one reaches is in the
table below. `src/keymap.csv` lists which switch (T1..T84) sits on which row and column.

## Firmware: the pin table of the STC8H8K64U

The Arduino sketch of the prototype does not run on the STC8H8K64U (8051 core, programmed in C with SDCC or Keil;
STC publishes USB HID keyboard examples). The new firmware drives the six rows, reads the sixteen columns, switches
the infra-red LEDs with `D0`, and is a USB HID keyboard at full speed (the chip's USB needs no crystal: its clock
locks to the bus). The chip runs from the same +5 V as the matrix, as the ATmega did.

| Matrix line (net) | Role | STC pin | Port |
|---|---|---|---|
| A0, A1, A2, A3, A4, A5 | rows (outputs) | 1, 2, 3, 4, 5, 6 | P1.0, P1.1, P1.4, P1.5, P1.6, P1.7 |
| MOSI | column | 7 | P1.3 |
| SCK | column | 9 | P5.4 |
| MISO | column | 16 | P3.3 |
| SS_RXLED | column | 17 | P3.4 |
| D2_SDA, D3_SCL, D4, D5 | columns | 19, 20, 21, 22 | P3.6, P3.7, P2.0, P2.1 |
| D6, D7, D8, D9 | columns | 25, 26, 27, 28 | P2.4, P2.5, P2.6, P2.7 |
| D10, D11, D12, D13 | columns | 29, 30, 31, 32 | P0.0, P0.1, P0.2, P0.3 |
| D0_RX | infra-red LED enable (to Q1 through J1) | 18 | P3.5 |
| USB D- / D+ | USB | 13 / 14 | P3.0 / P3.1 |
| BOOT_N | boot button, 10 k pull-up | 15 | P3.2 |
| PWRKEY_DRV | power-key output (gate of Q201, 100 k pull-down) | 24 | P2.3 |

Spare: pin 23 (P2.2). The column inputs keep the prototype's 10 k pull-ups (R169..R184). The STC pins
start in quasi-bidirectional mode (strong low, weak high): the firmware sets the six rows and `D0` to push-pull
outputs, as the ATmega's were, so that they can source current when high.

### The power key (2026-11-18)

T16 - top row, last column (row `A0`, column `MOSI`), the orange power keycap - is the Commander's power button.
`src/netlist/09_kbd_powerkey.net`:

- **T16's infra-red LED is on row A0, not on LED_K** (an `OVERRIDE` of the generated row file): it lights while `A0`
  is low and only then. In the normal scan nothing changes except that the firmware waits ~30 us after driving `A0`
  low before reading the columns (the LED and photo-transistor need that to settle).
- **Power-key output:** while T16 is pressed, set `PWRKEY_DRV` (P2.3, push-pull) high: Q201 pulls `PWR_KEY_N`, which is
  the mainboard's RK817 `PMIC_PWRON`, to ground. Mirror the key, debounced; don't time anything - the RK817 does
  (press: on; short press while on: power-key event for the OS; ~6 s held: off). Whether T16 also sends a keycode is a
  firmware choice (it should not, normally).
- **Standby:** the keyboard stays powered while the board is off (its 5 V is the mainboard's VCC5V_BUS). When USB is
  suspended / not configured: `D0` low (all other LEDs off), then sleep in power-down with the wake-up timer, every
  ~20 ms: `A0` low for ~100 us, read `MOSI` exactly as the normal scan reads T16, `A0` back, sleep. About
  35 uA on average. Keep the watchdog on: a hung keyboard means no power button (for service, short the two pins
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
| `src/netlist/01_kbd_mcu.net` | the microcontroller circuit (STC8H8K64U) - **edit this to change the new circuit** |
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
- The ADC reference pin (11) is tied to +5 V with its own 100 nF: no analogue input is used.
- UCAP (pin 8): 1 uF to ground for the chip's USB regulator (STC asks for 0.1 - 10 uF).
- Clock: the chip's internal oscillator; USB locks it to the host. No crystal.
- USB: device, full speed. 22 ohm in series at the chip, ESD array at the receptacle.
- No reset circuit: the chip resets itself at power-up (P5.4 is used as an ordinary pin, for `SCK`).

## Programming: over the USB-C, no adapter

(Unchanged by the power key: J201 stays the keyboard's USB-C, to the mainboard in the Commander and to any PC later.)

The STC8H8K64U has a USB boot loader in ROM. Hold the BOOT button SW201 (bottom face; P3.2 to ground) while
plugging the USB cable in, release it: the keyboard appears as "STC USB Writer (HID1)", and STC's free tool
STC-ISP loads the firmware. Firmware updates later work the same way - which also keeps the keyboard repairable
in the field.

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
