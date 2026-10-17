// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>
#include <stdbool.h>

// Stable Zephyr-facing board API. The same calls will be exposed to SmallVM
// primitives later; no direct Arduino/ESP-IDF dependency in this layer.
struct rlcd_device_status {
    bool display, shtc3, rtc, buttons, adc, i2c, spi, sd;
};

struct rlcd_environment {
    int32_t temp_milli_c;
    int32_t humidity_milli_pct;
};

void rlcd_probe(struct rlcd_device_status *out);
int rlcd_environment_read(struct rlcd_environment *out);
int rlcd_rtc_read(char *dst, unsigned dst_size);
int rlcd_battery_read(int32_t *raw, int32_t *mv_estimate);
int rlcd_display_checkerboard(void);
int rlcd_display_clear(bool white);
int rlcd_display_text(const char *text);
bool rlcd_button_pressed(unsigned index);
