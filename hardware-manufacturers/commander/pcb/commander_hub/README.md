# Commander hub board (branch `m2-hub`)

The nine Framework bays, both USB hubs (USB5744, USB2517), the bays' Type-C muxes, power switches and ESD, and the
microSD slot, on their own board.  It plugs into the mainboard (`../commander_mainboard`) through an **M.2 Key M
socket** (J41 there, LOTES APCI0146-P002A, top mount, 2.06 mm): this board's left end is the card edge (J90, gold
fingers, no connector part).  The pinout is `../commander_mainboard/tools/hub_link.py`, one source for both boards.

| | |
|---|---|
| Size | 291.7 x 21.72 mm body (board x 73.0 to 364.7) + the 19.85 mm card tongue, 4 mm long |
| Thickness | **0.8 mm** (M.2 cards are 0.8 +-0.08 mm) |
| Layers | 6 for now (the strip's routing came over as it was); 4 layers is the cost step for later |
| Finish | ENIG; fingers bevelled 20 deg; no copper or mask in the key notch |
| Height | the card rests 0.3 mm above the mainboard: everything on this board stands 1.1 mm higher than on the old strip |
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

Fabrication notes for the order: 0.8 mm, ENIG, "gold finger bevel 20 deg" on the left end, the key notch milled.
Mount it to the chassis with a screw near the socket end and between the bays (a 292 mm board at 0.8 mm is floppy;
every Framework card pushed in loads it).  The socket is rated 25 mating cycles.
