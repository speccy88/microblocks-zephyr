/* SPDX-License-Identifier: MIT */
#pragma once
#define ARDUINO_SPARKFUN_XRP_ZEPHYR 1
/* Raw GPIO0..47. A0..A6 alias GPIO40..46. Reserved and actuator pins rejected. */
#ifdef __cplusplus
extern "C" {
#endif
int sparkfun_xrp_pin_allowed(unsigned gpio);
int sparkfun_xrp_output_allowed(unsigned gpio);
void sparkfun_xrp_adc_mux(unsigned gpio);
void sparkfun_xrp_pwm_mux(unsigned gpio);
#ifdef __cplusplus
}
#endif
