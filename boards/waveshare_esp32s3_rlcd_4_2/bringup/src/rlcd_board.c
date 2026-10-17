// SPDX-License-Identifier: MIT
#include "rlcd_board.h"

#include <errno.h>
#include <string.h>
#include <stdio.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/drivers/rtc.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/display.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/input/input.h>
#include <zephyr/dt-bindings/input/input-event-codes.h>
#include <zephyr/sys/util.h>
#include <zephyr/sys/atomic.h>
#if defined(CONFIG_CHARACTER_FRAMEBUFFER)
#include <zephyr/display/cfb.h>
#endif

// Exact labels and aliases verified against Zephyr's official board DTS.
#define RLCD_DISPLAY_NODE DT_CHOSEN(zephyr_display)
#define RLCD_SHTC3_NODE   DT_NODELABEL(shtc3)
#define RLCD_RTC_NODE     DT_NODELABEL(rtc0)
#define RLCD_I2C_NODE     DT_NODELABEL(i2c0)
#define RLCD_SPI_NODE     DT_NODELABEL(spi2)
#define RLCD_BATT_NODE    DT_NODELABEL(vbatt)

#if !DT_NODE_EXISTS(RLCD_DISPLAY_NODE) || !DT_NODE_EXISTS(RLCD_SHTC3_NODE) || \
    !DT_NODE_EXISTS(RLCD_RTC_NODE) || !DT_NODE_EXISTS(RLCD_BATT_NODE)
#error "Expected esp32s3_rlcd_4_2/esp32s3/procpu Devicetree nodes are absent"
#endif

static const struct device *const display_dev = DEVICE_DT_GET(RLCD_DISPLAY_NODE);
static const struct device *const temp_dev = DEVICE_DT_GET(RLCD_SHTC3_NODE);
static const struct device *const rtc_dev = DEVICE_DT_GET(RLCD_RTC_NODE);
static const struct device *const i2c_dev = DEVICE_DT_GET(RLCD_I2C_NODE);
static const struct device *const spi_dev = DEVICE_DT_GET(RLCD_SPI_NODE);
static const struct device *const buttons_dev = DEVICE_DT_GET(DT_PATH(buttons));
static const struct adc_dt_spec batt_adc = ADC_DT_SPEC_GET_BY_IDX(RLCD_BATT_NODE, 0);

#define DISP_W DT_PROP(RLCD_DISPLAY_NODE, width)
#define DISP_H DT_PROP(RLCD_DISPLAY_NODE, height)
BUILD_ASSERT(DISP_W % 8 == 0, "ST730x monochrome framebuffer needs byte-aligned width");
BUILD_ASSERT(DISP_W % 12 == 0, "ST730x writes need 12-pixel column alignment");
BUILD_ASSERT(DISP_H % 2 == 0, "ST730x writes need paired rows");
BUILD_ASSERT((DISP_W * DISP_H) % 8 == 0, "monochrome buffer size must be integral");
static uint8_t display_frame[DISP_W * DISP_H / 8];
static K_MUTEX_DEFINE(display_mutex);
static atomic_t btn0;
static atomic_t btn1;
static bool adc_configured;

static void button_callback(struct input_event *event, void *user_data)
{
    ARG_UNUSED(user_data);
    if (event->type != INPUT_EV_KEY) {
        return;
    }
    if (event->code == INPUT_KEY_0) {
        atomic_set(&btn0, event->value != 0);
    } else if (event->code == INPUT_KEY_1) {
        atomic_set(&btn1, event->value != 0);
    }
}
INPUT_CALLBACK_DEFINE(NULL, button_callback, NULL);

bool rlcd_button_pressed(unsigned index)
{
    return index == 0 ? atomic_get(&btn0) != 0 :
           index == 1 ? atomic_get(&btn1) != 0 : false;
}

void rlcd_probe(struct rlcd_device_status *out)
{
    if (!out) { return; }
    memset(out, 0, sizeof(*out));
    out->display = device_is_ready(display_dev);
    out->shtc3 = device_is_ready(temp_dev);
    out->rtc = device_is_ready(rtc_dev);
    out->buttons = device_is_ready(buttons_dev); // Event delivery still needs a physical test.
    out->adc = adc_is_ready_dt(&batt_adc);
    out->i2c = device_is_ready(i2c_dev);
    out->spi = device_is_ready(spi_dev);
    // SDMMC not built into phase-1 application; the DTS node exists upstream.
    out->sd = false;
}

int rlcd_environment_read(struct rlcd_environment *out)
{
    if (!out) { return -EINVAL; }
    if (!device_is_ready(temp_dev)) { return -ENODEV; }
    int err = sensor_sample_fetch(temp_dev);
    if (err) { return err; }
    struct sensor_value temp, humidity;
    err = sensor_channel_get(temp_dev, SENSOR_CHAN_AMBIENT_TEMP, &temp);
    if (err) { return err; }
    err = sensor_channel_get(temp_dev, SENSOR_CHAN_HUMIDITY, &humidity);
    if (err) { return err; }
    // Zephyr sensor_value uses val1 + val2 / 1,000,000.
    out->temp_milli_c = temp.val1 * 1000 + temp.val2 / 1000;
    out->humidity_milli_pct = humidity.val1 * 1000 + humidity.val2 / 1000;
    return 0;
}

int rlcd_rtc_read(char *dst, unsigned dst_size)
{
    if (!dst || dst_size < 21) { return -EINVAL; }
    if (!device_is_ready(rtc_dev)) { return -ENODEV; }
    struct rtc_time t;
    int err = rtc_get_time(rtc_dev, &t);
    if (err) { return err; }
    // RTC may not have been initialized yet; time shouldn't be treated as valid automatically.
    int n = snprintf(dst, dst_size, "%04d-%02d-%02d %02d:%02d:%02d",
        t.tm_year + 1900, t.tm_mon + 1, t.tm_mday,
        t.tm_hour, t.tm_min, t.tm_sec);
    return (n >= 0 && (unsigned)n < dst_size) ? 0 : -ENOSPC;
}

int rlcd_battery_read(int32_t *raw, int32_t *mv_estimate)
{
    if (!raw) { return -EINVAL; }
    if (!adc_is_ready_dt(&batt_adc)) { return -ENODEV; }
    if (!adc_configured) {
        int err = adc_channel_setup_dt(&batt_adc);
        if (err) { return err; }
        adc_configured = true;
    }
    int16_t sample = 0;
    struct adc_sequence sequence = { .buffer = &sample, .buffer_size = sizeof(sample) };
    int err = adc_sequence_init_dt(&batt_adc, &sequence);
    if (err) { return err; }
    err = adc_read_dt(&batt_adc, &sequence);
    if (err) { return err; }
    *raw = sample;
    if (mv_estimate) {
        int32_t mv = sample;
        // On ESP32 calibration isn't guaranteed; -ENOTSUP means report raw only.
        err = adc_raw_to_millivolts_dt(&batt_adc, &mv);
        *mv_estimate = (err == 0) ?
            (int32_t)((int64_t)mv * DT_PROP(RLCD_BATT_NODE, full_ohms) /
                      DT_PROP(RLCD_BATT_NODE, output_ohms)) : -1;
    }
    return 0;
}

static int push_display(void)
{
    if (!device_is_ready(display_dev)) { return -ENODEV; }
    struct display_capabilities caps;
    display_get_capabilities(display_dev, &caps);
    if (caps.current_pixel_format != PIXEL_FORMAT_MONO01 ||
        caps.x_resolution != DISP_W || caps.y_resolution != DISP_H ||
        caps.screen_info != 0) {
        return -ENOTSUP;
    }
    const struct display_buffer_descriptor desc = {
        .buf_size = sizeof(display_frame),
        .width = DISP_W,
        .height = DISP_H,
        .pitch = DISP_W,
    };
    int err = display_blanking_off(display_dev);
    if (err && err != -ENOSYS) { return err; }
    return display_write(display_dev, 0, 0, &desc, display_frame);
}

int rlcd_display_clear(bool white)
{
    k_mutex_lock(&display_mutex, K_FOREVER);
    memset(display_frame, white ? 0xFF : 0x00, sizeof(display_frame));
    int err = push_display();
    k_mutex_unlock(&display_mutex);
    return err;
}

int rlcd_display_checkerboard(void)
{
    k_mutex_lock(&display_mutex, K_FOREVER);
    memset(display_frame, 0, sizeof(display_frame));
    // 24px squares, 1bpp, logical bitmap; display orientation requires physical check.
    for (unsigned y = 0; y < DISP_H; ++y) {
        for (unsigned x = 0; x < DISP_W; ++x) {
            bool white = ((x / 24u) + (y / 24u)) % 2u == 0;
            if (white) {
                unsigned i = y * DISP_W + x;
                display_frame[i >> 3] |= 0x80u >> (i & 7u);
            }
        }
    }
    int err = push_display();
    k_mutex_unlock(&display_mutex);
    return err;
}

int rlcd_display_text(const char *text)
{
#if defined(CONFIG_CHARACTER_FRAMEBUFFER)
    static bool initialized;
    int err = 0;
    k_mutex_lock(&display_mutex, K_FOREVER);
    if (!initialized) {
        err = cfb_framebuffer_init(display_dev);
        if (err) goto done;
        initialized = true;
    }
    uint8_t width = 0, height = 0;
    for (int font = 0; font < 16; ++font) {
        if (cfb_get_font_size(display_dev, font, &width, &height)) break;
        cfb_framebuffer_set_font(display_dev, font);
        if (width <= 12 && height >= 16) break;
    }
    cfb_framebuffer_clear(display_dev, false);
    unsigned y = 12;
    while (*text && y + height < DISP_H) {
        char line[48];
        size_t n = 0;
        while (*text && *text != '\n' && n < MIN(sizeof(line) - 1, 276u / MAX(width, 1u))) {
            line[n++] = *text++;
        }
        line[n] = 0;
        err = cfb_print(display_dev, line, 18, y);
        if (err) goto done;
        if (*text == '\n') ++text;
        y += height + 4;
    }
    err = display_blanking_off(display_dev);
    if (!err) err = cfb_framebuffer_finalize(display_dev);
done:
    k_mutex_unlock(&display_mutex);
    return err;
#else
    ARG_UNUSED(text);
    return -ENOTSUP;
#endif
}
