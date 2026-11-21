# Commander battery module (KiCad 10), revision B0

The battery of the Commander: **six standard AAA NiMH cells** (rechargeable, user-replaceable, sold everywhere,
fully recyclable through the usual battery take-back schemes) and the board that manages them. The board is sized
to the battery placeholder of the chassis model `COMMANDER_Z3E.skp` (`Group#56`: the cell tray, 3 columns x 2 cells,
and the 48 x 88.8 mm `BMS#1` board beside it, under the keyboard), and it talks to the mainboard through the
mainboard's battery port `J40`.

**Status (2026-11-16): first generated layout, not reviewed by a person.** Schematic complete (ERC clean), model /
schematic / board identical pad by pad (225 pads), **all 43 signal nets routed** on two layers, ground pours on both
faces stitched together. KiCad DRC: 5 unconnected items, all ground (pads of R35, C30, Q3 and two slivers of pour
that the stitching could not reach - a short track each in KiCad), 4 "starved thermal" remarks. What else is open
is listed in *Before ordering*.

Rebuild (from the mainboard folder): `python tools/build.py --variant battery` (board: `tools/small_board.py`).

## What it does

| | |
|---|---|
| Cells | 6 x AAA NiMH in series: 7.2 V nominal, 6.0 V empty, 9.4 V charge ceiling; about 800 mAh / 5.8 Wh with common LSD cells |
| Output | 4.98 V on the USB-C port (TPS563201 buck, 3 A), on by default, cut off in hardware below 5.8 V (0.97 V per cell) |
| Charging | from the port: the mainboard pushes 5 V in (its `BATT_VBUS_EN`); MT3608 boost, constant current set by the microcontroller (about 0.25 C = 200 mA, gentle on the cells), terminated on temperature rise, voltage and a timer |
| Gauge | 20 mOhm shunt + INA181A1 (both directions), cell voltage, port voltage, two thermistors (one on the cells, one on the board) |
| Host link | USB 2.0 full speed: a HID **Power Device** (UPS class). Linux reads it with the stock `usbhid-ups` / UPower stack |
| Protection | 2 A resettable fuse, P-MOSFET against a reversed cell, ESD array on the data lines, hardware under-voltage cut-off |
| On the board | three charge LEDs and a button (press: show the charge; held while plugging in: firmware update) |

### Why NiMH AAA

The request was standard AAA cells. Lithium cells in AAA size (10440) exist but are not standard, hold less energy
than they claim, and need per-cell protection; alkaline AAA are single-use. NiMH AAA are the standard rechargeable
AAA: safe chemistry, no protection IC per cell, 500-2000 cycles, replaceable by the user one by one, and accepted by
every battery recycling point. The price is energy: six cells give about 6 Wh - roughly half an hour at 10 W. In this
role (riding through PoE outages, a clean shut-down, a short session away from the network) that is the right size;
the front battery bar of the model (42 AAA cells) is the long-runtime option and can reuse this circuit.

### How the UPS works without a switch-over

The buck that feeds the port runs all the time and is set to 4.98 V. It cannot sink current (Eco-mode). While the
mainboard charges the module it holds the port at about 5.15-5.2 V (PoE set point 5.24 V since 2026-11-16); the buck then simply has nothing to do. When the
mainboard's PoE supply goes away, its own 5 V falls, the port voltage drops below 4.98 V and the buck carries the
load from that instant - nothing has to be switched, and the mainboard's TPS2121 selects the port as it was designed
to. The firmware stops charging as soon as it sees the cells' current reverse (the module would otherwise charge
itself from itself).

### The port protocol (needs the mainboard's firmware too)

- By default the module is a **source**: Rp (36 k to 3.3 V on both CC lines) and 5 V on VBUS. A dead mainboard
  (FUSB302 unpowered = Rd) starts from it.
- To charge, the host asks over USB (a HID feature report); the module drops Rp and switches Rd in (`CC_RD`), the
  mainboard's FUSB302 then sees a sink and the SoC may raise `BATT_VBUS_EN`. The module's buck stays on meanwhile.
- **Flat cells:** the microcontroller is powered from VBUS as well as from the cells (BAT54C), but a mainboard that
  only charges a module it can see would never wake a module whose cells are empty. The SoC's policy should be: with
  PoE present and nothing on the battery port for a few seconds, enable `BATT_VBUS_EN` for a moment; the module then
  enumerates and asks for its charge itself.
- Mechanically the module reaches `J40` with a short USB-C to USB-C cable. `J40` is the only battery port: this
  module and the front battery bar cannot both be connected in this revision (see the mainboard's DESIGN_NOTES 5.2b).

## Firmware: pin table of the STC8H8K64U (3.3 V)

| Net | Role | Pin | Port |
|---|---|---|---|
| VBAT_ADC | cell voltage x 33/133 | 1 | P1.0 / ADC0 |
| ISENSE | current: 1.65 V + 0.4 V/A (discharge positive) | 2 | P1.1 / ADC1 |
| NTC_EXT | thermistor on the cells (10 k B3950 to ground, 10 k pull-up) | 3 | P1.4 / ADC4 |
| VBUS_ADC | port voltage x 68/168 | 4 | P1.5 / ADC5 |
| NTC_BRD | thermistor on the board edge beside the cells | 5 | P1.6 / ADC6 |
| ISNS_REF | the current sense's zero (half supply), read for calibration | 6 | P1.7 / ADC7 |
| USB D- / D+ | crystal-less full speed | 13 / 14 | P3.0 / P3.1 |
| BTN_N | button (low = pressed); held at power-up = STC USB boot loader | 15 | P3.2 |
| CHG_EN | charger on (high); 100 k pull-down: off when the chip is off | 21 | P2.0 |
| CHG_PWM | charge current: PWM6 (PWMB), filtered; duty 0 = 9.4 V ceiling, 100 % = 5.0 V (no current) | 22 | P2.1 |
| OUT_OFF | high = 5 V output off (pull-down: on by default) | 23 | P2.2 |
| CC_RD | high = Rd on both CC lines (sink role) | 24 | P2.3 |
| CC_RP | high = Rp on both CC lines (source role); low / input = no Rp | 25 | P2.4 |
| LED1_K..LED3_K | charge LEDs, low = on | 26-28 | P2.5-P2.7 |

Charging rules for the firmware (NiMH): start only between 5 and 40 °C; set `CHG_PWM` to 100 % before `CHG_EN` and
ramp down until the current reaches the set point; stop on dT/dt > 1 °C/min, on -dV of 5 mV per cell, at 45 °C, at
1.55 V per cell, or after 1.5 x the capacity in charge; never leave `CHG_EN` high with the PWM at 0 for more than a
control period (use the watchdog). Below 1.0 V per cell under load switch the output off.

## Before ordering

1. **Routing**: the 5 ground items of `build/drc.rpt` need a person in KiCad (a few minutes), and the layout as a whole
   a review (the power stage - buck and boost loops - was placed by hand but routed by the script).
2. **Holder**: the cell holder / contacts and their harness to J1 (JST PH, B+ on 1-2, B- on 3-4) are not designed.
   The 2 A per contact and 22-24 AWG wire are enough for 2 A.
3. **Heat**: the cells sit on the heatsink plate in the model. NiMH ages fast above 45 °C; measure the plate under
   load. The firmware refuses to charge above 40 °C, but a warm resting place still costs cycle life.
4. **Height**: J1 / J2 are vertical PH connectors (6 mm); check them against the keyboard's underside, or use the
   side-entry versions (S4B-PH-K / S2B-PH-K).
5. **Values to confirm on the bench**: TPS563201 EN threshold (the cut-off divider), the boost's control range,
   the INA181's offset at 0 A.

## Parts (LCSC)

TPS563201DDCR C116592, MT3608 C84817, HT7333-A C347191, INA181A1IDBVR C2058943, STC8H8K64U-45I-LQFP32 C5210757,
USBLC6-2SC6 C2827654, HOAUC HYCW498 USB-C C42400252, JST B4B-PH-K-S C131334; passives, AO3401A, 2N7002, SS34,
BAT54C, the 1812 PTC and the B2B-PH-K-S by JLC's BOM matcher. BOM: `../../fabrication/bom/commander_battery_revB0_bom.csv`.

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
