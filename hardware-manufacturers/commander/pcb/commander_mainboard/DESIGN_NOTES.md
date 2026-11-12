# Commander mainboard — design notes, revision A1

Codec Terminal, model **Commander**: the Radxa ZERO 3E (RK3566), its PoE HAT and a USB hub for
nine Framework expansion-card bays, fused onto one coplanar L-shaped PCB that is fabricated in
the same panel as the keyboard.

**Status: schematic complete and electrically checked; board placed; routing started (bay strip and
battery-port area only — see 5.1). NOT ready for fabrication — section 0 says exactly why.**
This revision exists to be audited. Nothing here has been built or powered.

Changes in A1: front battery port (USB-C) with a PoE / battery 5 V selector; first routing tranche;
PoE output raised to 5.11 V; the chassis bleed network moved next to the RJ45; the head of the column
re-floorplanned (HDMI left, PoE centre, low-voltage corridor right).

## 0. Fabrication readiness (reviewed 2026-11-12): not ready

Do not order this board yet. A quote from JLCPCB would succeed and the boards would not work.

| # | Blocker | What it takes |
|---|---|---|
| 1 | **The codec core is not routed and its placement collides** (109 pad-level conflicts, `build/overlaps.txt`). RK3566 (0.4 mm ball pitch), LPDDR4, RK817 | Clean the placement against Radxa's drawings, then route by hand: DDR needs length matching per byte lane, the PMIC needs short switch loops. This is the bulk of the remaining work and it is specialist work. |
| 2 | **No differential pair is routed**: USB 2.0 (14 links), USB 3 (10 links), HDMI (4 pairs), MDI (4 pairs), plus RGMII and DDR | KiCad's interactive pair router, widths from the fabricator's impedance calculator for the chosen 6-layer stack-up. |
| 3 | **The PoE converter cannot be routed yet**: the transformer is a placeholder (part, pin-out and footprint), the loop values are textbook starting points | Choose the transformer, take its reference design, then lay the primary out by hand. |
| 4 | **Provisional footprints**: RJ45, the four LAN transformers, the flyback transformer | Replace with manufacturer land patterns. |
| 5 | **37 low-speed connections in the routed areas are still open** (list in `build/routing_report.txt`) | About an hour by hand, mostly hub decoupling. |
| 6 | **The schematic transcription has not had a second pair of eyes** (sheets 4-19 against the Radxa PDF) | One careful review; an error here costs a whole batch. |
| 7 | **The BOM has no manufacturer or LCSC part numbers**, and there are no Gerbers, drill files or JLC-format placement file | Generated in minutes once 1-4 are done; RK3566, LPDDR4 and RK817 will likely have to be consigned or globally sourced. |
| 8 | **Mechanical assumptions A1-A9 are unconfirmed**, mounting holes are provisional, there are no fiducials | Check against the chassis; the transformer on the bottom face needs about 13 mm of clearance below the board. |

What is in good shape: schematic (ERC clean, three-way consistent), the floorplan with its measured isolation gap,
the bay strip and battery-port low-speed routing (0 DRC violations), stack-up and planes.

**Fabrication class.** JLCPCB's published limits (3.5 mil / 0.09 mm track and space on 4-6 layers, via-in-pad for
fine-pitch BGA) cover what the core will need, but 0.4 mm ball pitch is at the edge of their standard service: expect
filled via-in-pad and the impedance-controlled stack-up option, and confirm on their live capability page before ordering.

**A faster way to hardware.** Almost everything that is *new* in this design — PoE, both hubs, nine bays, the battery
port — lives outside the codec core. A strip-only test board fed by a stock Radxa ZERO 3E over its USB-C port would be
4 layers with nothing finer than a QFN, and would validate that new circuitry while the core layout is done properly.
It is a separate board variant and has not been started.

## 1. What is on the board

| Block | Parts | Origin |
|---|---|---|
| SoC, DDR, PMIC | RK3566, LPDDR4 200-ball, RK817-5, RK860-0 | Radxa ZERO 3E V1.2, unchanged |
| Ethernet | RTL8211F-CG, 4 discrete LAN transformers + chokes, sunk RJ45 | Radxa, unchanged |
| Video | HDMI 2.0, micro HDMI (type D) | Radxa, unchanged |
| PoE | TPS23754 PD + isolated 5 V flyback, 802.3at class 4 | **new** (replaces the PoE HAT) |
| USB 3 | USB5744, bays 1–4 at 5 Gb/s | **new** (replaces the single Type-C USB3 port) |
| USB 2 | USB2517, bays 5–9, port 6 to the battery port | **new** |
| Battery port | USB-C on the front edge, FUSB302B CC controller, TPS2121 PoE / battery selector, charge switch | **new in A1** |
| Keyboard link | USB2 HOST3 straight from the SoC, JST-SH 4-pin | **new** (HOST3 is unused on the 3E) |
| Storage | eMMC 153-ball **and** microSD | eMMC **new**; microSD from Radxa, relocated |
| Service | USB-C (USB2 OTG, flashing), 3.3 V UART header, recovery and reset buttons, ID EEPROM | adapted / new |

672 components, 484 nets, 18 schematic sheets.

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
3. **Model, schematic and board agree.** `tools/check_consistency.py` compares all 2,844 pads
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

**Battery port (front edge, marked "TO BATT").** A 16-pin USB-C receptacle on the front end of the
column; a pogo-pin-to-USB-C adapter will dock the battery module there. It is a 5 V-only port:

- *Power in.* A TPS2121 power mux (U81) selects between the PoE converter (priority) and the port.
  Everything that used to hang on the PoE output — `VCC_SYS`, the nine bay switches, the keyboard —
  now hangs on the mux output `VCC5V_BUS`. The mux switches over in microseconds when PoE sags below
  about 81 % of the port voltage, blocks reverse current into either source, limits at 4.5 A and
  disconnects the port above 6.0 V. `PWR_SRC_ST` (GPIO4_C3) tells the SoC which source is in use.
- *Power out.* With PoE present the SoC can raise `BATT_VBUS_EN` (GPIO4_C2) to push 5 V out through a
  current-limited switch (U82) and charge the module; fault flag on GPIO4_C5. Off by default.
- *Role.* An FUSB302B (U80) on I2C3 handles the CC pins — the same circuit the ZERO 3E uses for its own
  Type-C port (there as ET7301B), so the mainline `fusb302` driver applies. Unpowered it presents Rd, so
  any USB-C source — the module, a power bank, a phone charger — can start a dead board. That also
  makes this the board's USB-C power input when no PoE switch is at hand.
- *Data.* D+/D− go to USB2517 port 6 so the module can enumerate (fuel gauge, HID power device). The SBU
  pins can be linked to I2C2 with two 0 Ω parts (DNP) for a module that prefers I2C telemetry.

The PoE set point moves from 5.05 V to 5.11 V to cover the drop in the mux (56 mΩ typical).
No rear USB-C was added: the connector beside the RJ45 is the micro HDMI and stays.

**Head of the column: HDMI left, PoE centre, low-voltage corridor right.** From the left edge:

| x (mm) | What | Why |
|---|---|---|
| 0 – 5.8 | HDMI corridor | the micro HDMI is on the rear-left tab; its pairs run straight down to the SoC |
| 5.8 – 8 | barrier | 2.2 mm, no copper (2.0 mm to the transformer pins) |
| 8 – 22 | PoE primary (57 V) and the transformer | directly under the RJ45, where the 48 V centre taps arrive |
| 22 – 24.2 | barrier | 2.2 mm; only the optocoupler U31 and the Y capacitor C518 straddle it |
| 24.2 – 30 | SELV corridor | RGMII from the PHY, and USB, SD and 5 V for the strip |

The PoE block could not simply be mirrored to the right edge: the bay strip joins the column on that
edge, so it has to stay low-voltage. The PoE secondary (rectifier, output filter, feedback, the
PoE / battery selector) wraps round the lower half of the transformer. `tools/check_isolation.py`
measures the result on every build and fails it below 2.0 mm (it did, once: the first planes came within
1.8 mm of the transformer pins). Smallest gaps now: 2.0 mm to a plane, 2.6 mm to a pad (the Y capacitor's own); the constants are `HDMI_COR`, `PRI_X0…PRI_Y1`, `SELV_COR`.

*What this costs:* the right corridor is the only way from the strip to the SoC and it is 5.8 mm wide at
the transformer's primary pins — about thirty signals (RGMII, two USB 3 pairs, three USB 2 pairs, SD)
have to share it over three signal layers. It is feasible, but it is the tightest spot on the board.
The transformer body (18.6 mm with courtyard, bottom face) overhangs both barriers; keep bottom-layer copper out from under it.

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
| A5 | Board is **6-layer, 1.2 mm** (signal / GND / signal / power / GND / signal) | RK3566 escapes on a standard 6-layer; thickness not specified |
| A9 | The battery port sits on the **front edge, 8 mm from the left corner** (`BATT_X`) | read off your annotated render; move the constant to suit the chassis |
| A6 | Mounting holes | **provisional**, positions belong to the chassis |
| A7 | Keyboard connects by **USB 2.0** on a 4-pin JST-SH | the keyboard interface was not specified |
| A8 | Component height is unconstrained | **not true for the transformer — see 5.2** |

## 5. Audit list, most important first

### 5.1 Routing status: started, about a fifth of the connections
`tools/route.py` sets the stack-up roles, pours the planes and routes what can be routed responsibly
by script. The detailed result of the last run is in `build/routing_report.txt`.

| Layer | Role | Routed so far |
|---|---|---|
| F.Cu | signal + parts | 1,131 mm |
| In1.Cu | GND plane | poured |
| In2.Cu | signal | 604 mm |
| In3.Cu | power plane (`VCC5V_BUS` under the strip; core rails to be split by hand) | poured |
| In4.Cu | GND plane | poured |
| B.Cu | signal + parts | 739 mm |

**Layer count.** Six layers is the fewest this board should be built on, and the routed part uses
exactly that: three signal layers and three planes. The bay strip alone would fit on four, but the
stack is set by the RK3566 and LPDDR4 (0.4 / 0.65 mm ball pitch, impedance-controlled pairs that
each need an unbroken ground plane next to them). Four layers for the core is not a risk worth taking.

**What is routed** (2,683 track segments, 331 vias, 0 DRC violations on the routed copper):
- the bay strip: VBUS, CC and port-control nets of all nine bays, the microSD socket, the keyboard
  connector, both hub ICs' straps, crystals, resets and most of their supply pins;
- the front / battery-port area: the local nets around J40, U80, U82, U83 and the parts placed there;
- a via to the planes for 203 ground and 5 V pads.

Ratsnest connections went from 2,141 to 1,671. 77 nets are complete within their region, 25 are
partly connected and 37 pad connections found no path (listed in the report). The router makes four
passes per region, putting what failed first on the next pass; that brought the open connections from
57 to 37 and then stopped improving, because the rest are hub pins and decoupling capacitors boxed in by
the dense row packing around U40 and U50. They need the parts nudged, i.e. hand work.

**What is deliberately not routed**
- **The codec core, Ethernet, PoE and HDMI areas.** The placement there still has **109 pad-level
  conflicts** and about 420 courtyard overlaps (`build/overlaps.txt`); routing over colliding parts would
  be fiction. Clean the placement first.
- **Every impedance-controlled pair**: USB 2.0 (9 bays, 3 root ports, battery port), USB 3 (bays 1–4 and
  the hub upstream), HDMI, MDI, RGMII, DDR. They need KiCad's differential-pair router and length
  tuning, with widths recalculated for the fabricator's real stack-up.
- **Planes under the PoE primary and the RJ45 / magnetics head.** Nothing is poured there,
  so the isolation barrier is not compromised by a script; those pours belong with the PoE layout.

**Read this before trusting the routed part**
- It is maze-router output: electrically connected and rule-clean, not hand-optimised. Signal tracks are
  0.15 mm, power 0.3 / 0.4 mm with 0.15 mm necks into the 0.5 mm-pitch connector pads.
- The two hub buck converters (U41, U42) are connected but their placement is a row packing, not a
  proper switch-node layout. Re-place and re-route them by hand.
- `VCC3V3_HUB` reaches the USB2517 as a 160 mm long 0.3 mm track (about 70 mV drop at 250 mA). Give it a
  split of the In3 plane or a wider path.
- To leave room for vias the parts in the hub and bay zones are spaced 0.6 mm apart; some hub passives
  moved to the bottom side as a result.
- Re-running `tools/build.py` regenerates the board and the routing from scratch. **Hand routing done in
  KiCad is lost by a rebuild** — once you start routing by hand, stop rebuilding (see section 6).

**The floorplan problem that routing exposed is fixed.** In the first placement the PoE primary sat on
the left of the column, between the micro HDMI and the SoC, so the HDMI pairs and the 48 V input had to
cross. The head of the column is now laid out in three lanes (decision of 2026-11-12, see section 3).

### 5.2 The PoE converter is a first pass
- **Transformer height.** A 30 W flyback transformer of the usual EP13 class is about 12.7 mm tall. It now
  sits on the **bottom face** (decision of 2026-11-12), with its primary pins towards the rear; the chassis
  needs about 13 mm of clearance below the board there. If it cannot take that, the alternatives are a
  planar transformer or dropping to 802.3af. The top face above it is free for low parts, but the 2 mm
  rule around the primary pins applies on every layer.
- Transformer part and pin-out are placeholders; current sense, clamp, bias and loop compensation
  are textbook starting values. They need a bench validation or the values of the chosen
  transformer's reference design.
- The isolation barrier is drawn on the board and measured by `tools/check_isolation.py`, but not yet
  enforced by KiCad rule areas — add them before hand-routing the head of the column.
- The Ethernet head itself (RJ45, magnetics, Bob-Smith network, PHY) keeps Radxa's arrangement, where the
  PHY sits on top above line-side parts on the bottom. With PoE that stack-through deserves its own review.

### 5.2b The battery port is a provisional interface
- The battery module does not exist yet. CC, SBU and data wiring are a reasonable guess at what it needs.
- **Switch-over is seamless only towards a source that is already on the port.** While the board is
  *charging* the module, the port is fed from the board; if PoE drops then, an ordinary dual-role power
  bank needs a few hundred milliseconds to turn round and the board will reboot. A module meant as a UPS
  must hold 5 V on the port continuously (or get a dedicated charge path in a later revision).
- Known `fusb302` behaviour on Rockchip boards: the driver resets the chip at probe, which drops Rd for a
  moment and can make a source cut VBUS — a boot loop when the port is the only supply. The DNP options
  R802 / R803 (fit 5.1 kΩ, omit U80) give a hard-wired sink that cannot do this, at the price of the
  charging role.
- 5 V only. A source that goes above 6.0 V is locked out by U81, but D80 and U83 are 5 V parts: do not
  enable USB-PD voltages in software.
- Charging takes its current from the same 21 W PoE budget as the SoC and nine bays. Advertise 1.5 A at most.

### 5.3 Framework cards that will not work
The **HDMI and DisplayPort cards need DisplayPort alt mode**, which a USB hub cannot provide.
USB-A, USB-C pass-through, storage, microSD, Ethernet and audio cards are plain USB and work.
The RK3566 has an unused eDP output that could feed one bay in a later revision; that needs a
PD controller and is not attempted here.

### 5.4 Things that differ between your documents
- The site lists the Basic model as S905X5M; the hardware README and this request say RK3566. RK3566 was followed.
- The site label says "5 V ⎓ 2 A"; this design budgets about 4 A at 5 V from 802.3at.
- The README lists "2× USB 2.0"; this board has 4× USB 3 and 5× USB 2 bays.
- Website requirements only partly addressed: USB-C power input is 5 V through the battery port, not 100 W PD;
  the 2×4 pogo battery interface is expected to arrive as a pogo-to-USB-C adapter on that port.

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
drop the camera and 40-pin overlays. Add the 24C02 at 0x50 on I2C2. Keep a `fusb302` node, but move it
to I2C3 (0x22, interrupt GPIO3_C7 as on the 3E) as a 5 V-only dual-role power port with no USB3 / DP
endpoints; its `vbus-supply` is a fixed regulator gated by GPIO4_C2. Read GPIO4_C3 (`PWR_SRC_ST`) to know
when the board runs from the battery port.

## 6. Files

```
commander/pcb/commander_mainboard/
  commander_mainboard.kicad_pro / .kicad_sch / .kicad_pcb     open these in KiCad 10
  sheets/*.kicad_sch            18 schematic sheets
  lib/commander.kicad_sym       symbols         lib/commander.pretty/   custom footprints
  src/netlist/*.net             THE SOURCE: one file per sheet, plain text
  src/reference/                placement data recovered from Radxa's drawings
  tools/build.py                regenerates everything and runs all checks
  tools/route.py                planes + scripted routing (tranche 1); build/routing_report.txt
commander/schematics/commander_mainboard_revA1_schematic.pdf
commander/fabrication/bom/commander_mainboard_revA1_bom.csv
commander/fabrication/position/commander_mainboard_revA1_{top,bottom}.pdf, _placement.csv
```

The schematic and board are **generated**. To change the circuit, edit `src/netlist/*.net` and
run `python tools/build.py`; edits made in the KiCad schematic editor are overwritten by the
next build. The scripted routing is regenerated too, so nothing is lost by a rebuild *today*.
That changes the moment someone routes by hand: from then on change the netlist, regenerate the
schematic only (`tools/gen_schematic.py`) and use *Update PCB from Schematic* instead of `build.py`.

The schematic is drawn in netlist style: each pin carries a label with its net name instead of
a drawn wire. That is what lets it be regenerated and machine-checked; search a net name to
find every pin on it.

## 7. Sources

- Radxa ZERO 3E V1.2 schematic and placement drawings (in `commander/schematics`, `commander/2d-models`)
- Microchip USB5744 data sheet DS00001855M; USB2517 data sheet DS00001598C
- Texas Instruments TPS23754 data sheet SLVS885I; TPS2121 data sheet SLVSEA3F
- onsemi FUSB302B pin-out (KiCad library) and the ET7301B circuit on sheet 14 of the Radxa schematic
- KiCad 10 standard libraries (pin-outs of the small parts were cross-checked against them)
- Dimensions of the outline: the three drawings supplied with the request
