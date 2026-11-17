# Commander front battery bar - BMS board (KiCad 10), revision S0

The front battery bar of the chassis model `COMMANDER_Z3E.skp` (the aluminium bar with the solar cover, 42 AAA cells
in six lanes of seven) gets its electronics from two boards:

| Board | Project | What it is |
|---|---|---|
| **BMS board** | this folder | 75.8 x 18.4 x 1.6 mm, four layers (In1 = ground plane), parts on both faces; lies flat in the bar's **left end cap**, in front of the cells |
| **Cell-contact board** | `../commander_bar_contacts` | 75.8 x 8.6 x 1.0 mm; stands upright on the BMS board's rear edge, facing the six lanes; plain ENIG pads the cells press against, three thermistors; soldered to the BMS board by 11 castellated pads (joint J3 here, J1 there) |

Rebuild (from the mainboard folder): `python tools/build.py --variant bar_bms` and `--variant bar_contacts`
(boards: `tools/small_board.py`, SPECs "bar" and "barcon").  Status: see *State* at the end.

## Why the BMS is in the bar, not in the terminal

The terminal only ever sees what its battery port J40 already expects: a protected ~5 V, USB 2.0 and a CC line -
the same as the internal 6 x AAA module (`../commander_battery`).

- **Safety**: 42 cells are about 40 Wh at 14-22 V.  With the electronics in the terminal, the bar's contacts would
  carry the raw pack whenever the bar is off the terminal.  With the BMS inside, the bar's port is dead until
  something asks for power (and only ever 5 V).
- **Modularity**: the terminal does not care about chemistry or cell count; the bar works on its own as a power bank
  (USB-C on its end), and the internal module, this bar or a later lithium bar all look alike to the terminal.
- **Solar**: the panel is on the bar; its charger belongs next to it and the cells.
- **Gauge travels with the cells**: the bar knows its own charge, temperature and cycles.

## Cells and strings

- 42 x AAA **NiMH** (low self-discharge, 750-800 mAh): **three strings of 14 in series** (16.8 V nominal, 14.0 V
  empty, about 21.7 V at the end of a charge), about **40 Wh**, roughly 3-3.5 h at 10 W after the converter.
- Lanes 1-6 seen from the front, left to right (chassis +X).  A string = two neighbouring lanes joined at the bar's
  **rear** end: lane 1 + 2, 3 + 4, 5 + 6.  So both ends of every string are at the front, on the contact board:
  lanes 1 / 3 / 5 bring the strings' plus, lanes 2 / 4 / 6 their minus (joined: B_NEG).
- The strings are **never paralleled**:
  - *discharge*: each string's plus through its own Schottky (D11-D13) to VBAT, so the fullest string carries the
    load and a weaker string is never charged by the others;
  - *charge*: one charger, switched to **one string at a time** (P-MOSFET Q11-Q13 + diode D21-D23), time-sliced by
    the microcontroller, so each string gets its own end-of-charge detection.
- The rear end needs no electronics: three link straps, each with a long conical spring, in the rear end cap (see
  *Mechanical items*).

## What the board does

| | |
|---|---|
| Output | 4.96 V on VBUS (TPS54302 buck, 4.5-28 V in, 3 A), on by default, Eco-mode (never sinks current); hardware cut-off below about 13.3 V of the fullest string (0.95 V per cell); the firmware can switch it off (OUT_OFF) |
| Ports | **J1** USB-C (16-pin) on the bar's left end face: charger input, power-bank output, or a cable to the terminal's J40.  **J4** dock harness (JST PH 5: VBUS, D+, D-, CC, GND) to the docking contacts on the bar's rear face (the model's INPUT_MODULE_CONNECTOR), so the bar powers the terminal when clipped on.  Both in parallel: use one at a time |
| UPS behaviour | as the internal module: the buck sits just under the terminal's own 5 V and takes over the moment it goes away, without a switch-over |
| Charging | MT3608 boost from CHG_IN to up to 21.8 V; CHG_IN = the port's VBUS (through Q5 - only when the firmware switches it in, so the bar never charges itself from its own output) or the solar panel (J5), each through a Schottky.  Constant current set by the firmware (filtered PWM into the boost's feedback node), measured on R6 / U8 (1 V/A); hardware ceiling 1.53 V per cell |
| Solar | J5 (JST PH 2): a 5-7 V class panel (open-circuit voltage below 13 V); maximum power tracking in firmware by maximising the charge current (the string's voltage barely moves, so current = power) |
| Gauge | pack current both directions on a 20 mOhm shunt + INA181A1 (B_NEG side), each string's voltage, three thermistors, port and panel voltage |
| Host link | USB 2.0 full speed, HID **Power Device** (UPS class), as the internal module - the terminal's software reads either the same way |
| Protection | 2 A resettable fuse in the strings' common minus, diode-OR (a reversed string blocks itself), ESD array on the data lines, no charging without the microcontroller (boost EN and every string switch pulled off) |
| Indication | three LEDs and a side button on the board's front edge (light pipes / plunger through the end face) |

## Firmware: pin table of the STC8H8K64U (3.3 V)

| Net | Role | Pin | Port |
|---|---|---|---|
| VSTR1_ADC / VSTR2_ADC / VSTR3_ADC | string voltage x 150/1150 (22 V -> 2.87 V); 1 M top resistor = 19 uA per string | 1 / 2 / 7 | P1.0 / P1.1 / P1.3 (ADC0, 1, 3) |
| IPACK | pack current: REF + 0.4 V/A, discharge positive | 3 | P1.4 / ADC4 |
| ICHG | charge current: 1 V/A from 0 | 4 | P1.5 / ADC5 |
| VBUS_ADC | port voltage x 68/168 | 5 | P1.6 / ADC6 |
| SOLAR_ADC | panel voltage x 33/133 | 6 | P1.7 / ADC7 |
| NTC1 / NTC2 / NTC3 | thermistors beside the minus pads of lanes 2 / 4 / 6 (10 k B3950 to ground, 10 k pull-up) | 29 / 30 / 31 | P0.0 / P0.1 / P0.2 (ADC8-10) |
| ISNS_REF | the pack current's zero (half supply), for calibration | 32 | P0.3 / ADC11 |
| USB D- / D+ | crystal-less full speed | 13 / 14 | P3.0 / P3.1 |
| BTN_N | button (low = pressed); held at power-up = STC USB boot loader | 15 | P3.2 |
| CHG1_EN / CHG2_EN / CHG3_EN | high = the charger feeds string 1 / 2 / 3 (100 k pull-downs) | 16 / 17 / 18 | P3.3 / P3.4 / P3.5 |
| USB_CHG_EN | high = the port's VBUS feeds the charger (only while the bar is the sink) | 19 | P3.6 |
| CHG_EN | boost on (high) | 21 | P2.0 |
| CHG_PWM | charge set point: PWM6 (PWMB), filtered; duty 0 = 21.8 V ceiling, 100 % = 11.8 V (no current) | 22 | P2.1 |
| OUT_OFF | high = 5 V output off | 23 | P2.2 |
| CC_RD / CC_RP | port role (as the internal module) | 24 / 25 | P2.3 / P2.4 |
| LED1_K..LED3_K | fuel LEDs, low = on | 26-28 | P2.5-P2.7 |

Charging rules (NiMH): start a string only between 5 and 40 °C; `CHG_PWM` at 100 % before `CHG_EN` and before a
string switch closes, then ramp down to the set point (0.25 C = 200 mA, or what the panel gives); one string at a time
(e.g. 2 s slices, or one string to the end then the next); stop a string on -dV of 5 mV per cell (70 mV per string,
read with the charger paused for a few ms), on dT/dt > 1 °C/min, at 45 °C, at 1.53 V per cell, or after 1.5 x its
capacity; never leave `CHG_EN` high with the PWM at 0 for longer than a control period (watchdog).  `USB_CHG_EN` only
while the port is in the sink role (Rd on).  Below 1.0 V per cell on every string switch the output off.

## Mechanical items (for the chassis model - not changed by me)

1. **Left end cap**: the BMS board sits on two **1.5 mm spacers** on the cap's floor plate (M2 screws at board
   (2.4, 9.5) and (73.4, 15.6)), board X 160.6-236.4, Y 3.6-22.0, top at z 6.7; parts under it are 1.3 mm at most.
   The end face needs an opening for the USB-C (centred at X 202.6, z about 8.3), two for the light pipes / button
   (X about 220-232).  The dock harness J4 runs to the rear face (X 152.7): the INPUT_MODULE_CONNECTOR spot.
   The through-hole leads of J1 (USB-C shell pegs), J4 and J5 (JST PH) stand 1.8 mm out of the underside as
   delivered: **trim them to 1.2 mm** after soldering (assembly note), or they touch the cap's floor.
2. **Contact board**: its face toward the cells is at Y 22.0, the cells start at Y 23.6; the **rear springs push
   every lane forward** against its pads.  That force (7 cells' worth per lane) must be taken by a rib of the cap
   behind the contact board's top edge, not by the solder joints.
3. **Rear end cap**: three link straps (lane 1 rear to lane 2 rear, 3 to 4, 5 to 6), each a nickel-plated strip
   with a **conical spring with at least 8 mm of travel**: seven AAA cells measure 304.5-311.5 mm end to end
   (43.5-44.5 mm per cell).  In the model the cells end at Y 331.8 and the cap's inner wall is 4 mm behind them -
   it needs about 8-10 mm.
4. **Under the cells**: the extrusion's board slot (z 2.9-3.9) is split by the centre web (X 197.4-199.3) and has
   about 1 mm of room above it, so no electronics go there; the slot can take a plain bottom plate.
5. **Solar panel**: the model's five 52 x 52 mm cells are about 135 cm2 of silicon, 2-2.7 W in full sun.  Wire them
   for a maximum-power voltage of 5-6 V (five two-cell mini panels in series, or a laminated panel with 10-12 cells in
   series) - a single 0.5 V cell per square would give 2.5 V, too low for the boost's duty-cycle limit.

## State

2026-11-16:

- **Contact board**: placed and routed; consistent with the schematic, ERC clean, DRC: 0 unconnected, one
  pth_inside_courtyard (same net, by design: the castellations), two starved thermals.  Review item: two B_NEG
  tracks run on the cell-facing side; move them to the other face.
- **BMS board**: four layers (F, In1 ground plane, In2 signals, B), all 118 parts placed (15 by hand, 103 packed; the
  low passives and SOT-23 / SOD-123 parts on the underside).  Consistent with the schematic (328 pads), ERC clean, DRC
  no shorts or clearance errors (10 starved thermals, 3 dangling stubs) - but **routing is not finished**: the
  scripted router completed 46 of 75 nets (8 passes + 16 repair rounds); 29 nets / 81 links are open, mostly around the
  three string switches (Q1x / D2x), the boost (U4 / L1 / D1) and the USB / CC lines between J1, U2 and the
  microcontroller.  This board is dense for its 75.8 x 18.4 mm and needs a person in KiCad (rip up the partial
  routes in those areas and route the power paths first, by hand); the placement itself has room.
- 3D: `3d-models/pcb_exports/commander_bar_bms.{glb,step,dae}` and `commander_bar_contacts.{glb,step,dae}`.
- Fabrication outputs: `fabrication/bom/commander_bar_{bms,contacts}_revS0_bom.csv`, placement files and assembly
  drawings in `fabrication/position/`, schematics in `schematics/`.
