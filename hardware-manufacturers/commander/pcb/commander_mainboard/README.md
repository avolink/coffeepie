# Commander mainboard (KiCad 10)

RK3566 codec core + PoE powered device + USB hubs for nine Framework expansion-card bays, on one
L-shaped PCB. Revision **A0: schematic complete, board placed but not routed — for audit.**

Read [DESIGN_NOTES.md](DESIGN_NOTES.md) first: it lists every decision, assumption and open item.

## Open it

Open `commander_mainboard.kicad_pro` in KiCad 10. The symbol and footprint libraries are
project-local (`lib/`) and are picked up through the project library tables.

## Rebuild it

```
python tools/build.py
```

Needs KiCad 10 (set `KICAD_BIN` if it is not in `C:/Program Files/KiCad/10.0/bin`). The build
regenerates the schematic and board from `src/netlist/*.net`, runs ERC and DRC, cross-checks the
netlist source against the schematic and the board pad by pad, and exports the PDF, BOM and
placement files into `commander/schematics` and `commander/fabrication`.

| Script | Does |
|---|---|
| `tools/cpmodel.py` | parses `src/netlist`, holds the part definitions, checks every pin is assigned |
| `tools/gen_usb_netlists.py` | writes the two hub netlists (the nine bays come from one template each) |
| `tools/gen_schematic.py` | symbol library + 17 schematic sheets |
| `tools/gen_footprints.py` | the six custom footprints |
| `tools/gen_pcb.py` | outline, footprints, nets, first placement (KiCad Python) |
| `tools/check_consistency.py` | model vs schematic vs board, and the RK3566 ball map vs Radxa's drawing |
| `tools/report_overlaps.py` | where the first placement still collides |
| `tools/gen_bom.py`, `tools/gen_project.py` | BOM, project file with net classes |

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
The codec core is transcribed from the Radxa ZERO 3E V1.2 reference schematic.
