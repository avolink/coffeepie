# Commander tray carrier (KiCad 10), revision R0

The sliding tray of the Commander takes **two Framework Laptop 16 input modules of the B size** (67.95 x 131.02 x
3.75 mm: the Numpad, the RGB Macropad, or any module built to Framework's open specification). This board is what they
plug into: an 18 mm wide, 0.8 mm thick strip that lies in a channel of the tray floor under the modules' contact edge,
with Framework's spring (pogo) contacts and the magnets that hold the modules. Upstream it needs one USB 2.0 port on a
USB-C receptacle at the tray's inner end - in the Commander the hub board's free port (see *The Commander side*), on its
own any computer: the tray is then simply a USB device with two Framework modules on it.

**Status (2026-11-17): generated layout, not reviewed by a person; strip 12 mm longer (see *Mechanics*).** Schematic
complete (ERC clean); model / schematic / board identical pad by pad (157 pads); 42 parts, 26 of 29 nets routed on two
layers, the 5 V and 3.3 V trunks pre-drawn along the bottom face, ground pours on both faces. KiCad DRC: **3 nets
open** - `M2_SLEEP_N`, `VCC3V3` and `VCC5` (15 unconnected items with the ground pads that have no stitching via yet),
2 starved thermals. Some minutes in KiCad. (Before the extension: `USB_UP_DM`, `VCC5`, `VCC5_M2` were open.)

Rebuild (from the mainboard folder): `python tools/build.py --variant tray` (board: `tools/small_board.py`).

## Why Framework modules

The tray of the chassis model is already sized for them: its two bays are 131 mm across with 68 mm per bay, and a
module of 3.75 mm on the tray floor ends 0.3 mm below the rails. Framework publishes the interface, the mechanical
drawings and the firmware (CC BY 4.0, github.com/FrameworkComputer/InputModules), the modules are hot-swappable USB
devices, and users can make their own. That fits all five goals: modules last (QMK keyboards, metal plate), are repaired
or replaced one by one, swap between numpad / macropad / LED matrix / custom without tools, and the carrier itself is a
cheap strip of two-layer board.

## The interface (system side, Framework's pinout)

| Pin | Signal | Here |
|---|---|---|
| 1, 7 | GND | ground |
| 2 | VCC_5V (up to 500 mA) | bay's 5 V switch (SY6280, limit 0.62 A) |
| 3 / 5 | USB D- / D+ | the bay's CH334P port, ESD array at the contacts |
| 4 | BOARD_ID (module pulls it to ground: 270 k numpad / macropad, 68-180 k generic) | 2.2 M pull-up, presence detector |
| 6 | SLEEP# (3.3 V = host awake) | 10 k to the bay's switched 3.3 V (always "awake"; the host suspends USB instead) |
| 8 | VCC_3V3 (up to 100 mA) | bay's 3.3 V switch (SY6280, limit 0.40 A, its smallest setting) |

**Uncovered contacts are dead.** The Framework Laptop 16 powers its input modules only when every connector is
covered. Here each bay does it alone: with a module in place its BOARD_ID resistor holds the pin below 0.7 V, the
detector FET lets go and the bay's two switches come on about 0.6 s later (1 M into 1 uF); without a module, or while a
module slides in or out over the contacts, the pins carry no power. Pulling the module out switches the bay off at once.

## Mechanics (from Framework's B-size drawing and STEP, checked in COMMANDER_Z3E.skp)

- **Where.** The modules lie as in the laptop: contact edge toward the user, i.e. toward the tray's front. A module
  rests with its rear lip under the tray's rear rail: module at chassis X 8.95-139.97 (the floor ends 1.5 mm further,
  at the front ramp, X 141.5). Framework's drawing and STEP put one contact block per module, 7.0 mm in from the
  contact edge (X 132.97) and 16.96 mm from the module's left edge seen from the front (Framework's firmware expects
  the board-ID contacts "at the very left of the module"); the module's steel plate has a 10.6 mm window over the pads
  and a second, empty one at the mirrored place (no contacts there). The strip runs along the tray (chassis Y) at
  X 119.07-137.07: the parts in its 12 mm under the module's thinner contact zone, only tracks in the 6 mm under the
  module's body (which rests on the floor) - the 5 V and 3.3 V trunks run there. Checked in COMMANDER_Z3E.skp
  (2026-11-17) against Framework's module models in both bays: pogo arrays within 0.05 mm of the pad blocks; the
  magnets 7.9 mm either side of each block, on the steel next to the window. (Until then the strip was 3.93 mm further
  forward, X 123-141, for a module pushed against the front ramp, where it does not fit.)
- **Heights.** The module's contact edge is 1.5 mm thinner than its body (Framework leaves that step for the
  connector). The strip's top is 0.1 mm below the tray floor and the plungers work at 1.6 mm, so they meet the pads at
  the module's contact plane. Everything on the strip is under 1.2 mm except the USB-C receptacle, which sits at the
  inner end where no module is.
- **Length (2026-11-17).** The strip is 166.2 mm long (was 154.2): in the model the USB-C receptacle at the inner end
  hit the tray's dust barrier, so the strip grew 12 mm at that end and the receptacle moved with the edge; everything
  else stayed where it was (the outer end is still at chassis Y 476.5, the inner end is now at Y 310.3, 12 mm past
  the drawer's inner end at Y 322.3). The case needs room for that 12 mm when the drawer is closed.
- **The floor slopes.** The tray floor of the model falls toward the front by about 0.7 deg (Z 10.2 at the rear rail,
  8.6 at the front one); modules and strip follow it.
- **Floor channel.** The tray floor needs a channel 18.2 mm wide and 0.9 mm deep along its length (X 118.97-137.17). The
  tray is an extrusion along Y, so the channel comes with the profile at no cost - but the model's floor is only
  1.2 mm thick (Z 7.5-8.7 at the front), which would leave 0.3 mm under the channel: the profile wants a thicker floor
  (about 2 mm) along that band, or the strip sits on the floor and the modules on 0.9 mm shims.
- **Magnets.** Eight 5 x 2 mm N52 discs, glued into the strip's holes and resting on the channel floor, under both
  halves of each module's steel contact plate (7.9 mm either side of each half's centre, as in Framework's own
  reference module); their tops end 0.4 mm under the plate.
- **Fixing.** Two M2 screws (one between the bays, one at the outer end) into the tray floor; the pogo pins' solder
  tails stand 0.4 mm under the strip - a polyimide tape on the channel floor insulates them from the aluminium.

## The Commander side

The free USB 2.0 port is **port 7 of the USB2517 on the hub board** (pins 55 DM / 56 DP, PRTPWR7 36, OCS7_N 37 - listed as
unused in `commander_hub/src/netlist/32_usb2_hub.net`). It is not on the mainboard: the mainboard's four root ports are
taken (USB3 HOST1 -> USB5744, USB2 HOST2 -> USB2517, HOST3 -> keyboard, OTG -> service port). Bringing port 7 out is the
same circuit as a USB 2.0 bay (USB-C receptacle, AP22804 power switch on PRTPWR7 / OCS7_N, USBLC6, 56 k Rp on CC) at the
hub board's end nearest the tray, and a short USB-C cable with a service loop for the tray's 155 mm of travel. Not done
in this revision of the hub (its layout is still open).

## Do they fit? (2026-11-16, after the modules were turned and shortened in the model)

Framework's drawing gives the B module's body as **131.02 x 67.95 mm** (131.5 with the lip at the far edge) - the same
as the placeholders of the model (131.07 x 68 and 131.02 x 68.03) that fit the prototype. The model of the module made
from Framework's STEP is not longer in the body; what made it look longer is the plate **tongue** (13.4 mm beyond the
contact edge, see 3. below). Shortening the model to about 123 mm makes it 8 mm shorter than the real module.

**Alternative raised: one touch surface instead of two modules.** A single two-layer board over both bays (about 131 x
136 mm) with the digits in silkscreen on a black mask, the touchpad's electrode grid (`commander_touchpad`'s IQS550 + STC8H
circuit) across the whole surface, and a low-profile slide switch: in touchpad mode the surface is a trackpad, in numpad
mode a tap on a printed digit sends that key. Cost about $4-5 at 10k (against about $78 retail for the two Framework
modules), no moving parts, but no key travel. The IQS550 drives at most 15 x 10 electrodes, i.e. about 9 x 13 mm pitch
over that area: plenty to tell 24 keys apart, coarser than a laptop touchpad for pointing (two controllers, one per bay,
would halve it). Not designed yet.

## Before ordering

1. **Check the pin order on a real module** with a meter before the first power-up: the contact block's orientation
   was taken from Framework's adapter and reference module (pin 1 = ground, on the row nearer the module's edge, on the
   module's left seen from the front). Pins 2 (5 V) and 8 (3.3 V) would trade places if it were mirrored.
2. **The pogo connector** (CFE BP33242-08200H0-FS, the part on Framework's adapter) is not stocked at LCSC; order it from
   CFE or replace it by eight single SMD pogo pins of 1.6 mm working height on the same pads.
3. **The tongue.** Framework modules have a thin plate tongue (27.7 mm wide, 13.4 mm long, 3.3 mm above the module's
   bottom) beyond their contact edge, which slides under the laptop's palm rest. With the contact edge at the front it
   meets the front rail (whose top is at 10.4-12.5 there): the rail needs a slot 28 mm wide for it, or the tongue (it is
   part of the plate held by three M2 screws) is shortened on modules used here.
4. **Sliding in.** If modules slide into the tray along the rails (rather than drop in from above), the plungers scrape
   along the module's pad rows. Framework's touchpad works that way; the power gating above keeps it harmless, but the
   module's plate edge should be checked for catching on the plungers.
5. **Routing**: see status; review of the layout as a whole by a person.

## Parts (LCSC)

CH334P C5373042, SY6280AAC C55136, ME6211C33M5G C82942, USBLC6-2SC6 C2827654, HOAUC HYCW498 USB-C C42400252;
12 MHz 3225 crystal, 2N7002, 1206 PTC and passives by JLC's BOM matcher. Pogo connector: CFE BP33242-08200H0-FS (not at
LCSC). Magnets: 8 x N52 5 x 2 mm. BOM: `../../fabrication/bom/commander_tray_revR0_bom.csv`.

Credits: interface, pinout, land pattern of the pogo connector and module dimensions from Framework Computer Inc,
github.com/FrameworkComputer/InputModules (CC BY 4.0); CH334P, SY6280AAC and ME6211 pinouts from the JLCEDA/EasyEDA Official
Library (https://easyeda.com).

Licence: CERN-OHL-S v2 + Coffee Pie Circular Economy Addendum (see `hardware-manufacturers/LICENSE`).
