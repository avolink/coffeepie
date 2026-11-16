commander_mainboard revA1 - QUOTATION PACKAGE - NOT FOR MANUFACTURE

These files are for getting a PRICE. Do not let a fabricator build from them: the routing is not finished.

Board
  layers            6, 1.2 mm, FR-4
  outline           a column, about 33.9 x 138.3 mm (rounded corners), milled, with a small tab under
                    the M.2 socket; one RJ45 notch
  copper            F.Cu sig / In1 GND / In2 sig / In3 power / In4 GND / B.Cu sig
  what to quote     smallest track / gap 0.09 / 0.09 mm, smallest via 0.25 mm pad / 0.15 mm hole,
                    via-in-pad (filled, capped) under the 0.4 mm-pitch BGA, impedance-controlled stack-up
                    (the fine features are used under the BGA packages only; elsewhere tracks are 0.10 mm or
                    wider and vias 0.45 / 0.20 mm or larger)
Assembly
  parts placed      440 on 148 BOM lines, both sides (292 top, 186 bottom) - including DNP positions in the CPL
  finest packages   FCCSP-565 with 0.40 mm ball pitch, BGA-200 (0.65 x 0.8 mm), BGA-153 (0.5 mm), QFN 0.35 mm
  not in the BOM    manufacturer part numbers / LCSC numbers: values and packages only, so the assembler's
                    price for parts is an estimate until they are filled in
Files
  *.gbr / *.g*      copper, solder mask, paste, silkscreen, outline
  *.drl             plated and non-plated holes, millimetres, absolute origin
  ../../bom/commander_mainboard_revA1_bom_jlc.csv          parts list
  ../../position/commander_mainboard_revA1_cpl_jlc.csv     placement (rotations follow KiCad; JLCPCB will want some corrected)

Known not to be finished (see pcb/commander_mainboard/DESIGN_NOTES.md, section 0)
  - the memory bus (RK3566 to LPDDR4) is NOT routed: it needs the chip vendor's length-matched layout
  - the Ethernet head (RJ45, magnetics, PHY) is NOT routed: its isolation boundary has to be drawn by a person
  - routed by script, not reviewed by a layout engineer: differential pairs are coupled but neither
    impedance-verified nor length-tuned
  - 7019 track segments are in the file; connections still open:
  commander_mainboard.kicad_pcb: 487 open connections on 259 nets (348 nets in all)
  connections made: 1171 of 1658 (70.6 %)
  tracks by layer: B.Cu 1663 mm, F.Cu 1922 mm, In2.Cu 1006 mm, In3.Cu 227 mm; vias: 534
  
  by net class:
    Default        269
    DDR            74
    HDMI           31
    PWR            27
    PWR_5V         27
    RGMII          26
    ETH_MDI        13
    POE_PRIMARY    12
    USB2           7
    USB3_SS        1
  
  by area (where the net's pads are):
    core                         215
    core+front+head+poe+strip    77
    head                         41
    core+head                    37
    core+front                   28
    core+poe                     19
    poe                          13
    core+front+strip             12
    core+front+head+poe          9
    core+front+poe               9
    head+poe                     8
    front                        6
    core+front+poe+strip         4
    front+head+poe               4
    core+head+poe                3
    core+front+head              1
    front+poe                    1
