// SPDX-License-Identifier: MIT
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/shell/shell.h>
#include <zephyr/drivers/display.h>
#include <errno.h>
#include <string.h>
#include "rlcd_board.h"

static int cmd_status(const struct shell *shell, size_t argc, char **argv)
{
    ARG_UNUSED(argc); ARG_UNUSED(argv);
    struct rlcd_device_status s;
    rlcd_probe(&s);
    shell_print(shell, "Zephyr Waveshare ESP32-S3-RLCD-4.2 [phase-1 driver probes]");
    shell_print(shell, "LCD=%d SHTC3=%d RTC=%d BUTTONS=%d BAT_ADC=%d I2C=%d SPI=%d SD=%d",
                s.display, s.shtc3, s.rtc, s.buttons, s.adc, s.i2c, s.spi, s.sd);
    shell_print(shell, "NOT PRESENT IN THIS BUILD: SmallVM, Arduino API, SD filesystem, Wi-Fi, BLE, audio codecs");
    return 0;
}

static int cmd_sensor(const struct shell *shell, size_t argc, char **argv)
{
    ARG_UNUSED(argc); ARG_UNUSED(argv);
    struct rlcd_environment env;
    int err = rlcd_environment_read(&env);
    if (err) { shell_error(shell, "SHTC3 read failed: %d", err); return err; }
    shell_print(shell, "temperature = %d.%03d C, relative humidity = %d.%03d %%",
                env.temp_milli_c / 1000, (int)(env.temp_milli_c < 0 ? -(env.temp_milli_c % 1000) : (env.temp_milli_c % 1000)),
                env.humidity_milli_pct / 1000, (int)(env.humidity_milli_pct % 1000));
    return 0;
}

static int cmd_rtc(const struct shell *shell, size_t argc, char **argv)
{
    ARG_UNUSED(argc); ARG_UNUSED(argv);
    char ts[32];
    int err = rlcd_rtc_read(ts, sizeof(ts));
    if (err) { shell_error(shell, "RTC read failed: %d", err); return err; }
    shell_print(shell, "PCF85063A = %s (uninitialized clocks may give invalid time)", ts);
    return 0;
}

static int cmd_battery(const struct shell *shell, size_t argc, char **argv)
{
    ARG_UNUSED(argc); ARG_UNUSED(argv);
    int32_t raw, voltage;
    int err = rlcd_battery_read(&raw, &voltage);
    if (err) { shell_error(shell, "battery ADC read failed: %d", err); return err; }
    shell_print(shell, "battery ADC raw=%ld", (long)raw);
    if (voltage >= 0) {
        shell_print(shell, "voltage divider x3: approximately %ld mV (not calibrated)", (long)voltage);
    } else {
        shell_print(shell, "millivolts unavailable without a supported ADC calibration/reference");
    }
    return 0;
}

static int cmd_buttons(const struct shell *shell, size_t argc, char **argv)
{
    ARG_UNUSED(argc); ARG_UNUSED(argv);
    shell_print(shell, "BOOT(GPIO0)=%d KEY(GPIO18)=%d", rlcd_button_pressed(0), rlcd_button_pressed(1));
    return 0;
}

static int cmd_display(const struct shell *shell, size_t argc, char **argv)
{
    ARG_UNUSED(argc);
    int err;
    if (argc == 1 || !strcmp(argv[1], "checker")) {
        err = rlcd_display_checkerboard();
    } else if (!strcmp(argv[1], "white")) {
        err = rlcd_display_clear(true);
    } else if (!strcmp(argv[1], "black")) {
        err = rlcd_display_clear(false);
    } else {
        shell_error(shell, "usage: hw display [checker|white|black]"); return -EINVAL;
    }
    if (err) { shell_error(shell, "display error: %d", err); return err; }
    shell_print(shell, "display frame sent. Inspect screen orientation and 300x400 visible crop.");
    return 0;
}

SHELL_STATIC_SUBCMD_SET_CREATE(hw_subcommands,
    SHELL_CMD(status, NULL, "Show ready devices and scope", cmd_status),
    SHELL_CMD(sensor, NULL, "Read SHTC3 temperature and humidity", cmd_sensor),
    SHELL_CMD(rtc, NULL, "Read PCF85063A RTC", cmd_rtc),
    SHELL_CMD(battery, NULL, "Read battery ADC", cmd_battery),
    SHELL_CMD(buttons, NULL, "Read BOOT and KEY", cmd_buttons),
    SHELL_CMD(display, NULL, "Display test: [checker|white|black]", cmd_display),
    SHELL_SUBCMD_SET_END);
SHELL_CMD_REGISTER(hw, &hw_subcommands, "Waveshare board diagnostics", NULL);

int main(void)
{
    printk("\nWaveshare ESP32-S3-RLCD-4.2 Zephyr hardware bring-up\n");
    printk("Use serial Zephyr shell: hw status; hw sensor; hw rtc; hw battery; hw buttons; hw display checker\n");
    struct rlcd_device_status s;
    rlcd_probe(&s);
    printk("Display ready=%d, sensor=%d, RTC=%d, battery ADC=%d\n",
           s.display, s.shtc3, s.rtc, s.adc);
    // Do not overwrite the user's current display on boot; run hw display explicitly.
    for (;;) {
        k_sleep(K_SECONDS(10));
    }
    return 0;
}
