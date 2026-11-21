# Commander keyboard (QMK)

The Commander's 84-key optical keyboard (pcb/commander_keyboard), Raspberry Pi RP2040 since 2026-11-19.

* Keyboard maintainer: Coffee Pie
* Hardware: pcb/commander_keyboard (KiCad), RP2040 + GD25Q16E flash, Keychron low-profile optical switches

Build (copy this folder to `qmk_firmware/keyboards/coffeepie/commander` first):

    qmk compile -kb coffeepie/commander -km via

Flashing: hold the BOOTSEL button (SW201, bottom face) while plugging in the USB-C cable - the board shows up as a
drive called RPI-RP2; copy the .uf2 file onto it.  Later: Fn + Esc (QK_BOOT), or hold Esc while plugging in
(bootmagic).

VIA: VIA does not know this keyboard yet - in VIA, Settings > "Show Design tab", then Design > Load
`../commander_via.json`.

The optical matrix is scanned by `matrix.c`: the infra-red LEDs (Q1) are on only while the USB host has configured
the keyboard; otherwise only T16 - the Commander's power key, wired to the mainboard's power-key line through Q201 -
is read.  `OPTICAL_PRESSED_WHEN_LIT` in config.h sets which way the switches work (not yet checked on a board).

| Line (net) | GPIO |
|---|---|
| A0 | GP21 |
| A1 | GP22 |
| A2 | GP1 |
| A3 | GP24 |
| A4 | GP25 |
| A5 | GP26 |
| SCK | GP2 |
| MISO | GP3 |
| D13 | GP20 |
| D12 | GP19 |
| D11 | GP18 |
| D10 | GP23 |
| D9 | GP17 |
| D8 | GP16 |
| D7 | GP11 |
| D6 | GP14 |
| D5 | GP9 |
| D4 | GP8 |
| D3_SCL | GP7 |
| D2_SDA | GP6 |
| SS_RXLED | GP4 |
| MOSI | GP10 |
| D0_RX | GP0 |
| PWRKEY_DRV | GP12 |

All files here are written by `pcb/commander_mainboard/tools/kbd_qmk.py` from the board.
