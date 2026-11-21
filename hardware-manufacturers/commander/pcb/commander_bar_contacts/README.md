# Commander front battery bar - cell-contact board (KiCad 10), revision S0

The front ends of the bar's six cell lanes press against this board; it stands upright on the BMS board's rear edge
(`../commander_bar_bms`, which describes the whole bar: strings, charging, firmware, mechanical items).

| | |
|---|---|
| Size | 75.8 x 8.6 mm, **1.0 mm**, two layers, ENIG |
| Place | chassis X 160.6-236.4, its cell-side face at Y 22.0 (the cells start at Y 23.6), z 6.7-15.3, in the bar's left end cap |
| Cell side (B face) | six plain 6.0 mm ENIG pads on the lanes' axes (lane 1 at z 11.45 down to lane 6 at z 9.96: the extrusion tilts the cells); three 10 k B3950 thermistors (0402) beside the minus pads of lanes 2, 4, 6.  **No copper pour on this face**: a cell can with a damaged wrapper must not find ground there |
| Other face (F) | ground pour |
| Joint | 11 **castellated** half-holes on the bottom edge, soldered to the 11 pads of J3 on the BMS board: STR1_P, NTC1, B_NEG, GND, STR2_P, NTC2, B_NEG, GND, STR3_P, NTC3, B_NEG |

Lanes seen from the front, left to right: 1 = string 1 plus, 2 = string 1 minus, 3 = string 2 plus, 4 = string 2
minus, 5 = string 3 plus, 6 = string 3 minus; the three minus pads are joined here (B_NEG).

Order notes for JLC: castellated holes on one edge; 1.0 mm; ENIG (or hard gold on the six pads for many cell changes).

Review items:
- The router ran two B_NEG links (lane 2 to lane 4, lane 4 to lane 6) on the cell-side face, under solder mask.  Moving
  them to the other face (two vias each) is a few minutes in KiCad and keeps every track away from the cell cans.
- DRC: one "PTH inside courtyard" (lane 5's pad over the castellation of the same net, by design) and two "starved
  thermal" remarks on the ground castellations.

Rebuild: `python ../commander_mainboard/tools/build.py --variant bar_contacts` (board by `tools/small_board.py`,
SPEC "barcon").  Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
