# Commander mainboard — design notes, revision A0

Codec Terminal, model **Commander**: the Radxa ZERO 3E (RK3566), its PoE HAT and a USB hub for
nine Framework expansion-card bays, fused onto one coplanar L-shaped PCB that is fabricated in
the same panel as the keyboard.

**Status: schematic complete and electrically checked; board placed, not routed.**
This revision exists to be audited. Nothing here has been built or powered.

## 1. What is on the board

| Block | Parts | Origin |
|---|---|---|
| SoC, DDR, PMIC | RK3566, LPDDR4 200-ball, RK817-5, RK860-0 | Radxa ZERO 3E V1.2, unchanged |
| Ethernet | RTL8211F-CG, 4 discrete LAN transformers + chokes, sunk RJ45 | Radxa, unchanged |
| Video | HDMI 2.0, micro HDMI (type D) | Radxa, unchanged |
| PoE | TPS23754 PD + isolated 5 V flyback, 802.3at class 4 | **new** (replaces the PoE HAT) |
| USB 3 | USB5744, bays 1–4 at 5 Gb/s | **new** (replaces the single Type-C USB3 port) |
| USB 2 | USB2517, bays 5–9, one spare internal port | **new** |
| Keyboard link | USB2 HOST3 straight from the SoC, JST-SH 4-pin | **new** (HOST3 is unused on the 3E) |
| Storage | eMMC 153-ball **and** microSD | eMMC **new**; microSD from Radxa, relocated |
| Service | USB-C (USB2 OTG, flashing), 3.3 V UART header, recovery and reset buttons, ID EEPROM | adapted / new |

639 components, 469 nets, 17 schematic sheets.

Removed relative to the 3E: 40-pin header, MIPI CSI connector, Type-C USB3 port with its mux
and CC controller (CH482D, ET7301B, SY6280), the PoE pick-off through the mounting posts.

## 2. How the reference design was carried over

The Radxa schematic is published as a PDF only, so it was transcribed sheet by sheet into
`src/netlist/04…19_*.net`. Component references are kept (R25 is still R25) so the two can be
compared line by line. Three independent checks protect the transcription:

1. **Every RK3566 ball is accounted for.** The netlist assigns exactly 565 balls, the package count.
2. **The ball map matches Radxa's own board.** The footprint was generated from the ball names
   and then compared with the 565 pad positions in Radxa's placement drawing: 565 of 565
   coincide, in exactly one of the eight possible orientations.
3. **Model, schematic and board agree.** `tools/check_consistency.py` compares all 2,736 pads
   three ways (netlist source, the netlist KiCad exports from the schematic, the pads on the
   board): 0 differences. KiCad ERC: 0 violations.

What those checks do *not* prove: that a value or a net name was read correctly off the PDF.
A second pair of eyes over sheets 4–19 against the Radxa PDF is the single most valuable audit step.

## 3. Decisions taken (and why)

**USB topology.** The RK3566 has one USB3 host, so SuperSpeed needs a hub. USB3 HOST1 feeds the
USB5744 (bays 1–4). The USB2517 hangs off USB2 HOST2 rather than behind the USB5744, so slow
peripherals do not share a root port with the fast ones and no device sits two hubs deep.
The keyboard gets its own root port (HOST3) and works even if a hub is misconfigured.
USB2 OTG stays a dedicated service port: RK3566 can only be flashed in maskrom/rockusb through it.

**Bays 1–4 are the SuperSpeed ones** because they are nearest the SoC; 5 Gb/s pairs to bay 4 run
about 120 mm, to bay 9 they would run 280 mm.

**No orientation mux on the SuperSpeed bays.** A Framework card only seats one way, so each
bay wires a single lane and saves a mux and CC controller per port. Which lane depends on how
the chassis seats the card, so both lanes have footprints: default stuffing is lane 1; move four
0402 parts to the DNP positions for lane 2. *Consequence:* a plain USB-C cable plugged in upside
down falls back to USB 2.0.

**No CC logic.** Each bay has fixed 56 kΩ Rp pull-ups (default USB current) and VBUS switched by
its hub port with over-current reporting. This is enough for Framework cards and ordinary
peripherals; it is not a compliant Type-C source (VBUS is not cold) and it cannot do USB-PD.

**The hubs do not load the SoC's 3.3 V rail.** They get their own 3.3 V and 1.2 V bucks from 5 V.

**PoE: 802.3at, isolated.** Isolation is mandatory because USB shells and HDMI are user-accessible.
Class 4 (25.5 W at the PD, roughly 21 W at 5 V) was chosen over class 3 because nine bays on
13 W leaves about 1.2 A for all peripherals together. Both PoE alternatives are rectified
(the 3E only wires the data pairs). TPS23754 was chosen because TI documents this exact
application; it is used in its simplest form (diode rectifier, optocoupler feedback).

**eMMC added, microSD kept.** The published 3E schematic leaves the eMMC bank unpopulated and
boots from microSD; the Commander spec calls for 16 GB eMMC. Both are fitted on revision A0 so
the board can be brought up from a card before eMMC boot is proven. The eMMC takes the place the
microSD socket had under the PMIC (bottom side); the socket moves to the strip between bays 1 and 2.

**Video stays on micro HDMI.** A full-size HDMI receptacle (15 mm) does not fit beside the RJ45
(16 mm) on a 30 mm column.

**Core placement is Radxa's.** Positions, sides and package sizes of the SoC, DDR, PMIC and their
passives were recovered from Radxa's placement drawings and rotated into the column, so the
proven DDR and power floorplan is the starting point rather than a guess.

## 4. Assumptions you should confirm

Mechanical values not on the drawing were derived; each is a named constant in `tools/gen_pcb.py`.

| # | Assumption | Basis |
|---|---|---|
| A1 | Bay strip starts **11.30 mm** below the top of the column | scaled from the image, ±0.5 mm |
| A2 | Rear panel plane is **20.6 mm** behind the column top | where the RJ45 block ends in the drawing; consistent with a 32 mm card behind the strip |
| A3 | The column grows a **rear tab** (14.2 mm under the RJ45, 19.6 mm under the HDMI) | the drawing shows the RJ45 floating off the board; a jack needs board under it. This makes the panel taller than 170.05 mm |
| A4 | The RJ45 is the **sunk low-profile type** Radxa uses, in a board notch | keeps the height of the reference design |
| A5 | Board is **6-layer, 1.2 mm** | RK3566 escapes on a standard 6-layer; thickness not specified |
| A6 | Mounting holes | **provisional**, positions belong to the chassis |
| A7 | Keyboard connects by **USB 2.0** on a 4-pin JST-SH | the keyboard interface was not specified |
| A8 | Component height is unconstrained | **not true for the transformer — see 5.2** |

## 5. Audit list, most important first

### 5.1 Not routed
Routing an RK3566 with LPDDR4, HDMI 2.0 and USB3 is skilled manual work. Net classes with
starting dimensions are in the project file; impedances must be recalculated for the real stack-up.
The first placement still has **109 pad-level conflicts** and about 420 courtyard-only overlaps
(`build/overlaps.txt` lists them). Most courtyard overlaps are benign: stock KiCad courtyards
overlap at Radxa's 0201 density. The pad conflicts are parts whose position could not be
recovered exactly, plus the service USB-C, whose footprint is larger than Radxa's.

### 5.2 The PoE converter is a first pass
- **Transformer height.** A 30 W flyback transformer of the usual EP13 class is about 12.7 mm tall.
  If the chassis cannot take that, the alternatives are a planar transformer or dropping to 802.3af.
- Transformer part and pin-out are placeholders; current sense, clamp, bias and loop compensation
  are textbook starting values. They need a bench validation or the values of the chosen
  transformer's reference design.
- The isolation barrier is drawn on the board but not enforced by rule areas yet.

### 5.3 Framework cards that will not work
The **HDMI and DisplayPort cards need DisplayPort alt mode**, which a USB hub cannot provide.
USB-A, USB-C pass-through, storage, microSD, Ethernet and audio cards are plain USB and work.
The RK3566 has an unused eDP output that could feed one bay in a later revision; that needs a
PD controller and is not attempted here.

### 5.4 Things that differ between your documents
- The site lists the Basic model as S905X5M; the hardware README and this request say RK3566. RK3566 was followed.
- The site label says "5 V ⎓ 2 A"; this design budgets about 4 A at 5 V from 802.3at.
- The README lists "2× USB 2.0"; this board has 4× USB 3 and 5× USB 2 bays.
- Website requirements not addressed: USB-C power input (100 W), the 2×4 pogo battery interface.

### 5.5 Provisional footprints
`RJ45_HR6042S…` (reconstructed from Radxa's mask drawing), `XFMR_LAN_1CH_6P`, `XFMR_Flyback…`.
Replace with manufacturer land patterns. The four LAN transformers and chokes have no reference
designators in Radxa's drawings, so their positions are estimates.

### 5.6 Smaller items
- Line-side TVS diodes D9–D23 are DNP: with PoE the line floats to 57 V and Radxa's part value could not be verified.
- eMMC wiring follows the usual RK356x pattern but is not on the 3E schematic; check it against Rockchip's hardware guide.
- USB5744 has no SPI flash and runs on ROM defaults (its SMBus links R606/R607 to I2C3 are DNP); USB2517 uses CFG_SEL = 110 with strap options off. Changing either configuration means rework.
- The RK817 audio codec is powered but unused.
- BOM target of 25 USD: SoC, 2 GB LPDDR4 and 16 GB eMMC alone are likely more than half of it.
- **Licence.** The core is transcribed from Radxa's schematic. Confirm Radxa's terms before publishing it under CERN-OHL-S.

### 5.7 Software that must change with the hardware
Device tree: enable USB2 HOST3 (keyboard) and the eMMC, release `HUB_RESET_SOC_N` (GPIO3_C6),
drop the fusb/ET7301 Type-C node, camera and 40-pin overlays. Add the 24C02 at 0x50 on I2C2.

## 6. Files

```
commander/pcb/commander_mainboard/
  commander_mainboard.kicad_pro / .kicad_sch / .kicad_pcb     open these in KiCad 10
  sheets/*.kicad_sch            17 schematic sheets
  lib/commander.kicad_sym       symbols         lib/commander.pretty/   custom footprints
  src/netlist/*.net             THE SOURCE: one file per sheet, plain text
  src/reference/                placement data recovered from Radxa's drawings
  tools/build.py                regenerates everything and runs all checks
commander/schematics/commander_mainboard_revA0_schematic.pdf
commander/fabrication/bom/commander_mainboard_revA0_bom.csv
commander/fabrication/position/commander_mainboard_revA0_{top,bottom}.pdf, _placement.csv
```

The schematic and board are **generated**. To change the circuit, edit `src/netlist/*.net` and
run `python tools/build.py`; edits made in the KiCad schematic editor are overwritten by the
next build. Once routing starts, stop regenerating the board: from then on change the netlist,
regenerate the schematic only (`tools/gen_schematic.py`) and use *Update PCB from Schematic*.

The schematic is drawn in netlist style: each pin carries a label with its net name instead of
a drawn wire. That is what lets it be regenerated and machine-checked; search a net name to
find every pin on it.

## 7. Sources

- Radxa ZERO 3E V1.2 schematic and placement drawings (in `commander/schematics`, `commander/2d-models`)
- Microchip USB5744 data sheet DS00001855M; USB2517 data sheet DS00001598C
- Texas Instruments TPS23754 data sheet SLVS885I
- KiCad 10 standard libraries (pin-outs of the small parts were cross-checked against them)
- Dimensions of the outline: the three drawings supplied with the request
