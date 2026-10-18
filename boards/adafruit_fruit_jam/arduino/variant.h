/* SPDX-License-Identifier: MIT */
#pragma once
#define ARDUINO_ADAFRUIT_FRUIT_JAM_ZEPHYR 1
/* D0..D8 are GPIO6,7,10,40,41,42,43,44,45. A0..A5 alias D3..D8.
 * No LED_BUILTIN: GPIO29 shares the IR receiver. No SPI pin constants: both
 * hardware buses are onboard. No UART pins: GPIO8/9 belong to AirLift.
 * These *_GPIO values describe physical pins, not Arduino D numbers. */
#define FRUIT_JAM_WIRE_SDA_GPIO 20
#define FRUIT_JAM_WIRE_SCL_GPIO 21
#define FRUIT_JAM_EXTENSION_COUNT 9
