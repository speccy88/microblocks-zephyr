/* SPDX-License-Identifier: MIT */
#include <zephyr/drivers/gpio.h>
#include "xrp.h"
#define MOTOR(n) GPIO_DT_SPEC_GET_BY_IDX(DT_PATH(zephyr_user),motor_input_gpios,n)
static const struct gpio_dt_spec motors[]={MOTOR(0),MOTOR(1),MOTOR(2),MOTOR(3),MOTOR(4),MOTOR(5),MOTOR(6),MOTOR(7)};
void xrp_motors_coast(void)
{
    for(unsigned i=0;i<ARRAY_SIZE(motors);++i)
        if(device_is_ready(motors[i].port))gpio_pin_configure_dt(&motors[i],GPIO_OUTPUT_INACTIVE);
}
