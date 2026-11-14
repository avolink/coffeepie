# Commander PoE HAT (KiCad 10), revision H0

The mainboard's PoE converter on a small board of its own, for a **stock Radxa ZERO 3E** used as the
codec core. The ZERO 3E keeps its own RJ45 at the rear panel; this board turns the PoE voltage into 5 V
and feeds it back through the 40-pin header, as Radxa's own PoE HAT does.

**Status: schematic only (63 parts, ERC clean). No board yet** — see "Before the board is drawn".

## How it connects

| Connector | Goes to | Carries |
|---|---|---|
| **J60** (1×4) | the ZERO 3E's 4-pin PoE header | PoE input, **up to 57 V — primary side**. Order and polarity of the four wires do not matter (diode bridges) |
| **J61** (2×20) | the ZERO 3E's 40-pin header, by ribbon cable or stacking socket | 5 V on pins 2 and 4 (3 A resettable fuse), ground on the eight ground pins. No signal pin is connected |
| **J62** (1×4) | hub strip / bays | 5 V and ground for the rest of the Commander |

The converter is the mainboard's `30_poe.net` (listed in `src/netlist/shared.txt`): TPS23754, Bourns
PLN060-ER20A05S planar transformer (8.0 mm tall), 5.11 V set point, 802.3at class 4.

Rebuild (from the mainboard folder): `python tools/build.py --variant poe_hat`

## Before the board is drawn

1. Measure on a real ZERO 3E: position of the 4-pin PoE header and of the 40-pin header, which face each
   is on, and the height available where this board will sit. Those fix the outline and the connector types.
2. Decide ribbon cable or direct stacking (a ribbon needs about 10 mm above the header for the plug).
3. The converter's loop values are first-pass and not bench-tested; the primary side needs a hand layout
   with 2 mm isolation, as on the mainboard (DESIGN_NOTES.md, section 0, item 3).

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
