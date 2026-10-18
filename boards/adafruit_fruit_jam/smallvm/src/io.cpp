/* SPDX-License-Identifier: MIT */
#include "generic_io.h"
#include "fruit_jam.h"
#include "vm/interp.h"
#include <Arduino.h>
#include <Wire.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/pwm.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#ifndef ARDUINO_ADAFRUIT_FRUIT_JAM_ZEPHYR
#error "The isolated Fruit Jam Arduino variant is required"
#endif
static_assert(NUM_OF_DIGITAL_PINS == 9, "Extension mapping changed");
static const device *const bus = DEVICE_DT_GET(DT_NODELABEL(i2c0));
static const device *const gpio = DEVICE_DT_GET(DT_NODELABEL(gpio0));
static const device *const pwm = DEVICE_DT_GET(DT_NODELABEL(pwm));
static const unsigned physical_pins[] = {6,7,10,40,41,42,43,44,45};
static const unsigned pwm_channels[] = {6,7,10,16,17,18,19,20,21};
static const unsigned button_pins[] = {0,4,5};
static bool pwm_active[9];
static int last_error;
static uint8_t pending_data[32];
static size_t pending_count;
static unsigned pending_address;

extern "C" void fj_io_init(void)
{
    for (unsigned pin = 0; pin < 9; ++pin) pinMode(pin, INPUT);
    /* Input-only buttons; BOOT/ESP_BOOT is never driven. */
    if (device_is_ready(gpio))
        for (unsigned pin : button_pins) gpio_pin_configure(gpio, pin, GPIO_INPUT | GPIO_PULL_UP);
}

extern "C" int fj_button(unsigned button)
{
    if (button >= 3 || !device_is_ready(gpio)) return -EINVAL;
    int value = gpio_pin_get(gpio, button_pins[button]);
    return value < 0 ? value : !value;
}

extern "C" void hardwareInit(void) { initTasks(); fj_io_init(); Wire.begin(); }
extern "C" uint32 microsecs(void) { return micros(); }
extern "C" uint32 millisecs(void) { return millis(); }
extern "C" uint64 totalMicrosecs(void) { return k_ticks_to_us_floor64(k_uptime_ticks()); }
extern "C" uint32 seconds(void) { return millis() / 1000; }
extern "C" void handleMicosecondClockWrap(void) {}
extern "C" void smallvmDelay(unsigned long ms) { delay(ms); }
extern "C" void lightSleep(int ms) { if (ms > 0) delay(ms); }
extern "C" void deepSleep(int sec) { (void)sec; fail(primitiveNotImplemented); }
extern "C" int pinCount(void) { return 9; }
extern "C" OBJ primDigitalPins(OBJ *) { return int2obj(9); }
extern "C" OBJ primAnalogPins(OBJ *) { return int2obj(6); }

extern "C" void fj_io_prepare_gpio(unsigned pin)
{
    if (pin >= 9) return;
    if (pwm_active[pin]) {
        pwm_set(pwm, pwm_channels[pin], 1000000, 0, 0);
        pwm_active[pin] = false;
    }
}

extern "C" OBJ primDigitalRead(int argc, OBJ *args)
{
    if (argc < 1) return fail(notEnoughArguments);
    if (!isInt(args[0])) return fail(needsIntegerError);
    int pin = obj2int(args[0]);
    if (pin < 0 || pin >= 9) return fail(badPinError);
    fj_io_prepare_gpio(pin);
    PinMode mode = INPUT;
    if (argc > 1) {
        if (args[1] == trueObj) mode = INPUT_PULLUP;
        else if (IS_TYPE(args[1], StringType)) {
            if (!strcmp(obj2str(args[1]), "up")) mode = INPUT_PULLUP;
            else if (!strcmp(obj2str(args[1]), "down")) mode = INPUT_PULLDOWN;
        }
    }
    pinMode(pin, mode);
    int value = gpio_pin_get(digitalPinToPortDevice(pin), digitalPinToPinIndex(pin));
    return value < 0 ? fail(primitiveNotImplemented) : value ? trueObj : falseObj;
}

extern "C" void primDigitalSet(int pin, int state)
{
    if (pin < 0 || pin >= 9) { fail(badPinError); return; }
    fj_io_prepare_gpio(pin);
    pinMode(pin, OUTPUT);
    if (gpio_pin_set(digitalPinToPortDevice(pin), digitalPinToPinIndex(pin), !!state))
        fail(primitiveNotImplemented);
}

extern "C" void primDigitalWrite(OBJ *args)
{
    if (!isInt(args[0])) { fail(needsIntegerError); return; }
    primDigitalSet(obj2int(args[0]), args[1] != falseObj);
}

extern "C" void fj_io_pwm_stop(void)
{
    if (!device_is_ready(pwm)) return;
    for (unsigned pin = 0; pin < 9; ++pin) {
        pwm_set(pwm, pwm_channels[pin], 1000000, 0, 0);
        pwm_active[pin] = false;
        pinMode(pin, INPUT);
    }
}

extern "C" void turnOffPins(void)
{
    fj_io_i2c_cancel();
    fj_io_pwm_stop();
    for (unsigned pin = 0; pin < 9; ++pin) pinMode(pin, INPUT);
}

extern "C" int fj_io_analog_read(unsigned pin, unsigned mode, int *value)
{
    if (pin >= 6 || !value) return -EINVAL;
    /* RP2350 adc_gpio_init disables pulls; do not silently claim pull support. */
    if (mode) return -ENOTSUP;
    fj_io_prepare_gpio(pin + 3);
    pinMode(pin + 3, INPUT);
    analogReadResolution(10);
    int sample = analogRead(pin + 3);
    if (sample < 0) return last_error = sample;
    if (sample > 1023) return last_error = -ERANGE;
    *value = sample;
    return last_error = 0;
}

extern "C" int fj_io_pwm_write(unsigned pin, unsigned value)
{
    if (pin >= 9 || value > 1023) return -EINVAL;
    if (!device_is_ready(pwm)) return last_error = -ENODEV;
    pinMode(pin, INPUT);
    int err = pwm_set(pwm, pwm_channels[pin], 1000000, (uint64_t)value * 1000000 / 1023, 0);
    if (!err) { fruit_jam_pwm_mux(physical_pins[pin]); pwm_active[pin] = true; }
    return last_error = err;
}

extern "C" void fj_io_i2c_cancel(void) { pending_count = 0; }
extern "C" int fj_io_i2c_get(unsigned address, unsigned reg, uint8_t *value)
{
    fj_io_i2c_cancel();
    if (address > 127 || reg > 255 || !value) return -EINVAL;
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    return last_error = i2c_reg_read_byte(bus, address, reg, value);
}
extern "C" int fj_io_i2c_set(unsigned address, unsigned reg, uint8_t value)
{
    fj_io_i2c_cancel();
    if (address > 127 || reg > 255) return -EINVAL;
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    return last_error = i2c_reg_write_byte(bus, address, reg, value);
}
extern "C" int fj_io_i2c_read(unsigned address, uint8_t *data, size_t count)
{
    if (address > 127 || count > 32 || (!data && count)) return -EINVAL;
    if (!count) return 0;
    size_t pending = pending_count;
    fj_io_i2c_cancel();
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    if (pending) {
        if (address != pending_address) return last_error = -EINVAL;
        return last_error = i2c_write_read(bus, address, pending_data, pending, data, count);
    }
    return last_error = i2c_read(bus, data, count, address);
}
extern "C" int fj_io_i2c_write(unsigned address, const uint8_t *data, size_t count, bool stop)
{
    if (address > 127 || count > 32 || (!data && count)) return -EINVAL;
    if (!count) return 0;
    if (pending_count) { fj_io_i2c_cancel(); return last_error = -EBUSY; }
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    if (!stop) {
        memcpy(pending_data, data, count); pending_count = count; pending_address = address;
        return last_error = 0;
    }
    return last_error = i2c_write(bus, data, count, address);
}
extern "C" int fj_io_i2c_exists(unsigned address)
{
    fj_io_i2c_cancel();
    if (address > 127) return -EINVAL;
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    uint8_t unused = 0;
    return last_error = i2c_write(bus, &unused, 0, address);
}
/* Both onboard SPI buses stay reserved. Never drive SD/AirLift via raw blocks. */
extern "C" int fj_io_spi_setup(unsigned hz, unsigned mode, bool lsb)
{ (void)hz; (void)mode; (void)lsb; return -ENOTSUP; }
extern "C" int fj_io_spi_transfer(const uint8_t *tx, uint8_t *rx, size_t count)
{ (void)tx; (void)rx; (void)count; return -ENOTSUP; }
extern "C" int fj_io_info(char *dst, unsigned size)
{
    snprintf(dst, size, "{\"digital_gpio\":[6,7,10,40,41,42,43,44,45],\"analog_gpio\":[40,41,42,43,44,45],\"analog_max\":1023,\"pwm_hz\":1000,\"i2c_gpio\":[20,21],\"spi\":false,\"hardware_tested\":false,\"error\":%d}", last_error);
    return 0;
}
