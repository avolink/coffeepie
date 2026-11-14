commander_strip_test revT0 - QUOTATION PACKAGE - NOT FOR MANUFACTURE

These files are for getting a PRICE. Do not let a fabricator build from them: the routing is not finished.

Board
  layers            4, 1.2 mm, FR-4
  outline           L-shaped, about 324.8 x 138.4 mm (rounded corners), milled; one RJ45 notch
  copper            F.Cu sig / In1 GND / In2 5 V / B.Cu sig
  what to quote     smallest track / gap 0.09 / 0.09 mm, smallest via 0.25 mm pad / 0.15 mm hole,
                    via-in-pad (filled, capped) under the 0.4 mm-pitch BGA, impedance-controlled stack-up
                    (the fine features are used under the BGA packages only; elsewhere tracks are 0.10 mm or
                    wider and vias 0.45 / 0.20 mm or larger)
Assembly
  parts placed      288 on 83 BOM lines, both sides (200 top, 94 bottom) - including DNP positions in the CPL
  finest packages   FCCSP-565 with 0.40 mm ball pitch, BGA-200 (0.65 x 0.8 mm), BGA-153 (0.5 mm), QFN 0.35 mm
  not in the BOM    manufacturer part numbers / LCSC numbers: values and packages only, so the assembler's
                    price for parts is an estimate until they are filled in
Files
  *.gbr / *.g*      copper, solder mask, paste, silkscreen, outline
  *.drl             plated and non-plated holes, millimetres, absolute origin
  ../../bom/commander_strip_test_revT0_bom_jlc.csv          parts list
  ../../position/commander_strip_test_revT0_cpl_jlc.csv     placement (rotations follow KiCad; JLCPCB will want some corrected)

Known not to be finished (see pcb/commander_mainboard/DESIGN_NOTES.md, section 0)
  - routed by script, not reviewed by a layout engineer: differential pairs are coupled but neither
    impedance-verified nor length-tuned
  - 5716 track segments are in the file; connections still open:
  commander_strip_test.kicad_pcb: 259 open connections on 155 nets (243 nets in all)
  connections made: 725 of 984 (73.7 %)
  tracks by layer: B.Cu 2704 mm, F.Cu 2949 mm; vias: 561
  
  by net class:
    Default        105
    USB3_SS        68
    POE_PRIMARY    42
    PWR            22
    USB2           13
    PWR_5V         9
  
  by area (where the net's pads are):
    strip                        164
    front+poe+strip              44
    poe                          40
    head+poe                     6
    front+poe                    3
    front                        1
    front+strip                  1
