# Commander touchpad module (KiCad 10), revision P0

The other module of the Commander's sliding tray (`TOUCHPAD_MODULE` of the chassis model `COMMANDER_Z3E.skp`,
131 x 68 mm, 4.3 mm thick): a **111.4 x 62 mm capacitive touch area** and, in an 18 mm strip at its front end, the
electronics and a USB-C. (The model's module has a 117.8 mm surface and a 13 mm strip; 13 mm is too narrow for the
controller and its 25 sensor lines, so the strip grew by 5.8 mm - the module's outline is unchanged.) A USB mouse / precision touchpad of its own.

**Status (2026-11-18): generated layout, NOT ready to order - 10 nets open.** ERC clean, model / schematic / board
identical, Framework contacts added (below). The 2026-11-16 status ("37 of 40 nets routed") was wrong: the generator
counted only nets with two or more pads, so the 25 sensor lines (one pad each, at the IQS550) were never checked - and
15 of them did not reach the controller (the repair step had ripped their pre-drawn feeds, and rows 7-9's lanes
crossed, shorting RX7 / RX8 / RX9). Both are fixed in `tools/small_board.py` and the check now covers the sensor lines.
**Open now: sensor lines TX0, TX5, TX8, TX9, TX11, TX13, TX14, RX5 (from their feed vias, which end 2-8 mm from the
IQS550, to its pins), USB_CON_DP and VCC3V3** - KiCad DRC: 19 unconnected items (these plus a few ground pads) and 23
dangling vias (the waiting feed ends). The strip round the IQS550 is too crowded for the script: 25 feeds, the
microcontroller, USB and now J40's pads on the bottom copper under U4 (moving U4 1.7 mm away from J40 made it worse,
12 open). Finish in KiCad's interactive router (or move parts by hand to open a channel), then refill zones and DRC.
The 0.5 / 0.25 mm vias of the feeds and bridges are JLCPCB's standard 2-layer process (the project's minimum hole is
0.25 mm since 2026-11-18).

Rebuild (from the mainboard folder): `python tools/build.py --variant touchpad` (board: `tools/small_board.py`).

## Design

| | |
|---|---|
| Sensor | the board itself: 15 Tx columns (7.43 mm) x 10 Rx rows (6.20 mm) of diamonds on the top copper, 0.3 mm gaps; Tx diamonds joined by necks on the top, Rx diamonds by bridges (two 0.5 / 0.25 vias each) on the bottom. Area x 0.6-112.0, y 0.6-62.6 (board mm); the 5 mm band beside it carries the Tx feed lanes (8 on the bottom copper, 7 on the top), the Rx feeds run down the strip's edge on the bottom copper |
| Controller | Azoteq **IQS550**-B000 (150 channels, I2C, gestures / tap in the chip; LCSC C5271144, about $1.93 - **0 in stock at LCSC on 2026-11-16**, order from Azoteq's distributors) |
| Microcontroller | STC8H8K64U at 3.3 V (the keyboard's chip): reads the IQS550 (I2C on P1.5 / P1.4, RDY on INT1 P3.3, reset on P3.4) and reports as a USB HID mouse / Windows precision touchpad |
| Supply | USB 5 V -> 500 mA fuse -> HT7333 (3.3 V) |
| USB | USB-C 16-pin on the front edge, device side, as on the numpad |
| Boot loader | SW1 (P3.2) held while plugging in |

The overlay (0.3-0.5 mm glass or PET film glued over the electrodes) is part of the module, not of the board.
The bottom copper under the touch area carries only the Rx bridges (no pour); ground is poured in the strip only.

## Open points

1. **Electrode pitch**: 7.4 x 6.2 mm is coarse for a pad this size (Azoteq suggests about 5 mm); the IQS550 has no
   more channels (15 x 10). Interpolation gives usable resolution; a smaller sensor or a second controller are the
   alternatives. Tune the IQS550's settings (ATI targets, thresholds) on the real board.
2. Rx pins: only the A pin of each Rx pair is used (the B pins are left open) - confirm against the IQS5xx-B000
   datasheet's pin description.
3. Connection to the terminal and the overlay: as for the numpad - since 2026-11-17 the touchpad has **Framework's
   input-module contacts** on its underside (J40, 180 k BOARD_ID R40, supplies OR-ed by D40), Framework's B-size
   outline (131.02 x 67.95 mm) and seat, so it drops into the tray like a Framework module; it needs the same 1.5 mm
   feet and steel plate (see `../commander_numpad/README.md`, *Framework-compatible*). The USB-C stays.
4. A physical click (a switch on the IQS550's SW_IN under a hinged pad) is not fitted: tap-to-click only.

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
