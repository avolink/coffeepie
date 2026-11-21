commander_keyboard revK1 - PROTOTYPE PACKAGE

The keyboard of the Commander terminal: the prototyped Altium design (Teclado_V2), converted to KiCad, with the
Arduino Micro module replaced by an ATmega32U4 circuit soldered on the board.

State
  every connection is made (KiCad: 0 unconnected); design-rule check: 45 remarks, listed in pcb/commander_keyboard/README.md
  the new copper was drawn by script and has not been reviewed by a layout engineer; the copper of the proven
  prototype (switch matrix, zones) is unchanged

Board
  layers            2, FR-4, 1 oz
  thickness         1.6 mm ASSUMED (the Altium file carries only its default stack-up) - confirm before ordering
  outline           about 315.1 x 135.0 mm, milled; 84 round switch holes and 104 slots / cut-outs inside
  finest features   track / gap 0.15 / 0.15 mm; vias 0.5 mm pad / 0.3 mm hole beside the QFN (elsewhere 0.6 / 0.3
                    and larger) - within the ordinary 2-layer service of JLCPCB / PCBWay
Assembly
  parts placed      291 on 20 BOM lines: 271 on the top face (as in the prototype), 20 on the bottom face
                    (the ATmega32U4 circuit, where the Arduino module used to be) - so both faces are assembled
  finest package    QFN-44, 0.5 mm pitch (ATmega32U4-MU); USB-C receptacle, 16 pins
  to confirm        the 84 key positions T1..T84 are in the parts list and the placement file exactly as the Altium
                    design has them (one six-pad part each): tell the assembler whether that is a part they solder
                    or the plug-in switch that is fitted afterwards, as on the prototype
  not in the BOM    manufacturer / LCSC part numbers: values and packages only
  after assembly    the ATmega32U4 is delivered without the Arduino bootloader: it has to be programmed once through
                    the six ISP pads on the bottom face (see the README)
Files
  *.gbr / *.g*      copper, solder mask, paste, silkscreen, outline
  *.drl             plated and non-plated holes, millimetres, absolute origin
  ../../bom/commander_keyboard_revK1_bom_jlc.csv          parts list
  ../../position/commander_keyboard_revK1_cpl_jlc.csv     placement (rotations follow KiCad; JLCPCB will want some corrected)
