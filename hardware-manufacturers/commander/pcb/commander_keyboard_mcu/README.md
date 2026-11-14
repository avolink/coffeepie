# Commander keyboard — ATmega32U4 core (KiCad 10), revision K0

> **Superseded (2026-11-14).** The keyboard PCB is now in the repository as `../commander_keyboard/`, with this
> circuit placed on it (QFN package, USB-C on the board edge). Change the circuit there
> (`commander_keyboard/src/netlist/01_kbd_mcu.net`); this project is kept as the first, schematic-only draft.

The microcontroller circuit of the **Arduino Micro**, reduced to what a bus-powered USB keyboard needs,
so the ATmega32U4 can be soldered straight onto the keyboard PCB instead of a hand-soldered Micro.

**This is a schematic block, not a board.** The keyboard PCB itself is not in this repository; this
project is the part to copy into it. Schematic: `commander/schematics/commander_keyboard_mcu_revK0_schematic.pdf`.
Source: `src/netlist/01_keyboard_mcu.net`. Rebuild from the mainboard folder with
`python tools/build.py --variant keyboard_mcu`.

**Status: generated from the ATmega32U4 pin-out in the KiCad library and the Arduino Micro's published
circuit; not built, not yet checked against the keyboard prototype.** ERC reports only the 22 free I/O
labels, which is expected: they are the connection points for the key matrix.

## What is in it

| Kept from the Arduino Micro | Left out | Changed |
|---|---|---|
| ATmega32U4 and its pin assignment | 5 V and 3.3 V regulators, VIN path | micro-USB → **USB-C** (5.1 kΩ on both CC pins) |
| 16 MHz crystal | RX / TX / L / power LEDs | two varistors → one USBLC6-2 ESD array |
| 22 Ω USB series resistors, 1 µF on UCAP | pin headers | ferrite + capacitor on AVCC |
| HWB pull-down, reset pull-up and button | | |
| 500 mA resettable fuse, ISP pins | | |

25 parts. The USB-C side matches the keyboard port on the Commander mainboard (J20), which is a host
port with Rp on CC: a plain USB-C cable connects the two.

## Pin names

Nets carry the **Arduino pin names**, so the existing firmware and matrix wiring carry over unchanged.

| Arduino | MCU pin | | Arduino | MCU pin | | Arduino | MCU pin |
|---|---|---|---|---|---|---|---|
| D0 (RX) | PD2, 20 | | D8 | PB4, 28 | | A0 | PF7, 36 |
| D1 (TX) | PD3, 21 | | D9 | PB5, 29 | | A1 | PF6, 37 |
| D2 (SDA) | PD1, 19 | | D10 | PB6, 30 | | A2 | PF5, 38 |
| D3 (SCL) | PD0, 18 | | D11 | PB7, 12 | | A3 | PF4, 39 |
| D4 | PD4, 25 | | D12 | PD6, 26 | | A4 | PF1, 40 |
| D5 | PC6, 31 | | D13 | PC7, 32 | | A5 | PF0, 41 |
| D6 | PD7, 27 | | MISO | PB3, 11 | | SS / RXLED | PB0, 8 |
| D7 | PE6, 1 | | SCK / MOSI | PB1, 9 / PB2, 10 | | TXLED | PD5, 22 |

## Things to know before copying it

1. **Bootloader.** A factory-fresh ATmega32U4 does not contain the Arduino bootloader (it ships with
   Microchip's DFU bootloader). Each board needs the Arduino Micro bootloader burned once through J102
   (ISP), after which it updates over USB exactly like the prototype. J102 can be six test pads instead of
   a header.
2. **PB0 and PD5 blink during the bootloader.** The Arduino bootloader drives the RX and TX LED pins for a
   few seconds after reset. If the matrix uses those two pins, nothing breaks, but do not hang anything on
   them that minds being toggled.
3. **Crystal capacitors.** 15 pF suits a 3225 crystal with 10 pF load capacitance. Use the value that
   matches the crystal actually bought (the Micro's own crystal uses 22 pF).
4. **Package.** Drawn with the TQFP-44 (ATmega32U4-AU), which is easy to assemble and inspect. The QFN-44
   (-MU, as on the Micro) has the same pin numbers plus a ground pad.
5. **The reset button** is what lets a technician get into the bootloader if a bad firmware is loaded.
   Keep it, or at least keep two pads for it.

## Still needed

The keyboard PCB design files (and ideally the firmware): to check which Arduino pins the matrix really
uses, to place this block on the board, and to confirm the keyboard's own reference numbers.

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
