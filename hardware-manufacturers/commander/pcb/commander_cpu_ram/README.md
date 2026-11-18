# commander_cpu_ram — the RK3566, its LPDDR4 and its eMMC on a board of their own

Status (2026-11-18, revC0): **the memory bus and the eMMC are fully routed and KiCad's DRC is clean** (0 violations,
0 unconnected),
but the board is a **routing study, not ready to order**: lengths are not matched yet, the strobe / clock pairs are only
partly coupled, and the board has no way in for its supplies (see "Not done" below).

On the mainboard the memory bus never got further than 40-52 of 73 nets: the two packages are less than 1 mm apart and
there are only two inner signal layers for it. Here the two chips get the room and the layers the bus needs.

## What is on it

| | |
|---|---|
| U1 | Rockchip RK3566, FCCSP-565, all 565 balls (the 261 that this board does not use are NC: `src/netlist/90_soc_unused.net`) |
| U10 | LPDDR4 200-ball FBGA (Samsung K4F8E3S4HD-MGCL, 1 GB), turned 90°: channel A on the left, channel B on the right |
| R1, R120, R121 | DDR PHY RZQ, memory ZQ0 / ZQ1 (240R 1 %) |
| R123, C204-C207 | the memory's VDD1 (1.8 V) from VCCA1V8_PMU, along the memory's far side |
| C159 (DNP) | on the memory's RESET_n |
| U20 | eMMC 5.1, 153-ball FBGA 0.5 mm (Samsung KLM8G1GETF-B041, 8 GB — the mainboard's part; no eMCP: LCSC has none), turned 90° beside the memory |
| R401 (by the processor's clock ball), R402-R404, C405, TP3 | eMMC clock series 22R, CMD / RST_n pull-ups, DS pull-down, VDDI, clock test point |
| 65 capacitors, R68 (DNP), R69, R122 | decoupling of VCC_DDR, VCC0V6_DDR, the core rails, VCC_3V3 and VCCIO_FLASH, on the bottom face, a filled-and-capped via in every pad |

The circuit is the mainboard's own: sheets 11 (DDR PHY), 12 (processor supplies), 13 (LPDDR4) and `21_emmc.net` (eMMC
+ the processor's VCCIO_FLASH domain) come in unchanged through `src/netlist/shared.txt`, so a change there reaches both
boards. (`21_emmc.net` was split out of the mainboard's 05 / 19 for this; the parts keep their sheets there, and the
mainboard's design model is byte-for-byte the same.)

## Board

- 39.5 × 39.5 mm, 10 layers, 1.6 mm (JLC 10-layer class).
- Processor at (19.25, 27.2), memory centre at (12.25, 10.0); 5 mm between the memory's long side and the processor's top
  edge; eMMC centre at (28.0, 10.0), 2 mm right of the memory, its signal corner facing the processor's eMMC balls
  (right half of its top edge). `CR_GAP`, `CR_MEM_DX`, `CR_EMMC_GAP` in the environment move them for experiments.
- Stack-up:

  | layer | use |
  |---|---|
  | F.Cu | signal (the escapes from both packages, short runs) |
  | In1 | GND |
  | In2 | signal |
  | In3 | GND |
  | In4 | signal |
  | In5 | VCC_DDR (memory + DDR corner of the processor) · VDD_CPU · VCC_3V3 (eMMC) |
  | In6 | VCC0V6_DDR (same area) · VDD_LOGIC · VCCIO_FLASH (eMMC, down to the processor's ball 1C13) |
  | In7 | signal · VDD_GPU_NPU under the processor (kept out of the router) |
  | In8 | GND |
  | B.Cu | signal · decoupling capacitors |

- Rules (DDR class): 0.09 mm track, 0.09 mm space, via 0.25 / 0.15 mm everywhere, hole to copper 0.195 mm,
  hole to hole 0.25 mm. **Every via in a ball is a via in pad and must be filled and capped** (JLC: "via in pad /
  POFV", free on 6+ layers).

## How the bus was routed

`tools/cpu_ram_board.py` (stages netlist / place / route / finish), search core in `tools/cr_astar.c` (built on the fly
with the gcc that comes with Qt's MinGW; set `CP_GCC` if it lives elsewhere).

- 0.025 mm grid: the 0.65 / 0.40 / 0.80 pitches and the 0.325 mm mid-points between balls all fall on it, so a track
  passes between two 0.65 mm-pitch vias with its exact 0.315 mm clearance to each hole.
- A via in every supply / ground ball first. The ground balls on the processor's 0.40 mm outer ring in the memory
  corner are left free: Rockchip put them in the gaps of the ring, and they may leave on the top face.
- All 73 bus nets, RZQ, ZQ0 / ZQ1, RESET_n and the 1.8 V net are then routed together with negotiated congestion
  (PathFinder): every net takes its cheapest way through all five signal layers, cells used by several nets get dearer
  each round, until no two nets share a cell. 24 rounds, 16 s.
- A strobe or clock half is drawn towards its partner's route (pairs end up mostly side by side, on the same layer).
- Then each track is straightened against its final neighbours and written to the board; KiCad's DRC is the check.

Result (`build/ddr_report.txt`):

| group | complete | length range (mm) | spread (mm) | vias |
|---|---|---|---|---|
| A byte 0 | 11 / 11 | 9.81 – 16.25 | 6.44 | 0–3 |
| A byte 1 | 11 / 11 | 18.62 – 23.03 | 4.41 | 0–3 |
| A command / address / clock | 13 / 13 | 8.61 – 17.34 | 8.73 | 0–2 |
| B byte 0 | 11 / 11 | 8.01 – 10.77 | 2.76 | 0–3 |
| B byte 1 | 11 / 11 | 13.08 – 16.45 | 3.38 | 0–3 |
| B command / address / clock | 13 / 13 | 6.99 – 16.33 | 9.33 | 0–2 |

| eMMC (D0-D7, CMD, CLK, DS, RST_n, VDDI) | 14 / 14 | 1.6 – 18.7 | — | 0–4 |

Pair skew (P vs N) varies a little from build to build (the router's result is deterministic for a given input, but any
change of input moves it): about 0.2–0.6 mm for the strobes, 1.4–1.5 mm for the clocks — see `build/ddr_report.txt`.
The eMMC (HS200, 200 MHz) is far less sensitive than the memory; its data lines are 8.5–10.4 mm, CMD 19 mm, CLK 18 mm
(it also feeds TP3).

A supply pad's via may only land inside its own plane piece (the router checks), and a series resistor goes next to the
pin that drives it.

## Not done (next steps, in order)

1. **Length matching.** Every byte lane to its strobe, every command / address line to its clock, within Rockchip's
   tolerance for LPDDR4 (their RK3566 hardware design guide / reference layout gives the numbers). KiCad's interactive
   length tuning (serpentines) on the short members; the 5 mm gap and the area left of the processor leave room for it.
2. **Pairs.** DQS1_A / DQS1_B / CLK_B change layer differently on their two halves, and parts of every pair run apart:
   re-route them as coupled pairs (KiCad's differential-pair router) once the lengths are set.
3. **Impedance.** 0.09 mm is the fabricator's minimum, not a calculated width: derive the 40 Ω / 80 Ω widths from JLC's
   10-layer stack-up calculator and widen where it asks.
4. **Supplies.** The board has no connector: VCC_DDR, VCC0V6_DDR, VCCA1V8_PMU and VCC_1V8 (the two ERC warnings: their
   labels have only R123 / R69 on them), VDD_CPU, VDD_LOGIC, VDD_GPU_NPU, VCC_3V3 come from the PMIC / RK860 on the
   mainboard. The eMMC's matching (CMD / data to CLK) is also still to do. To make it a real module it
   needs a board-to-board connector (or the PMIC on board) and the processor's other interfaces brought out — a design
   decision for later.
5. Silkscreen: the bottom capacitors' names are on B.Fab only (no room between the vias).

## Build

```
python ../commander_mainboard/tools/build.py --variant cpu_ram              # everything, about 2 minutes
python ../commander_mainboard/tools/build.py --variant cpu_ram --keep-board # only the checks and exports
```

Writes ERC / DRC reports to `build/`, the schematic PDF to `commander/schematics/`, the placement file to
`commander/fabrication/position/` and the BOM to `commander/fabrication/bom/`. Once someone edits the board by hand, stop
regenerating it (a rebuild overwrites hand routing) and use `--keep-board`.
