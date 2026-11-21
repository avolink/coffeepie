# commander_cpu_ram — a minimal RK3566 single-board computer (processor, LPDDR4, eMMC, power, ports)

Status (2026-11-18, revC0): **KiCad DRC 0 violations; 27 connections still open, all in the power section** (list
below — for KiCad's interactive router). Not ready to order: besides those, lengths are not matched, the strobe /
clock pairs are only partly coupled, and track widths are not impedance-calculated.

What started as a routing study for the memory bus (the mainboard never got it past 40-52 of 73 nets) is now the
smallest board that boots on its own bench: power in, flash the eMMC over USB, see it on a monitor, type on it.

## What is on it

| | |
|---|---|
| U1 | Rockchip RK3566, FCCSP-565 (all 565 balls; 2 unused) |
| U10 | LPDDR4 200-ball, 1 GB (Samsung K4F8E3S4HD-MGCL), turned 90° above the processor |
| U20 | eMMC 5.1, 8 GB (Samsung KLM8G1GETF-B041, 153-ball 0.5 mm) beside the memory (no eMCP: LCSC has none) |
| U9 | RK817 PMIC: VDD_LOGIC, VDD_GPU_NPU, VCC_DDR, VCC3V3_SYS bucks, the 5 V boost for HDMI, all the LDOs |
| U3 | RK860 buck for VDD_CPU |
| Y1, Y6 | 24 MHz (processor), 32.768 kHz (PMIC) |
| J95 | **power USB-C** (sink: 5.1K Rd on CC, any USB-C charger gives 5 V) |
| J2 | **flashing USB-C** (USB 2.0 OTG0, rockusb / Maskrom; it can power the board too) |
| J96 | **USB host USB-C** (HOST2, USB 2.0, 1 A switch SY6280, 56K Rp): keyboard + mouse through a splitter / hub |
| J10 | **micro-HDMI** (HDMI 2.0 TX, ESD, DDC level shifter, 5 V) |
| J21 | 3.3 V debug UART (JST-SH 4) |
| SW3 / SW2 / SW1 / SW95 | power (side button on the left edge), reset, recovery, **Maskrom** (grounds the eMMC clock at power-up) |
| LED1 | status |

No video over USB-C: the RK3566 has no DisplayPort (HDMI 2.0, eDP, MIPI-DSI, LVDS only).

The circuit is the mainboard's own wherever it can be: sheets 04-09, 11-13, 15 (HDMI), 17 (PMIC), `21_emmc.net`,
`22_power_core.net` (5 V into VCC_SYS, flashing port J2, switched 3.3 V, RK860) and `23_service.net` (debug header,
buttons, LED) come in unchanged through `src/netlist/shared.txt`. 21 / 22 / 23 were split out of the mainboard's
05 / 18 / 19 for this; the parts keep their sheets there and the mainboard's design model is byte-for-byte the same.
Only `src/netlist/40_board_io.net` is this board's own (power port, host port, Maskrom button). The processor's other
interfaces (Ethernet MAC, microSD, USB 3, I2C2/3 headers) are on balls with nothing on the other end here: the 34
`isolated_pin_label` ERC warnings.

## Board

- 39.5 × 59 mm, 10 layers, 1.6 mm (JLC 10-layer class).
- Top half: memory (left) and eMMC (right) above the processor. Bottom half: the RK817 centred under the processor,
  turned so its bucks 1 / 2 face up into the processor's centre (L17, L19), buck 3 left (L20), 4 / 5 right (L18, L21);
  RK860 + L2 to the right; the three USB-C on the bottom edge (host, power, flashing from left to right), micro-HDMI
  on the right edge next to the processor's HDMI balls, debug header and power button on the left edge.
- Stack-up:

  | layer | use |
  |---|---|
  | F.Cu | signal (escapes, short runs, the power stage) |
  | In1 | GND |
  | In2 | signal |
  | In3 | GND |
  | In4 | signal |
  | In5 | VCC_DDR (memory, DDR corner, down the left side to L20) · VDD_CPU (processor corner, down the right side to the RK860) · VCC_SYS (5 V, the power section) |
  | In6 | VCC0V6_DDR · VDD_LOGIC (processor centre, down to L17) |
  | In7 | signal · VDD_GPU_NPU under the processor and down to L19 (kept out of the router) |
  | In8 | GND |
  | B.Cu | signal · decoupling |

- Rules: 0.09 mm space everywhere (the project's net classes say so too). Signals and small supplies 0.09 mm tracks,
  via 0.25 / 0.15; the 5 V paths and buck switch nodes 0.25 mm, via 0.45 / 0.20. **Every via in a pad must be filled
  and capped** (JLC "via in pad / POFV", free on 6+ layers). The small supplies (PMIC LDOs, IO domains, VCC_3V3, the
  eMMC's VCCQ) are routed as 0.09 mm tracks: fine for their tens to hundreds of mA, but widen what you can by hand.

## How it is built

`tools/cpu_ram_board.py`, search core `tools/cr_astar.c` (compiled on the fly with the gcc of Qt's MinGW; `CP_GCC`
otherwise). Stages:

1. `place` — outline, the three packages, a via in every supply / ground ball.
2. `route` — **pass 1**: memory bus + eMMC (+ ZQ / RZQ / RESET_n / 1.8 V of the memory), negotiated congestion
   (PathFinder) on a 0.025 mm grid over five signal layers. 73 / 73 + 14 / 14 in about 20 s.
3. `place2` — the power section and the ports by hand (`power_parts()`), every other part by a packer: as near the pads
   of what it connects to as the copper of pass 1 allows (capacitors on the bottom, a via in each supply pad that lands
   on that supply's plane; a ring around the RK817 / RK860 kept free for their pin fan-out; footprint keep-outs honoured).
4. `wide` — **pass 2**: the 5 V paths and switch nodes at 0.25 mm.
5. `rest` — **pass 3**: everything else at 0.09 mm (with the earlier passes as walls).
6. `finish` — the planes, zone fill.

`python ../commander_mainboard/tools/build.py --variant cpu_ram` runs all of it (about 30 minutes, pass 3 is most of it)
and the checks / exports; `--keep-board` only the checks and exports. Once someone routes by hand, use `--keep-board`.

## Result (`build/ddr_report.txt`, `build/drc.rpt`)

| | |
|---|---|
| memory bus | 73 / 73 nets |
| eMMC | 14 / 14 nets |
| power section and ports, 0.25 mm pass | 16 / 17 nets (open: PMIC_SW5, the 5 V boost's switch node) |
| everything else, 0.09 mm pass | 112 / 119 nets |
| KiCad DRC | 0 violations, 27 unconnected items |

Still open (for KiCad's interactive router — all in the crowded strip around the RK817):
PMIC_SW5 (pin 53 to L21), HDMI_TX0P_PORT, PDM_CLK0_M0_PMIC, PMIC_SLEEP_H, UART2_TX_3V3, VCC1V8_DVP, VCC2V8_DVP; and the
plane vias of the VDD_GPU_NPU pads, C6 / C8 / C9 (VDD_LOGIC), the RK817's pins 13 (VDD_LOGIC sense), 22 (VCC_SYS) and
26 (VCC_DDR sense).

## Not done (next steps)

1. The 27 open items above.
2. **Length matching** of the memory bus (byte lanes to their strobe, command / address to the clock; Rockchip's RK3566
   guide gives the tolerances) and of the eMMC; KiCad's length tuning. Then the **strobe / clock pairs** as coupled
   pairs, and the **impedance** widths from JLC's 10-layer stack-up calculator.
3. The power stage deserves a look by a person against the RK817 / RK860 data sheets (input capacitors right at the VIN
   pins, switch-node loops): the capacitors are on the bottom face with vias, the packer put them near, not tight.
4. Silkscreen: the bottom names are on B.Fab only.
