/* SPDX-License-Identifier: MIT
 * Production XRP only. Quiet, non-actuating source-stage diagnostic.
 * No motor PWM, servo pulses, LEDs, ultrasonic trigger, radio or flash writes. */
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/kernel.h>
#include <errno.h>

#define USER DT_PATH(zephyr_user)
#define MOTOR(index) GPIO_DT_SPEC_GET_BY_IDX(USER, motor_input_gpios, index)
static const struct gpio_dt_spec motor_inputs[] = {
    MOTOR(0), MOTOR(1), MOTOR(2), MOTOR(3), MOTOR(4), MOTOR(5), MOTOR(6), MOTOR(7)
};
static const struct gpio_dt_spec button = GPIO_DT_SPEC_GET(USER, user_button_gpios);
static const struct device *const imu_bus = DEVICE_DT_GET(DT_NODELABEL(i2c1));
/* Debugger-visible evidence only; not a claim that the physical checks passed. */
volatile struct {
    uint32_t signature, motor_coast_failures, cycles;
    int button_error, button_pressed, imu_error;
    uint8_t imu_family_id;
    bool actuator_commands_enabled;
} xrp_baseline_status = {.signature = 0x58525032, .actuator_commands_enabled = false};

int main(void)
{
    for (unsigned i = 0; i < ARRAY_SIZE(motor_inputs); ++i) {
        int error = !gpio_is_ready_dt(&motor_inputs[i]) ? -ENODEV :
            gpio_pin_configure_dt(&motor_inputs[i], GPIO_OUTPUT_INACTIVE);
        if (error) xrp_baseline_status.motor_coast_failures |= 1u << i;
    }
    xrp_baseline_status.button_error = !gpio_is_ready_dt(&button) ? -ENODEV :
        gpio_pin_configure_dt(&button, GPIO_INPUT | GPIO_PULL_UP);
    uint8_t identity = 0;
    xrp_baseline_status.imu_error = !device_is_ready(imu_bus) ? -ENODEV :
        i2c_reg_read_byte(imu_bus, 0x6b, 0x0f, &identity);
    if (!xrp_baseline_status.imu_error) xrp_baseline_status.imu_family_id = identity;
    for (;;) {
        if (!xrp_baseline_status.button_error)
            xrp_baseline_status.button_pressed = gpio_pin_get_dt(&button);
        ++xrp_baseline_status.cycles;
        k_msleep(1000);
    }
    return 0;
}
