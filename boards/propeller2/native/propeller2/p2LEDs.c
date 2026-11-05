/* SPDX-License-Identifier: MPL-2.0 */
/* Bounded WS2812 RGB output. No allocation, background cog or flash access. */
#include <stdint.h>
#include <string.h>
#include <propeller2.h>
#include "mem.h"
#include "interp.h"
#include "p2Board.h"

#define LED_LIMIT 128
static uint32_t pixels[LED_LIMIT];
static int ledPin = -1, ledCount, brightness = 255;
extern void invalidatePinModeTracking(int pin);

/* Cached PASM keeps pulse widths independent of HUB instruction fetches.
   RGB is sent GRB, MSB first. About 4.2 ms maximum including the latch. */
static void sendPixel(int pin, uint32_t rgb) {
    uint32_t payload = (((rgb >> 8) & 255) << 24) | ((rgb >> 16) << 16) | ((rgb & 255) << 8);
#ifdef P2_PERIPHERAL_HOST_TEST
    extern void testLEDWord(int pin, uint32_t grb);
    testLEDWord(pin, payload);
#else
    uint32_t zero = _clockfreq() / 2500000, one = _clockfreq() / 1250000;
    uint32_t period = _clockfreq() / 800000, high, edge;
    int bits = 24;
    __asm volatile {
p2_led_bit
        shl payload, #1 wc
        mov high, zero
 if_c   mov high, one
        drvh pin
        getct edge
        addct1 edge, high
        waitct1
        drvl pin
        sub high, period
        neg high, high
        addct1 edge, high
        waitct1
        djnz bits, #p2_led_bit
    }
#endif
}

static int pinOK(int pin) { return pin >= 0 && pin <= P2_LAST_USER_PIN; }
static uint32_t scaled(uint32_t rgb) {
    uint32_t r = ((rgb >> 16) & 255) * brightness / 255;
    uint32_t g = ((rgb >> 8) & 255) * brightness / 255;
    uint32_t b = (rgb & 255) * brightness / 255;
    return (r << 16) | (g << 8) | b;
}
void p2LEDReset(void) { ledPin = -1; ledCount = 0; }

OBJ p2LEDInit(int argc, OBJ *args) {
    if (argc != 2 || !isInt(args[0]) || !isInt(args[1])) return fail(needsIntegerError);
    int pin = obj2int(args[0]), count = obj2int(args[1]);
    if (!pinOK(pin)) return fail(badPinError);
    if (count < 1 || count > LED_LIMIT) return fail(indexOutOfRangeError);
    /* Configuration is inert until update, permitting wiring before output. */
    ledPin = pin; ledCount = count; brightness = 255;
    memset(pixels, 0, sizeof(pixels));
    return trueObj;
}
OBJ p2LEDSet(int argc, OBJ *args) {
    if (argc != 2 || !isInt(args[0]) || !isInt(args[1])) return fail(needsIntegerError);
    int index = obj2int(args[0]), rgb = obj2int(args[1]);
    if (index < 1 || index > ledCount || rgb < 0 || rgb > 0xffffff) return fail(indexOutOfRangeError);
    pixels[index - 1] = rgb; return trueObj;
}
OBJ p2LEDFill(int argc, OBJ *args) {
    if (argc != 1 || !isInt(args[0])) return fail(needsIntegerError);
    int rgb = obj2int(args[0]);
    if (!ledCount || rgb < 0 || rgb > 0xffffff) return fail(indexOutOfRangeError);
    for (int i = 0; i < ledCount; i++) pixels[i] = rgb;
    return trueObj;
}
OBJ p2LEDBrightness(int argc, OBJ *args) {
    if (argc != 1 || !isInt(args[0])) return fail(needsIntegerError);
    int value = obj2int(args[0]);
    if (value < 0 || value > 255) return fail(byteOutOfRange);
    brightness = value; return trueObj;
}
OBJ p2LEDUpdate(int argc, OBJ *args) {
    (void)argc; (void)args;
    if (!pinOK(ledPin) || !ledCount) return fail(badPinError);
    invalidatePinModeTracking(ledPin); _pinclear(ledPin); _pinl(ledPin);
    _waitus(300);
    for (int i = 0; i < ledCount; i++) sendPixel(ledPin, scaled(pixels[i]));
    _pinl(ledPin); _waitus(300);
    return trueObj;
}

/* Standard shared NeoPixel library: RGB only; reject RGBW explicitly. */
OBJ p2NeoPixelSetPin(int argc, OBJ *args) {
    if (argc < 1 || !isInt(args[0])) return fail(needsIntegerError);
    int pin = obj2int(args[0]);
    if (!pinOK(pin)) return fail(badPinError);
    if (argc > 1 && args[1] == trueObj) return fail(primitiveNotImplemented);
    ledPin = pin; return falseObj;
}
OBJ p2NeoPixelSend(int argc, OBJ *args) {
    if (argc != 1 || !IS_TYPE(args[0], ListType)) return fail(needsListError);
    int count = obj2int(FIELD(args[0], 0));
    if (count < 1 || count > LED_LIMIT) return fail(indexOutOfRangeError);
    for (int i = 1; i <= count; i++) {
        OBJ value = FIELD(args[0], i);
        if (!isInt(value) || obj2int(value) < 0 || obj2int(value) > 0xffffff) return fail(badColorPalette);
    }
    for (int i = 0; i < count; i++) pixels[i] = obj2int(FIELD(args[0], i + 1));
    ledCount = count; brightness = 255;
    return p2LEDUpdate(0, NULL);
}
