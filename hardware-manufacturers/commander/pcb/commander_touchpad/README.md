# Commander touchpad module (KiCad 10), revision P0

The other module of the Commander's sliding tray (`TOUCHPAD_MODULE` of the chassis model `COMMANDER_Z3E.skp`,
131 x 68 mm, 4.3 mm thick): a **111.4 x 62 mm capacitive touch area** and, in an 18 mm strip at its front end, the
electronics and a USB-C. (The model's module has a 117.8 mm surface and a 13 mm strip; 13 mm is too narrow for the
controller and its 25 sensor lines, so the strip grew by 5.8 mm - the module's outline is unchanged.) A USB mouse / precision touchpad of its own.

**Status (2026-11-16): first generated layout, not reviewed by a person.** ERC clean, model / schematic / board
identical, 325 electrode diamonds (copper zones) with their necks, bridges and 25 feed lanes, **37 of 40 nets routed**:
TP_RDY, TP_SCL and TP_VREG (three short links round the IQS550 in the crowded strip) are left for KiCad's
interactive router. DRC: nothing else.

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
3. Connection to the terminal and the overlay: as for the numpad (USB-C on the front edge).
4. A physical click (a switch on the IQS550's SW_IN under a hinged pad) is not fitted: tap-to-click only.

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
