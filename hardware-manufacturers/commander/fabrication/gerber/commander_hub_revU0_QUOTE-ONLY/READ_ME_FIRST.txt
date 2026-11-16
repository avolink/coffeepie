commander_hub revU0 - QUOTATION PACKAGE - NOT FOR MANUFACTURE

These files are for getting a PRICE. Do not let a fabricator build from them: the routing is not finished.

Board
  layers            6, 0.8 mm, FR-4
  outline           a strip, 291.7 x 21.7 mm, plus an M.2 card tongue (19.85 mm wide, 4 mm long, Key M
                    notch) on its left end; milled
  copper            F.Cu sig / In1 GND / In2 sig / In3 power / In4 GND / B.Cu sig
  what to quote     smallest track / gap 0.09 / 0.09 mm, smallest via 0.25 mm pad / 0.15 mm hole,
                    impedance-controlled stack-up (USB 3 pairs)
                    (the fine features are used under the QFN hubs only; elsewhere tracks are 0.10 mm or
                    wider and vias 0.45 / 0.20 mm or larger)
  card edge         M.2 Key M gold fingers on the left end: ENIG (hard gold if offered), fingers bevelled
                    20 deg, no copper or solder mask in the key notch - the card plugs into an M.2 socket
Assembly
  parts placed      199 on 36 BOM lines, both sides (116 top, 85 bottom) - including DNP positions in the CPL
  finest packages   USB5744 / USB2517 QFN (0.4 / 0.5 mm), 0.5 mm-pitch Type-C muxes, nine USB-C receptacles
  not in the BOM    manufacturer part numbers / LCSC numbers: values and packages only, so the assembler's
                    price for parts is an estimate until they are filled in
Files
  *.gbr / *.g*      copper, solder mask, paste, silkscreen, outline
  *.drl             plated and non-plated holes, millimetres, absolute origin
  ../../bom/commander_hub_revU0_bom_jlc.csv          parts list
  ../../position/commander_hub_revU0_cpl_jlc.csv     placement (rotations follow KiCad; JLCPCB will want some corrected)

Known not to be finished (see pcb/commander_mainboard/DESIGN_NOTES.md, section 0)
  - routed by script, not reviewed by a layout engineer: differential pairs are coupled but neither
    impedance-verified nor length-tuned
  - 4951 track segments are in the file; connections still open:
  (run tools/build.py for the list of open connections)
