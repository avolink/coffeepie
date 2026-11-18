# Commander numpad module (KiCad 10), revision N0

One of the two modules of the Commander's sliding tray (`NUMPAD_MODULE` of the chassis model `COMMANDER_Z3E.skp`,
131 x 68 mm, 8 mm thick): **24 keys** in the model's grid (6 across at 17.0 mm, 4 down at 17.5 / 17.5 / 18.0 mm,
12 x 12 mm caps), a microcontroller and a USB-C. It is a USB keyboard (keypad usage page) of its own, so it also
works on any other computer.

**Status (2026-11-18): generated layout with the Framework contacts, not reviewed by a person - 1 signal net open.**
ERC clean, model / schematic / board identical (142 pads), 38 of 39 nets routed, ground pours stitched. KiCad DRC: 6
unconnected items - **KEY_4_1** (key SW_4_1 to U1 pin 3, a long run across the key field) and five ground links (C5 and
R2 to the USB-C's ground, the USB-C shell pin, J40 pad 7 to the bottom pour, two pour pieces), plus 4 starved thermals.
Finish in KiCad (interactive router; a ground via each), refill zones, DRC, before ordering.

Rebuild (from the mainboard folder): `python tools/build.py --variant numpad` (board: `tools/small_board.py`).

## Design

| | |
|---|---|
| Keys | **12 mm four-leg metal snap domes** on gold (ENIG) pads, held by an adhesive dome sheet - not soldered. The chassis model's caps start right on the board (z 9.8 over a board at 8.0-9.6) and its tray panel sits 0.7 mm above it: a 12 x 12 mm tact switch (4.3 mm, tried first) collided by 4-5 mm. Domes are about 0.4 mm tall and rated 1-5 million presses (a tact switch: 100 000). Footprint `lib/commander.pretty/Dome_12mm_4Leg` (centre pad = key, four leg pads = ground), drawn by hand: check it against the dome supplier's drawing |
| Wiring | every key on its own pin, to ground, with the chip's internal pull-ups: no matrix, no diodes, no ghosting |
| Microcontroller | STC8H8K64U-45I-LQFP32 at 5 V - the keyboard's chip: one part number, one firmware tool chain, USB without crystal |
| USB | USB-C 16-pin on the front edge (chassis +X), device side: 5.1 k on CC1 / CC2, USBLC6-2 ESD, 22 ohm series resistors, 500 mA resettable fuse |
| Status LED | D1 (Num Lock), low = on, P0.2 |
| Boot loader | hold key SW_1_1 (on P3.2) while plugging the cable in -> "STC USB Writer (HID1)" in STC-ISP |

Key names: `SW_r_c`, row r = 1 nearest the touchpad module (chassis -Y), column c = 1 at the rear (chassis -X).
The pin of each key is written next to it in `src/netlist/02_np_keys.net`; the firmware reads 24 inputs and sends
keypad codes (the model's legends: 1, 2, 3, 0, 000, %, ( ) * - . are on columns 1 and 4-6; the keymap is a firmware
table).

## Framework-compatible (2026-11-17)

The tray carrier (`../commander_tray`) takes Framework Laptop 16 B-size input modules; this module now fits it the same
way (the touchpad module too):

- **Outline and seat**: Framework's B size, 131.02 x 67.95 mm; in the tray it rests like a Framework module, its rear
  edge under the tray's rear rail (chassis X 8.95-139.97).
- **Contacts J40**: eight 1.5 mm gold pads on the underside, 7.0 mm from the front edge and 16.96 mm from the left
  edge seen from the front - Framework's position (FW_B_SIZE_DESIGN_REF, CC BY 4.0). The footprint
  (`lib/commander.pretty/FW_InputModule_Pads_2x4`) is written by `tools/fw_module_pads.py` from the tray's own pogo
  pins, so pin n meets pad n. Pinout: 1, 7 GND - 2 VCC_5V - 3 USB D- - 4 BOARD_ID - 5 USB D+ - 6 SLEEP# / 8 VCC_3V3 not
  used. Gold (ENIG; hard gold would last longer on a contact that slides in and out).
- **BOARD_ID**: R40, 180 k to ground (Framework's reference value for a generic module); the tray powers a bay only
  while a module holds this pin low.
- **Two supplies, never paralleled**: D40 (BAT54C) OR-s the USB-C's VBUS and the tray's 5 V into the fuse; the data
  lines join the USB-C's ahead of the ESD array (full speed tolerates the short stub).
- **Mechanical, not on the board**: (a) **1.5 mm feet** under the module (Framework's contacts sit 1.5 mm above the
  floor, in a recess of the module; the tray's pogo pins are set for that height) - e.g. four adhesive 1.5 mm feet or
  standoffs at the corner holes; (b) a **steel plate** (0.1-0.2 mm, magnetic stainless or tin-plated steel, insulated
  side towards the board) across the contact zone for the tray's magnets: about 60 x 13 mm along the front edge, with
  10.6 mm windows over the pads and at the mirrored place (Framework's plate has both), the magnets sit 7.9 mm either
  side of each window. Keep the underside in the 14 mm along the front edge free of parts.

## Open points

1. **Connection to the terminal** (2026-11-17): the module now also has **Framework's input-module contacts** - see
   *Framework-compatible* below - so it drops into the tray like a Framework Laptop 16 module, no cable. The USB-C stays
   for any other computer.
2. Domes: pick the supplier (12 mm 4-leg, 250-350 gf) and its dome sheet; the caps press on the dome tops through the
   panel. Switching back to tact switches needs a thicker module.
3. Mounting: four M2.5 holes in the corners (3 mm from the edges).

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
