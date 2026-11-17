# Commander hub board (branch `m2-hub`)

The nine Framework bays, both USB hubs (USB5744, USB2517), the bays' Type-C muxes, power switches and ESD, and the
microSD slot, on their own board.  It plugs into the mainboard (`../commander_mainboard`) through an **M.2 Key M
socket** (J41 there, LOTES APCI0107-P001A H4.2, top mount, 4.05 mm; was APCI0146 H2.3): this board's left end is the card edge (J90, gold
fingers, no connector part).  The pinout is `../commander_mainboard/tools/hub_link.py`, one source for both boards.

| | |
|---|---|
| Size | 291.7 x 21.72 mm body (board x 73.0 to 364.7) + the 19.85 mm card tongue, 4 mm long |
| Thickness | **0.8 mm** (M.2 cards are 0.8 +-0.08 mm) |
| Layers | 6 for now (the strip's routing came over as it was); 4 layers is the cost step for later |
| Finish | ENIG; fingers bevelled 20 deg; no copper or mask in the key notch |
| Height | the card rests about 2.4 mm above the mainboard (H4.2 socket); the bay receptacles are sink-mount (see below) |
| Coordinates | the mainboard's own, so `route.py`'s strip region applies unchanged |

Build: `python ../commander_mainboard/tools/build.py --variant hub` (schematic, ERC, and the checks if the board
exists).  The board is not generated: `tools/hub_board.py SRC DST` cut it out of the routed mainboard (strip parts and
copper kept; the parts in the way of the card edge moved; then `route.py` with `CP_ROOT` set to this project,
`CP_REGIONS=strip --stage local`).  From here on it is edited in KiCad.

State (2026-11-15): consistent with the schematic, ERC clean, DRC only the 58 edge items inherited from the strip
(bays' rear pad row 1 mm from the edge); 215 links open, 137 of them at the left end (card edge, USB5744, bay 1),
where U40 moved 2.2 mm right and Y40 / C612 / C622 / C623 went to the bottom face.  Each finger has a straight stub
on its own face to x 72.6; route.py knows this board's outline (body + the tongue inside the socket slot, no notch).
Open mechanical point: no mounting screw near the socket end yet (the first hole, H4, is at x 138): one belongs within
10-15 mm of the socket, which needs room in the USB5744 corner.

**2026-11-15/16: the bay receptacles are now HOAUC HYCW275-USBC24-050B** (LCSC C42400261, about $0.16-0.33, in stock;
the JAE DX07S024WJ1R350 is not stocked at LCSC and costs $3.30).  `tools/hub_usbc24_swap.py` put the four new parts
J31-J34 where the JAE ones were (mating face on the same line, nets kept, the old copper round them ripped up:
817 tracks / vias).  Board now: consistent (1014 pads), ERC clean, **213 links open**.  DRC remarks and what they mean:

| DRC item | Count | Meaning |
|---|---|---|
| copper_edge_clearance | 2 | was 58; the new receptacles' rear row is further in |
| annular_width / hole_clearance | 16 / 52 | the HYCW275's own slotted shell holes and NPTH pegs as JLC's library draws them - expected for this part, check against the datasheet drawing before ordering |
| track_dangling | 141 | stubs left by the rip-up; to be cleaned when the 213 links are routed (an automatic prune also removed the finger stubs, so it was not used) |

**Fit in the chassis model (2026-11-16):** with the HYCW275 (3.26 mm tall, top mount) the receptacle centres stood
1.1 mm above the expansion cards' plugs and their tops touched the back-I/O profile (0.72 mm).  In
`COMMANDER_Z3E.skp` the hub and the mainboard were therefore lowered together: the hub's underside is now at
z 17.37 and the mainboard's at 15.87 (its top 17.07: the card's 0.3 mm above it at J41), so the receptacles' axis is
at z 19.8 - the cards' plug axis - and they clear the profile.  The standoffs are 1.5 mm (hub) / 1.7 mm (mainboard)
shorter than the boards the model had there.  What still touches: the profile holds the board's rear
edge in a low slot over the last 1.5 mm, and three parts reach into it - L42 (0.5 mm), the
microSD slot J6 (0.3 mm; its card also needs an opening in the profile) and C712 (0.1 mm).  Next layout pass: keep
the rear 2 mm free of parts, and agree the microSD opening with the profile drawing.

**2026-11-16 (later): the hub sits 2 mm higher, in the chassis' slot, on a taller socket; the bays are sink-mount.**
The user placed the hub where the profile's slot holds it (underside 2.3 mm above the mainboard's top). Two changes:

- **J41 on the mainboard: LOTES APCI0107-P001A, H4.2** (LCSC C841661, 4.05 mm tall), same land pattern as the
  APCI0146: the card rests about 2.4-2.47 mm above the mainboard (LOTES stack-up drawing) instead of 0.3 mm.
- **J31-J39: Amphenol 12402072E512A**, USB-C 24-pin, USB4 Gen3, *sink (mid) mount*, centre 0.10 mm *under* the
  board's top face (Amphenol drawing C-12402072 rev 7) - instead of 1.63 mm above it for a top-mount part. All nine
  bays use it (same centre height everywhere; on bays 5-9 the SuperSpeed pins stay unconnected). Not stocked at LCSC:
  about $1.50 (5,500) / $1.68 (1,100 reel) / $2.75 (1) from Amphenol's distributors - consigned to JLC.
  Footprint `lib/commander.pretty/USB_C_Receptacle_Amphenol_12402072E512A` (from the drawing's recommended layout;
  check it against the drawing once more before ordering). 3D model `lib/3d/Amphenol_12402072E512A.step` = Amphenol's
  STEP turned into the footprint's frame; it is Amphenol's file and stays out of git - download `sc12402072.zip` from
  amphenol-cs.com and run `tools/amph_model.py` on it if it is missing.
- Each receptacle sits in a **notch of the rear edge**, 9.42 mm wide and 7.6 mm deep behind the mouth, R0.5 reliefs at
  the inner corners (`tools/hub_midmount_swap.py`, which also put the mouths exactly where the old ones were, so the
  cards mate as before). Parts in the way moved to the nearest free spot of their bay (`tools/hub_make_room.py`, 48
  parts, the bottom-face ones off the receptacles' through-slots too); copper touching another net's pad removed
  (`tools/hub_clean_copper.py`).
- Heights in `COMMANDER_Z3E.skp`: mainboard 0.39 mm lower than before (underside 15.48, top 16.68), hub underside
  19.12 / top 19.92, receptacle centres at 19.82 = the expansion cards' plug axis. The hub ends 0.25 mm lower than
  where it was placed by hand (no standard socket height in between: H3.2 holds the card at about 1.47 mm).

Board now: consistent with the schematic (1054 pads), ERC clean, DRC: the 2 inherited J6 edge items, dangling
stubs from the rip-ups, **499 unconnected items** (was 213) - the bay areas need the router again.

**2026-11-16 (evening): nothing plugged into a bay can push voltage back into the hub.**  A charger or power bank on
a C-to-C cable, a broken USB-PD source, a bench supply on an adapter: every bay's VBUS now leaves its power switch
through a **40 V Schottky** (Nexperia PMEG4030ER-QX, SOD-123W, LCSC C5709679, about $0.09) and has a **24 V TVS**
(SMF24CA) on the connector side for ESD.  Back-feed up to 40 V is blocked; the TVS does not conduct at 20 V.  On the
connector side only 20 V-safe parts remain (TVS, a 50 V 100 nF capacitor, the 909 k VBUS-detect resistor of the
SuperSpeed bays); the 47 uF bulk capacitor, the USBLC6's supply pin and the Hi-Speed bays' 56 k Rp resistors moved to
the supply side.  The diode drops about 0.35 V at 1 A, so the PoE supply's set point went from 5.11 to **5.24 V**
(mainboard R515 9.53 k -> 9.09 k): a bay gives about 4.85 V at 1 A.  Netlist: `vbus_guard()` in
`tools/gen_usb_netlists.py`; board: `tools/hub_vbus_guard.py` (18 parts added beside the bays' switches, 37 pads
moved to their new nets, 19 tracks removed) then `hub_clean_copper.py`.  Still consistent with the schematic (1090
pads), ERC clean, DRC no shorts or clearance errors; the open links (499) are for the router as before.

What this does **not** cover: a short of 20 V onto the data or CC pins (a damaged cable or plug).  The ESD arrays
clamp spikes, not a sustained 20 V; the USB5744 / USB2517 / HD3SS3220 pins are 3.3-5 V parts.  Full protection
there needs a Type-C port protector per bay (e.g. TI TPD6S300A / ST TCPP03-M20, about $0.40-0.60 each, CC and SBU
20 V-tolerant) - an option if the bays must survive abuse with broken cables too.

**2026-11-17: re-routed.**  `route.py` now knows the receptacle notches (its hub outline takes the bay centres from
the board file and cuts the 9.42 x 7.6 mm notches with their reliefs), and its prune keeps the finger stubs (x < 73).
Run on the board: prune (1119 loose tracks / vias from the rip-ups removed), `--stage local` with
`CP_REGIONS=strip` (4 passes, best kept), prune again (48), zones refilled.  Note: the router takes the net classes
from the project file - run it on the board in this folder (or with the `.kicad_pro` copied beside a copy), otherwise
every net is routed as Default (0.15 mm VBUS, wrong clearances).  Result: consistent (1090 pads), ERC clean, DRC no
clearance errors or shorts, **308 unconnected** (was 499); `build/commander_hub.before_reroute.kicad_pcb` is the
board before.  For the hand pass:

- the open links (`build/drc.rpt`), most of them at the left end (USB5744, card edge) as before;
- VBUS neck-downs: the router used 0.15 mm where the 0.4 mm class width did not fit into the receptacles' fine-pitch
  pins - 6-16 mm per bay, pieces up to 4 mm long (one 3.6 mm piece of VBUS_SW_P1 on In2).  Fine for short necks at
  1.5 A, but widen the longer ones where there is room;
- the dangling-track items are mostly the finger stubs (by design) and GND / VCC5V_BUS stubs that end on a pour.

Fabrication notes for the order: 0.8 mm, ENIG, "gold finger bevel 20 deg" on the left end, the key notch milled.
Mount it to the chassis with a screw near the socket end and between the bays (a 292 mm board at 0.8 mm is floppy;
every Framework card pushed in loads it).  The socket is rated 25 mating cycles.
