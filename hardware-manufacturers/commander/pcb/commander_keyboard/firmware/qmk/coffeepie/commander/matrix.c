// Commander keyboard: the optical matrix (written by pcb/commander_mainboard/tools/kbd_qmk.py)
//
// Each key is an infra-red LED and a phototransistor.  The LEDs of all keys are switched together by Q1
// (OPTICAL_LED_EN_PIN, about 0.56 A); the phototransistors' emitters sit on the rows (driven low to scan a row),
// their collectors on the columns (10 k pull-ups to 3.3 V).  T16's LED is not on Q1 but on row 0 itself: it lights
// whenever row 0 is scanned, so T16 - the Commander's power key - is read even with the other LEDs off.
//
// The LEDs are on only while the USB host has configured the keyboard; otherwise (the Commander off, or USB
// suspended) only T16 is read, and POWER_KEY_PIN follows it in hardware terms: high while T16 is down.
#include "quantum.h"
#include "matrix.h"
#include <hal.h> // (ChibiOS: USBD1.state - USB_ACTIVE once the host has configured the keyboard)

static const pin_t row_pins[MATRIX_ROWS] = MATRIX_ROW_PINS;
static const pin_t col_pins[MATRIX_COLS] = MATRIX_COL_PINS;
static bool        leds_on               = false;

static void leds(bool on) {
    if (on != leds_on) {
        gpio_write_pin(OPTICAL_LED_EN_PIN, on);
        leds_on = on;
        wait_us(200); // (the LEDs and phototransistors settle)
    }
}

void matrix_init_custom(void) {
    gpio_set_pin_output(OPTICAL_LED_EN_PIN);
    gpio_write_pin_low(OPTICAL_LED_EN_PIN);
    gpio_set_pin_output(POWER_KEY_PIN);
    gpio_write_pin_low(POWER_KEY_PIN);
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        gpio_set_pin_output(row_pins[r]);
        gpio_write_pin_high(row_pins[r]);
    }
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        gpio_set_pin_input(col_pins[c]); // (the board has the pull-ups)
    }
}

static matrix_row_t read_row(uint8_t r) {
    gpio_write_pin_low(row_pins[r]);
    wait_us(OPTICAL_SETTLE_US);
    matrix_row_t v = 0;
    for (uint8_t c = 0; c < MATRIX_COLS; c++) {
        bool lit = !gpio_read_pin(col_pins[c]);
        if (lit == (OPTICAL_PRESSED_WHEN_LIT != 0)) v |= (matrix_row_t)1 << c;
    }
    gpio_write_pin_high(row_pins[r]);
    return v;
}

bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    leds(USBD1.state == USB_ACTIVE);
    bool changed = false;
    for (uint8_t r = 0; r < MATRIX_ROWS; r++) {
        matrix_row_t v = 0;
        if (leds_on) {
            v = read_row(r);
        } else if (r == POWER_KEY_ROW) {
            v = read_row(r) & ((matrix_row_t)1 << POWER_KEY_COL); // only T16 has its light
        }
        if (current_matrix[r] != v) {
            current_matrix[r] = v;
            changed           = true;
        }
    }
    gpio_write_pin(POWER_KEY_PIN, (current_matrix[POWER_KEY_ROW] >> POWER_KEY_COL) & 1);
    return changed;
}
