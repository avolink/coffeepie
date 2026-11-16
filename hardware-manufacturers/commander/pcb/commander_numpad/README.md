# Commander numpad module (KiCad 10), revision N0

One of the two modules of the Commander's sliding tray (`NUMPAD_MODULE` of the chassis model `COMMANDER_Z3E.skp`,
131 x 68 mm, 8 mm thick): **24 keys** in the model's grid (6 across at 17.0 mm, 4 down at 17.5 / 17.5 / 18.0 mm,
12 x 12 mm caps), a microcontroller and a USB-C. It is a USB keyboard (keypad usage page) of its own, so it also
works on any other computer.

**Status (2026-11-16): first generated layout, not reviewed by a person.** ERC clean, model / schematic / board
identical, **all 35 signal nets routed**, ground pours stitched. KiCad DRC: 3 unconnected items (ground pads / pour
slivers the stitching could not reach), one dangling track and via, one starved thermal - minutes in KiCad.

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

## Open points

1. **Connection to the terminal**: the USB-C sits on the module's front edge; with the tray pulled out a short cable
   goes to a bay. A dock contact in the tray (pogo pins to the hub) would avoid the cable - not designed.
2. Domes: pick the supplier (12 mm 4-leg, 250-350 gf) and its dome sheet; the caps press on the dome tops through the
   panel. Switching back to tact switches needs a thicker module.
3. Mounting: four M2.5 holes in the corners (3 mm from the edges).

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
