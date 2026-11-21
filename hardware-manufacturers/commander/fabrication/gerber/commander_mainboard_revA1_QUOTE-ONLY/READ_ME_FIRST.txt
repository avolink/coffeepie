commander_mainboard revA1 - QUOTATION PACKAGE - NOT FOR MANUFACTURE

These files are for getting a PRICE. Do not let a fabricator build from them: the routing is not finished.

Board
  layers            6, 1.2 mm, FR-4
  outline           L-shaped, about 324.8 x 138.4 mm (rounded corners), milled; one RJ45 notch
  copper            F.Cu sig / In1 GND / In2 sig / In3 power / In4 GND / B.Cu sig
  what to quote     smallest track / gap 0.09 / 0.09 mm, smallest via 0.25 mm pad / 0.15 mm hole,
                    via-in-pad (filled, capped) under the 0.4 mm-pitch BGA, impedance-controlled stack-up
                    (the fine features are used under the BGA packages only; elsewhere tracks are 0.10 mm or
                    wider and vias 0.45 / 0.20 mm or larger)
Assembly
  parts placed      640 on 169 BOM lines, both sides (406 top, 282 bottom) - including DNP positions in the CPL
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
  - 11114 track segments are in the file; connections still open:
  commander_mainboard.kicad_pcb: 784 open connections on 375 nets (526 nets in all)
  connections made: 1570 of 2354 (66.7 %)
  tracks by layer: B.Cu 3237 mm, F.Cu 4002 mm, In2.Cu 2884 mm, In3.Cu 227 mm; vias: 941
  
  by net class:
    Default        416
    DDR            74
    PWR            59
    USB3_SS        53
    POE_PRIMARY    38
    ETH_MDI        36
    PWR_5V         33
    HDMI           33
    RGMII          31
    USB2           11
  
  by area (where the net's pads are):
    core                         218
    strip                        137
    core+front+head+poe+strip    137
    head                         91
    core+head                    41
    poe                          31
    head+poe                     30
    core+front                   29
    core+front+strip             19
    core+front+head+poe          11
    core+strip                   10
    core+poe                     6
    front                        6
    core+front+poe+strip         5
    front+head+poe               4
    core+front+poe               4
    core+head+poe                3
    core+front+head              1
    front+strip                  1
