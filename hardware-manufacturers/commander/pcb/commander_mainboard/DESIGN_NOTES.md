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

## 0. Fabrication readiness (reviewed 2026-11-14): not ready

Do not order this board yet. A quote from JLCPCB would succeed and the boards would not work.

**Where it stands.** The scripted router now covers the whole board except two areas that are left out on purpose.
It has made **1,570 of the 2,354 connections (66.7 %)**; 784 are still open, on 375 of 526 nets
(`build/open_report.txt` lists them net by net, `build/usb_report.txt` the USB links). In KiCad the open ones are
the thin ratsnest lines that remain.

| # | What stands between this file and an order | What it takes |
|---|---|---|
| 1 | **The memory bus is not routed, on purpose** (74 connections, RK3566 to LPDDR4). A maze router can join these balls, and did in an experiment (5.2a), but a memory bus joined that way looks finished and does not work | A layout engineer places Rockchip's reference layout for this interface (mirrored: the core is on the bottom face) and tunes the lengths per byte lane. |
| 2 | **The Ethernet head is not routed, on purpose** (RJ45, the four LAN transformers, the PHY and its parts; about 179 connections, the RGMII lines from the RK3566 among them). The line side of the transformers has to keep 1.5 kV from everything else, and the transplanted placement mixes line-side and PHY-side parts on both faces | Decide where the isolation boundary runs, re-place the head on either side of it, give its PHY side a ground plane; the router's isolation mask (which already guards the PoE primary) can then be extended to it. |
| 3a | **The PoE primary is not connected** (31 connections, 2026-11-14 build). Its class clearance was 0.30 mm, more than the 0.20 mm between the TPS23754's own pins, so none of them could be left; it is 0.20 mm now (IPC-2221B: 0.13 mm at 57 V). What still blocks it: the row packer puts R511 and D31 0.45 mm in front of the controller's pin rows, and the primary area is too full to keep a band free there (tried: 1.0-1.4 mm, two parts no longer fit) | Place the PoE primary by hand (the TI layout for this chip is the model), or give the primary area more room; then the router connects it. |
| 3 | **About 530 other connections are open** in the areas that are routed: 174 ground pads without a via, the supply balls and capacitors under the RK3566 that the pours did not reach, the mux chips of bays 1-4, and what is listed in `build/routing_report.txt` | Hand routing in KiCad, or first loosening the placement where the report shows a cluster. |
| 4 | **The eMMC cannot be connected where it is**: it sits on the top face directly over the PMIC, so the vias its inner balls need would land in the PMIC's pads (17 eMMC connections open) | Move it to a place whose other face is free, or build the prototype with the microSD socket only. |
| 5 | **Everything that is routed is script output, not reviewed by a layout engineer.** Differential pairs run as coupled tracks at the class geometry, but nobody has checked impedance against the real stack-up, and nothing is length-tuned (the differences are in `build/usb_report.txt`). The supply rails of the core are joined by pours placed by a simple rule and by 0.09 mm links between ball vias. The PoE primary is connected, its switching loop is not optimised | A review by someone who lays out boards of this class; a power-integrity look at the core rails; a bench validation of the PoE converter. |
| 6 | **The rear USB-C sockets are hard to route and not stocked** (JAE 24-pin, two rows of surface-mount pads, the rear row 1 mm from the board edge) | Swap for a common hybrid 24-pin socket (one row through-hole): easier to route, and available. Your decision, see the cost table. |
| 7 | **Provisional footprints**: RJ45 and the four LAN transformers | Replace with manufacturer land patterns. The flyback transformer footprint is from the Bourns data sheet; check it against the current revision before ordering. |
| 8 | **USB-C receptacles stand 3.2-3.3 mm on a face with about 3 mm of room.** The nine bays are at the rear, where the case is taller; the three in the column (service J2, keyboard J20, battery J40) are under the keyboard | Decide per port: a sunk (mid-mount) receptacle in a board cut-out stands about 1.6-2.4 mm above the board, or the port moves to the bottom face, where there is room. |
| 9 | **The schematic transcription has not had a second pair of eyes** (sheets 4-19 against the Radxa PDF) | One careful review; an error here costs a whole batch. |
| 10 | **The BOM has no manufacturer or LCSC part numbers**; the Gerbers in `fabrication/` are marked QUOTE-ONLY | Filled in once 1-6 are done; RK3566, LPDDR4 and RK817 will likely have to be consigned or globally sourced. |
| 11 | **Mechanical assumptions A1-A9 are unconfirmed**, mounting holes are provisional, there are no fiducials | Check against the chassis. |

What is in good shape: schematic (ERC clean, three-way consistent), the floorplan with its measured isolation gap,
a placement with no two pads touching, the USB 2.0 links from the processor to both hubs (section 5.1; the links
from the hubs on to the bays are about half done), stack-up and planes.

**Fabrication class.** The board now uses, under the BGA packages only, 0.09 mm tracks and 0.25 / 0.15 mm vias placed in
the ball pads (to be filled and capped). JLCPCB's published limits cover that on 6 layers, but it is their finest class:
confirm on their live capability page, and ask for the impedance-controlled stack-up. Elsewhere tracks are 0.10 mm or
wider and vias 0.45 / 0.20 mm or larger.

**A faster way to hardware: the strip test board.** Almost everything that is *new* in this design — PoE, both hubs,
nine bays, the battery port — lives outside the codec core. `pcb/commander_strip_test` is that circuitry on its own
4-layer board, fed by a stock Radxa ZERO 3E, generated from the same netlist sources by the same tools
(`python tools/build.py --variant strip_test`). Its placement has no collisions at all; it is routed by the same
script, with fewer layers to do it on; see its README.

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
| Keyboard link | USB2 HOST3 straight from the SoC, standard USB-C (USB 2.0) on the inner edge | **new** (HOST3 is unused on the 3E) |
| Storage | eMMC 153-ball **and** microSD | eMMC **new**; microSD from Radxa, relocated |
| Service | USB-C (USB2 OTG, flashing) on the inner edge, 3.3 V UART header, recovery and reset buttons, ID EEPROM | adapted / new |
| Power button | side-operated tact switch (Panasonic EVQ-P7A, 1.35 mm tall) on the left edge beside the PoE block, on the RK817's PWRON: press = on; short press while running = power-key event for the OS; about 6 s = forced off | **new in A1** |

695 components, 526 nets, 18 schematic sheets.

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
3. **Model, schematic and board agree.** `tools/check_consistency.py` compares all 3,049 pads
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

**SuperSpeed bays 1-4 have a Type-C port controller and orientation mux** (decision of 2026-11-12; this
replaces the earlier "no mux, lane chosen by BOM" arrangement). Each bay carries a TI HD3SS3220, wired as in
Microchip's USB5744 figure "Downstream Port Type-C USB Connections":

- It reads CC1 / CC2, presents the port as a source (DFP, default USB current) and switches the hub's single
  SuperSpeed lane to whichever side of the receptacle the plug uses. A cable plugged in either way up now
  runs at 5 Gb/s, and the port is a proper Type-C source on CC instead of two fixed pull-ups.
- GPIO mode: no I2C, no firmware. Its ID output goes low on attach and also enables the mux, so an empty
  bay's SuperSpeed lines are switched off.
- AC coupling: 100 nF on the transmit pair (hub side), 330 nF on each receive pair at the connector. ESD
  protection on both lanes at the connector.
- VCONN for active cables comes from the 5 V bus through the controller (10 uF local bulk; TI suggests
  100 uF if long active cables are ever expected).

*Not done:* the controller does not gate VBUS. The bay is powered whenever the hub enables the port, so VBUS
is not "cold" before attach as the Type-C specification asks of a source. Gating it needs the ID signal
combined with the hub's port-power line; that is one small logic gate per bay if you want full compliance.

**Hi-Speed bays 5-9 keep fixed CC pull-ups.** They are USB 2.0 only, where plug orientation does not matter:
56 kOhm Rp on each CC pin and VBUS switched by the hub port with over-current reporting. That is enough for
Framework cards and ordinary peripherals; no USB-PD.

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

**The codec core is on the bottom face** (decision of 2026-11-12). The case is sealed and fanless and the
heatsink is the bottom of the chassis, so the parts that make the heat have to touch the aluminium directly:
heat does not usefully cross the board under a BGA. The RK3566 cannot move alone (the memory and the PMIC hang
on short matched connections, and their decoupling sits under them on the other face), so the **whole core
block is built as the mirror image of Radxa's placement**: every part is reflected about the centre line of the
column and changes face. RK3566, LPDDR4 and RK817 now face down; their decoupling is on top.
`tools/gen_pcb.py` does this with one flag (`CORE_ON_BOTTOM`), and the build was checked against the un-mirrored
placement pad by pad: all 257 core parts are exact mirror images (worst deviation 0.001 mm).

What follows from it:

- **HDMI and RGMII now leave the SoC on the "wrong" sides** (HDMI towards the inner edge, RGMII towards the
  outer edge) and have to cross each other in the neck between the PoE block and the SoC, each with a layer
  change. USB 3 gained: it now leaves on the side of its corridor.
- **The eMMC is on the top face**, opposite the PMIC, where Radxa has the microSD socket. It dissipates little.
- **The plate has a 6 mm pedestal** (prototype: 3D-printed aluminium, which is ample for the 2-3 W involved;
  copper adds little here). With the chips 1.0-1.2 mm tall that leaves about 7 mm under the board over the
  plate, and nothing on the bottom of the core comes near it (tallest neighbour 1.45 mm). If one pedestal is to
  serve the SoC, the LPDDR4 and the PMIC together, note that the parts between them - the PMIC's four
  inductors at 1.2 mm, three HDMI chokes - are as tall as the chips, so either relieve the pedestal there or
  keep it to the outline of each package. Use a compliant thermal pad, not paste: three packages of slightly
  different height share one surface.
- **The transformer now fits**: see "PoE transformer" below.
- Two more parts are worth coupling to the plate: the PoE output rectifier D41 (close to 2 W at full load)
  and the USB5744.

**Nothing is in the way of the chips.** `tools/check_chips.py` runs on every build and fails it if any part
sits under a big chip's package on the same face, or if a through-hole pad comes up inside one. It found six
such parts after the first placement (for example the 24 MHz crystal lay on the SoC's land pattern - an
artefact of recovering positions from text anchors). A legalisation step now moves every small part that
sits on a chip, a connector or another part's pads to the nearest free spot on its own face: 80 parts moved,
1.7 mm on average. Their new positions are approximations, like the anchor positions they replace, and still
want a human eye - but the board can be assembled as placed.

**Nothing on the top face is taller than the bay connectors** (decision of 2026-11-13). A USB-C receptacle
stands about 3.3 mm, and seven parts stood taller. Moving them all underneath was not the best answer for
most of them, because a power stage wants its parts on one face, so each was dealt with on its merits:

| Part | Was | Now | Why |
|---|---|---|---|
| C504, PoE input bulk capacitor | 100 V electrolytic, 7.7 mm, top | **bottom face** | no low-profile equivalent exists at 22 uF / 100 V; the bottom already has the transformer's height |
| U31, feedback optocoupler | SMDIP-4, about 4 mm | mini-flat SOP-4, 2.1 mm (TLP291 class) | same pin-out, 5 mm creepage, still straddles the barrier |
| L30, 5 V output inductor | 5 x 5 x 3.0 mm | 4 x 4 x 2.1 mm (XAL4020 class, 1 uH) | stays beside the rectifier and output capacitor |
| C514, 5 V output capacitor | polymer 7343, 3.1 mm | same value in the 2.0 mm case | |
| L41, L42, hub buck inductors | 4 x 4 x 3.0 mm | 2520 size, 1.2 mm | each hub rail draws well under 1 A |
| J21, debug UART | 2.54 mm pin header, 8.5 mm | JST-SH 4-pin, 2.95 mm | kept on top so a technician can reach it |

`tools/report_heights.py` lists the tallest parts on each face on every build (`build/heights.txt`) and fails
the mainboard build if any part other than a connector exceeds the clearance on top (now 3 mm, the measured figure). The heights are typical package figures, to be
confirmed against the datasheets of the parts actually bought. The RJ45 is not in the table: it is the
sunk low-profile type and is the one item that does stand above the rest at the rear edge.

*Consequence:* the optocoupler change alters the feedback loop gain (different current-transfer ratio);
the compensation values were first-pass in any case and need the same bench check as before.

**Routing the whole board by script: what was changed to make it possible** (2026-11-13). You asked for a board with no
ratsnest left except for features that are deliberately not implemented. These are the changes that request led to;
each one is a judgement of mine that you may want to reverse.

- **A ring around each USB hub is kept free of parts on both faces** (4 mm around the USB 3 hub U40, 3 mm around the
  USB 2 hub U50). The hub's pairs leave the pins, change layer there and run on. Without it they could not get out
  from between the hub's own capacitors. Cost: twelve hub passives sit a few millimetres further from the chip.
- **The parts of the PoE primary are spaced 0.45 mm apart** (they were 0.2 mm), and the class clearance between
  primary nets is 0.20 mm (it was 0.60 mm, then 0.30 mm). The TPS23754 itself has only 0.20 mm between its pins
  (HTSSOP, 0.65 mm pitch), so with any larger class clearance not one of its pins could be left by a track: the whole
  primary stayed unrouted. 0.20 mm under solder mask is more than IPC-2221B asks for 57 V (0.13 mm) and what TI's
  layouts for this chip use; the 2 mm to everything that is not primary is unchanged and still checked by
  `tools/check_isolation.py`.
- **Small parts that touched each other were moved apart.** About seventy small parts in the core, each placed from
  its own pads in Radxa's drawing, ended up with pads touching a neighbour (the footprints used here are larger than
  the ones in the drawing). Touching pads of different nets are a short circuit, so the smaller part of each such pair
  was moved to the nearest free spot (`build/placement_report.txt` marks them "moved off another part's pads").
- **Top-side parts are kept off the balls of the USB and HDMI pairs.** Those balls leave the RK3566 through a via in the
  ball itself, which comes out on the top face.
- **Vias in the ball pads of the three BGA packages**: 0.25 mm pad, 0.15 mm hole, to be filled and capped. The board
  rules allow them (minimum via 0.25 / 0.15 mm, hole to copper 0.195 mm: a via in a 0.4 mm-pitch ball is exactly
  0.200 mm from the next ball). They are used under the BGAs only.
- **Supply nets of the core get a pour each on In3**, the smaller net winning where two overlap, on top of whatever
  tracks join them. A split of the power layer drawn by a person will be better; this one is drawn by a rule.
- **The Ethernet head and the memory bus are left out** (section 0, blockers 1 and 2).

**PoE transformer: Bourns PLN060-ER20A05S** (decision of 2026-11-13). The case has about 10 mm under the board
and 3 mm above it, and the usual 30 W PoE transformers (EP13 / EFD20) are 11.4-12.7 mm tall. This one is a
planar part, **8.0 mm tall**, 22.5 x 21.0 mm, 36-72 V in, 5 V out, 200 kHz, 1500 Vrms, with a 12 V auxiliary
winding for the controller's bias - the arrangement the TPS23754 circuit already used. Turns ratio
1 : 0.25 : 0.5, primary inductance 40 uH. Data from the Bourns data sheet (rev. 01/24), which is where the
pin-out and the land pattern in `lib/commander.pretty` come from.

- It is rated 60 W; the series has nothing smaller. It was chosen for its height, not its rating.
- Pins: primary 2-3, auxiliary 1-4, secondary 6-5. With the supply on 2 and the switch on 3, the rectifier is
  on 6 and the bias diode on 4 (checked against the winding dots).
- The switching frequency resistor moved from 69.8 k to 75 k (200 kHz, the transformer's design frequency).
- At 36 V input and full load the primary peaks at about 2.7 A, in continuous conduction; the 0.15 ohm sense
  resistor limits at about 3.7 A. Reflected voltage 22 V, so the 150 V switch and the 40 V rectifier have margin.
- Its primary pad row is 17.8 mm wide, wider than the primary zone, so both low-voltage corridors step back
  where they pass it (to x = 4.1 and x = 25.9 for about 6 mm). The right corridor is 4.1 mm wide there:
  that is now the narrowest point for the thirty signals that go to the strip.

**Both user-plugged USB-C ports open onto the inner edge** (decision of 2026-11-12). The inner (right)
edge of the column faces the keyboard, so nothing on it is reachable from outside the case:

- **Keyboard port J20**, a standard USB-C receptacle carrying USB 2.0 from the SoC's own root port (HOST3).
  The board is the host: 56 kOhm Rp on both CC pins, 5 V through a 500 mA resettable fuse. The keyboard
  therefore needs an ordinary device-side USB-C port (5.1 kOhm Rd on CC) and a plain USB-C cable.
- **Service port J2**, used to flash the OS in maskrom / rockusb. The terminal is flashed by technicians,
  not by the user, like a set-top box, so the port is inside the case on purpose.

The two ports sit side by side, J2 at 83.0 mm and J20 at 94.0 mm from the column top - the stretch you marked.
Their shield legs go through the board, so they may not stand over a chip on the other face: beside the
LPDDR4 and the PMIC the legs are clear, beside the SoC they would not be. Their small parts are on the bottom
face under them.

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
| A10 | **Rounded outline**: free outer corners R3.0, rear-tab corners R1.0 (connectors sit right beside them), the two inside corners where the strip meets the column R1.0, RJ45 notch R0.5 | JLCPCB's guidance (R3-R5 on boards over 100 mm; an inside corner cannot be sharper than the router bit). Constants `R_OUT`, `R_TAB`, `R_IN`, `R_NOTCH` in `tools/gen_pcb.py` |
| A11 | The heatsink plate is **below** the board with a **6 mm pedestal** that meets the chips (1.0-1.2 mm tall); over the plate about 7 mm is free under the board. Prototyped in 3D-printed aluminium, copper planned | measured on the prototype, 2026-11-13 (`PEDESTAL`, `CLEAR_OVER_PLATE`) |
| A12 | Clearance **above the board about 3 mm, below it about 10 mm** | measured on the prototype case, 2026-11-13 (`CLEAR_TOP`, `CLEAR_BOTTOM` in `tools/gen_pcb.py`) |
| A7 | Keyboard connects by **USB 2.0 over standard USB-C**, as a device with Rd on CC | confirmed 2026-11-12; the keyboard PCB itself has not been reviewed (its design files are not in the repository) |
| A8 | Component height is unconstrained | **not true for the transformer — see 5.2** |

## 5. Audit list, most important first

### 5.1 Routing status: 66.7 % of the connections, by script (2026-11-14 build)
`tools/route.py` routes the board in stages, each a process of its own working on the same board file. The detailed
result of the last run is in `build/routing_report.txt`; `build/open_report.txt` lists what is still open and
`build/usb_report.txt` every USB net.

| Stage | Grid | What it does |
|---|---|---|
| local | 0.05 mm | the bay strip, the front / battery area and the PoE converter, each in its own window, up to four passes (what failed goes first next time). In the strip, before anything else: a short coupled stub out of every pair of hub pins, then the links that go on to the processor, then the supply nets, then the pairs, then the rest |
| ports | 0.05 mm | a second chance for links between strip and column that did not reach the hand-over line (a line across the right-hand corridor at y = 32.3; pairs are handed over 1 mm further on, so that their two ends stand clear of the others) |
| escape | 0.025 mm | under the RK3566, the LPDDR4 and the eMMC: every signal ball is brought out to a point outside the package (0.09 mm track, a 0.25 / 0.15 mm via in the ball where needed), then ground and supply balls get a via in the pad, then the supply balls of each net are joined on the power layer |
| power | 0.05 mm | the supply nets of the column, with the power layer In3 as the preferred layer |
| column | 0.05 mm | the whole column from the HDMI tab to the front edge: everything that is still in more than one piece, pairs first. A pair trunk that ends at loose ends of copper already there (an escape, the trunk from the strip) is drawn straight onto them |
| prune | - | removes dead ends (a hand-over point nobody picked up, a pair trunk whose ends could not be joined) |
| finish | - | ground planes, the 5 V plane, a pour on In3 for every supply net of the core, the report |

| Layer | Role | Routed |
|---|---|---|
| F.Cu | signal + parts | 4,002 mm |
| In1.Cu | GND plane | poured |
| In2.Cu | signal | 2,884 mm |
| In3.Cu | power: `VCC5V_BUS` plane under the strip, a pour per supply net in the core | 227 mm of links + pours |
| In4.Cu | GND plane | poured |
| B.Cu | signal + parts | 3,237 mm |

941 vias. KiCad's ratsnest count went from 2,322 (nothing routed) to 784 (2026-11-14 build, with the power button).

**The USB links** (what you asked for on 2026-11-13). 57 of the 110 USB nets are complete end to end; 14 pair
sections run as a coupled trunk (two parallel tracks at the class geometry, 0.11 / 0.13 mm for USB 2.0 and
0.10 / 0.12 mm for SuperSpeed).

| Link | Nets complete |
|---|---|
| RK3566 <-> USB 3 hub (U40), SuperSpeed | 5 of 8 |
| RK3566 <-> USB 3 hub (U40), USB 2.0 lane | 2 of 2 |
| RK3566 <-> USB 2 hub (U50) | 2 of 2 |
| RK3566 <-> keyboard port (J20) | 0 of 2 |
| RK3566 <-> service port (J2) | 2 of 4 |
| USB 2 hub <-> battery port (J40) | 1 of 2 |
| USB 3 hub <-> bays 1-4, USB 2.0 | 1 of 8 |
| USB 2 hub <-> bays 5-9, USB 2.0 | 8 of 10 |
| USB 3 hub <-> bays 1-4, SuperSpeed (hub - capacitor - mux - socket) | 36 of 72 |

The links that involve the processor, net by net (pads joined / pads of the net, routed length):

| Net | State | Pads | Length |
|---|---|---|---|
| `USB3_HOST1_DM` | complete | 2/2 | 71.6 mm |
| `USB3_HOST1_DP` | complete | 2/2 | 68.5 mm |
| `USB2_HOST2_DM` | complete | 2/2 | 238.6 mm |
| `USB2_HOST2_DP` | complete | 2/2 | 225.2 mm |
| `HUB3_UP_RXN` | complete | 2/2 | 36.6 mm |
| `HUB3_UP_RXP` | **open** | 1/2 | 0.0 mm |
| `HUB3_UP_TXN` | **open** | 1/2 | 0.0 mm |
| `HUB3_UP_TXP` | complete | 2/2 | 45.2 mm |
| `USB3_HOST1_SSRXN` | complete | 2/2 | 80.4 mm |
| `USB3_HOST1_SSRXP` | complete | 2/2 | 81.5 mm |
| `USB3_HOST1_SSTXN` | **open** | 1/2 | 68.5 mm |
| `USB3_HOST1_SSTXP` | complete | 2/2 | 86.9 mm |
| `USB2_HOST3_DM` | **open** | 3/5 | 25.0 mm |
| `USB2_HOST3_DP` | **open** | 4/5 | 20.6 mm |
| `SVC_DM` | complete | 5/5 | 41.3 mm |
| `SVC_DP` | complete | 5/5 | 54.9 mm |
| `USB_OTG0_DM` | **open** | 2/3 | 22.0 mm |
| `USB_OTG0_DP` | **open** | 2/3 | 34.5 mm |
| `USB_AUX_DM` | complete | 5/5 | 298.9 mm |
| `USB_AUX_DP` | **open** | 4/5 | 191.0 mm |

How a pair is routed: the two hub pins get a short coupled stub straight out to a ring around the chip (a 4 mm ring
around the USB 3 hub and a 3 mm ring around the USB 2 hub are kept free of parts on both faces for this); from there a
trunk is searched as ONE wide track and drawn as two, changing layer with a pair of vias; the last millimetre or two to
each pad is two single tracks. Where no trunk could be found the two nets are routed singly (the report says which).
A link from the processor to a hub is made in three pieces - out from under the RK3566, up the right-hand corridor,
along the strip - so its two wires change layer several times and differ in length by some millimetres.

**What is not routed, on purpose**
- **The memory bus** (class DDR): see 5.2a.
- **The Ethernet head** (box x > 10.6, y < 8.0 in the board's design coordinates): see blocker 2 in section 0. The HDMI
  connector beside it is routed.
- **Planes under the PoE primary and the Ethernet head.** Nothing is poured there, so the isolation barrier is not
  compromised by a script.

**Read this before trusting the routed part**
- It is maze-router output: electrically connected and checked against the design rules, not hand-optimised.
- KiCad's design-rule check on the routed copper reports 109 items {'hole_clearance': 1, 'clearance': 5, 'track_dangling': 61, 'via_dangling': 8, 'isolated_copper': 34}; `build/routing_report.txt` lists them.
  Loose track ends and vias (`track_dangling`, `via_dangling`) and unconnected pour fragments (`isolated_copper`) are
  untidy, not shorts; anything else in that list is a defect to fix by hand. In the last run the `clearance` items are
  vias of pair trunks that a later track passes about 0.09 mm from instead of 0.10 mm (the router rounded those vias
  onto its grid; corrected in `tools/route.py`, so they go with the next rebuild), and the `hole_clearance` item is one
  track beside a via under the RK3566.
- Pair lengths are whatever came out. For USB 2.0 that is harmless at these lengths. For SuperSpeed (5 Gbit/s) the
  usual rule is 0.13 mm between the two wires of a pair; the report shows what each pair has, and several are far from it.
- `USB_AUX` (USB 2 hub to the front battery port) and `USB2_HOST2` (processor to the USB 2 hub) are each well over
  200 mm long. That is beyond the usual 150 mm guideline for high-speed USB 2.0 on FR-4 and should be measured.
- Under the RK3566 a through-via in a ball is only legal where the next ball is 0.4 mm away or more; the script
  checks that per ball. A top-side part must not sit over a pair ball: the placement keeps those spots free.
- The supply pours on In3 are rectangles around each net's pads, the smaller net winning where two overlap. Whatever a
  pour did not reach shows up as an open connection. This is a starting point for a power-integrity review, not a result of one.
- The PoE primary is packed with 0.45 mm between parts and routed with 0.4 mm tracks, 0.2 mm apart (57 V under solder
  mask; IPC-2221B asks 0.13 mm). Exposed pads of different primary nets are closer than 0.5 mm at the 0402 parts: have
  that looked at, or coat the area.
- The two hub buck converters (U41, U42) are connected but their placement is a row packing, not a proper switch-node
  layout. Re-place and re-route them by hand.
- A full rebuild takes about an hour and a quarter. **Hand routing done in KiCad is lost by a rebuild** — once you
  start routing by hand, stop rebuilding (see section 6).

**The floorplan problem that routing exposed is fixed.** In the first placement the PoE primary sat on
the left of the column, between the micro HDMI and the SoC, so the HDMI pairs and the 48 V input had to
cross. The head of the column is now laid out in three lanes (decision of 2026-11-12, see section 3).

### 5.2 The PoE converter is a first pass
- **Transformer.** A real part is fitted: Bourns PLN060-ER20A05S, planar, 8.0 mm, on the **bottom face** with its
  primary row towards the rear (section 3). The top face above it is free for low parts, but the 2 mm
  rule around the primary pins applies on every layer.
- Current sense, clamp, bias and loop compensation are textbook starting values, now worked through once for
  the chosen transformer (section 3) but not validated: they need a bench check.
- The low-voltage side is routed by script, with copper pours added on the 5 V output path (rectifier, output
  capacitors, inductor), which carries more than 4 A. Nobody has checked the width of the narrowest neck:
  do that before trusting it at full load.
- The isolation barrier is drawn on the board and measured by `tools/check_isolation.py`, but not yet
  enforced by KiCad rule areas — add them before hand-routing the head of the column.
- The Ethernet head itself (RJ45, magnetics, Bob-Smith network, PHY) keeps Radxa's arrangement, where the
  PHY sits on top above line-side parts on the bottom. With PoE that stack-through deserves its own review.

### 5.2a The memory bus: tried, and not good enough
You asked for the RK3566-to-LPDDR4 connections with one simple rule, every path the same length. I tried it
(`tools/route_ddr.py`, on a copy of the board; nothing of it is in the project's board file):

- With the finest features the board allows (0.09 mm tracks, 0.25 / 0.15 mm vias placed in the BGA pads, three
  signal layers) the scripted router connected **52 of the 73 memory nets** end to end. More passes did not
  help; they made it worse. Both clock lines, several data bits and data-mask lines are among the 21 it
  could not reach, so the bus as a whole does not work.
- The connected nets came out between 5.6 and 22.9 mm long, with 2 to 17 mm of difference inside each group
  that has to match. Equalising them means adding up to 17 mm of detour per net in the 3 mm gap between the two
  packages, which is already full.
- Equal length on the board is also not the whole rule. The lengths inside the two chip packages differ from
  ball to ball and have to be compensated; each data group is matched to its own strobe and the commands to
  the clock; the pairs are differential; every signal needs an unbroken ground plane beside it.

This is the one part of the board where the honest answer is that a script is the wrong tool. Rockchip
publishes a reference layout for exactly this interface because it is easier to copy than to re-derive,
and Radxa's board is such a copy. The way to a working core is a layout engineer placing that template
(mirrored, since the core is on the bottom face), not a longer run of this router.

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
- **Cost against the 25 USD target.** `fabrication/estimated-cost.csv` (from `tools/make_cost_estimate.py`) prices every
  BOM line for 5 to 100,000 boards with the stock found at LCSC / JLCPCB and elsewhere. Components alone come to about
  72 USD at 100 boards and 47 USD at 100,000; with board, assembly and test about 96 and 57 USD. SoC, memory and eMMC are
  about 19 USD of that at 100 boards. It is a budget built from price snapshots, not a quotation.
- **Parts to settle before production** (same file, section 2): the planar PoE transformer (single source, almost no stock),
  the JAE 24-pin USB-C receptacles (not stocked at LCSC, 3 USD each - a mainstream Chinese part is a tenth of that), the
  LPDDR4 (Samsung part discontinued, alternatives out of stock), and the Rockchip and Microchip USB 3 hub parts, which
  LCSC holds only in small numbers.
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
  tools/route.py                planes + scripted routing in stages (5.1); build/routing_report.txt
  tools/report_open.py          what is still open, by class, area and net; build/open_report.txt
  tools/report_usb.py           every USB net: complete or not, length, pair difference; build/usb_report.txt
  tools/transplant_copper.py    copies the routing of one board file into another with the same placement
  tools/make_quote_package.py   Gerbers, drill, JLC-style BOM and placement, marked QUOTE-ONLY
  tools/make_cost_estimate.py   fabrication/estimated-cost.csv: cost for 5 ... 100,000 boards, stock and risk per part
  tools/route_ddr.py            the memory-bus experiment (works on a copy; see 5.2a)
commander/pcb/commander_strip_test/                           the test-board variant (same tools, --variant strip_test)
commander/schematics/commander_mainboard_revA1_schematic.pdf
commander/fabrication/bom/commander_mainboard_revA1_bom.csv
commander/fabrication/position/commander_mainboard_revA1_{top,bottom}.pdf, _placement.csv
```

The schematic and board are **generated**. To change the circuit, edit `src/netlist/*.net` and
run `python tools/build.py`; edits made in the KiCad schematic editor are overwritten by the
next build. The scripted routing is regenerated too (about an hour and a quarter), so nothing is lost by a rebuild *today*.
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
