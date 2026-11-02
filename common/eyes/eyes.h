/* SPDX-License-Identifier: MIT */
#ifndef MB_EYES_H
#define MB_EYES_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Portable facade; RoboEyes implementation is GPL-3.0-or-later. One instance. */
typedef struct {
    int height, controller, address; /* controller: 0 SSD1306, 1 SH1106 */
    int mood, x, y, width, eye_height, radius, spacing;
    bool autoblink, idle, curious, cyclops, sweat, alignment;
    int blink_interval, blink_variation, idle_interval, idle_variation;
    int horizontal_flicker, vertical_flicker;
} eyes_config;
enum { EYES_BLINK=1, EYES_WINK_LEFT, EYES_WINK_RIGHT, EYES_OPEN,
       EYES_CLOSE, EYES_LAUGH, EYES_CONFUSED };
eyes_config eyes_defaults(int height, int controller, int address);
bool eyes_config_valid(const eyes_config *config);
int eyes_normalize_address(int address);
typedef int (*eyes_probe)(void *context, uint8_t address);
/* 0 = neither address ACKed, -1 = both ACKed, otherwise the unique address.
 * An ACK identifies an address only, never the display controller. */
int eyes_find_address(eyes_probe probe, void *context);
void eyes_engine_begin(const eyes_config *config, uint32_t now);
void eyes_engine_configure(const eyes_config *config);
void eyes_engine_action(unsigned action);
const uint8_t *eyes_engine_frame(uint32_t now);
const uint8_t *eyes_engine_alignment(void);
/* 7-bit bus address, control byte included in every packet, <= 17 bytes. */
typedef int (*eyes_write)(void *context, uint8_t address, const uint8_t *data, size_t bytes);
int eyes_oled_init(const eyes_config *config, eyes_write write, void *context);
int eyes_oled_page(const eyes_config *config, unsigned page, const uint8_t *frame,
                   eyes_write write, void *context);
#ifdef __cplusplus
}
#endif
#endif
