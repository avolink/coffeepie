#pragma once

/* Commander keyboard, RP2040 (written by pcb/commander_mainboard/tools/kbd_qmk.py - pins from the board's
 * GPIO plan, build/kbd_rp_plan.json).  Net names are the Arduino pin names of the prototype. */

/* program flash: GigaDevice GD25Q16E (2 MB) - its boot stage 2 */
#define RP2040_FLASH_GD25Q64CS

/* rows A0..A5: driven low one at a time */
#define MATRIX_ROW_PINS { GP21, GP22, GP1, GP24, GP25, GP26 }
/* columns (SCK MISO D13 D12 D11 D10 D9 D8 D7 D6 D5 D4 D3_SCL D2_SDA SS_RXLED MOSI): 10 k pull-ups to 3.3 V on the board */
#define MATRIX_COL_PINS { GP2, GP3, GP20, GP19, GP18, GP23, GP17, GP16, GP11, GP14, GP9, GP8, GP7, GP6, GP4, GP10 }

/* the infra-red LEDs of all keys: high = on (Q1 through the jumper J1, net D0_RX) */
#define OPTICAL_LED_EN_PIN GP0
/* the Commander's power key output (Q201 pulls the mainboard's PMIC_PWRON low while it is high) */
#define POWER_KEY_PIN GP12
/* T16 (top row, last key) is the power key: matrix row 0, column 15 */
#define POWER_KEY_ROW 0
#define POWER_KEY_COL 15

/* phototransistor settling time after a row is driven low, microseconds */
#define OPTICAL_SETTLE_US 30
/* 1: a pressed key lets the light through (its column reads low).  If every key reads pressed at rest,
 *    the switches work the other way round: set 0. */
#define OPTICAL_PRESSED_WHEN_LIT 1
