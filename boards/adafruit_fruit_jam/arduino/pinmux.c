/* SPDX-License-Identifier: MIT */
/* Pico SDK headers use <cassert> in C++; keep the SDK boundary in C so this
 * module works with Zephyr's minimal C++ library. No device-wide reset. */
#include <hardware/gpio.h>
#include <hardware/adc.h>

void fruit_jam_adc_mux(unsigned gpio)
{
    if (gpio >= 40 && gpio <= 45) adc_gpio_init(gpio);
}

void fruit_jam_pwm_mux(unsigned gpio)
{
    if (gpio == 6 || gpio == 7 || gpio == 10 || (gpio >= 40 && gpio <= 45))
        gpio_set_function(gpio, GPIO_FUNC_PWM);
}
