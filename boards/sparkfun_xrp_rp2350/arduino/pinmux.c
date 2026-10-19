/* SPDX-License-Identifier: MIT */
#include <hardware/gpio.h>
#include <hardware/adc.h>
#include "pin_policy.h"
int sparkfun_xrp_pin_allowed(unsigned p)
{ return xrp_pin_readable(p); }
int sparkfun_xrp_output_allowed(unsigned p) { return xrp_pin_writable(p); }
void sparkfun_xrp_adc_mux(unsigned p)
{ if (p >= 40 && p <= 46) adc_gpio_init(p); }
void sparkfun_xrp_pwm_mux(unsigned p)
{ if (p >= 12 && p <= 19) gpio_set_function(p, GPIO_FUNC_PWM); }
