/* SPDX-License-Identifier: MIT
 * Factory AirLift identification only. No network settings, firmware upload,
 * scanning, UART access or boot-time reset. Framing follows the pinned MIT
 * Adafruit ESP32SPI reference; see nina_protocol.c and LICENSES.md. */
#include "airlift.h"
#include "fruit_jam.h"
#include "nina_protocol.h"
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#define AIRLIFT DT_PATH(zephyr_user)
static const struct device *const bus = DEVICE_DT_GET(DT_NODELABEL(spi1));
static const struct gpio_dt_spec cs = GPIO_DT_SPEC_GET(AIRLIFT, airlift_cs_gpios);
static const struct gpio_dt_spec busy = GPIO_DT_SPEC_GET(AIRLIFT, airlift_busy_gpios);
static const struct gpio_dt_spec reset = GPIO_DT_SPEC_GET(AIRLIFT, airlift_reset_gpios);
/* CS is manual: NINA acknowledges CS with BUSY before SPI clocks may begin. */
static const struct spi_config config = {
    .frequency = 1000000,
    .operation = SPI_OP_MODE_MASTER | SPI_WORD_SET(8) | SPI_TRANSFER_MSB,
    .slave = 0,
};
K_MUTEX_DEFINE(state_lock);
K_SEM_DEFINE(request_sem, 0, 1);
static struct {
    unsigned state, generation, queries;
    int error, stage, busy_level, connection;
    bool reset_requested;
    char version[32], mac[18];
} report;

static int wait_busy(int level)
{
    int64_t deadline = k_uptime_get() + 1000;
    do {
        int actual = gpio_pin_get_dt(&busy);
        if (actual < 0) return actual;
        if (actual == level) return 0;
        k_sleep(K_MSEC(1));
    } while (k_uptime_get() < deadline);
    return -ETIMEDOUT;
}

static int select_device(void)
{
    int err = wait_busy(0);
    if (err) return err;
    if ((err = gpio_pin_set_dt(&cs, 1))) return err;
    err = wait_busy(1);
    if (err) gpio_pin_set_dt(&cs, 0);
    return err;
}

static int read_byte(void *unused, uint8_t *value)
{
    (void)unused;
    /* SPI read emits zero dummy bytes, like CircuitPython SPI.readinto(). */
    uint8_t dummy = 0;
    const struct spi_buf tx = {.buf = &dummy, .len = 1};
    struct spi_buf rx = {.buf = value, .len = 1};
    const struct spi_buf_set txs = {.buffers = &tx, .count = 1};
    const struct spi_buf_set rxs = {.buffers = &rx, .count = 1};
    return spi_transceive(bus, &config, &txs, &rxs);
}
static void retry_pause(void *unused) { (void)unused; k_sleep(K_MSEC(10)); }

static int query(uint8_t command, uint8_t *dst, size_t capacity, size_t *length)
{
    uint8_t frame[8];
    int count = fj_nina_query_frame(command, frame, sizeof(frame));
    if (count < 0) return count;
    int err = select_device();
    if (err) return err;
    const struct spi_buf buffer = {.buf = frame, .len = count};
    const struct spi_buf_set buffers = {.buffers = &buffer, .count = 1};
    err = spi_write(bus, &config, &buffers);
    int release_err = gpio_pin_set_dt(&cs, 0);
    if (err || release_err) return err ? err : release_err;
    if ((err = select_device())) return err;
    const struct fj_nina_reader io = {.byte = read_byte, .retry_pause = retry_pause};
    err = fj_nina_read_reply(&io, command, dst, capacity, length);
    release_err = gpio_pin_set_dt(&cs, 0);
    return err ? err : release_err;
}

static int prepare(bool reset_first)
{
    if (!device_is_ready(bus) || !gpio_is_ready_dt(&cs) || !gpio_is_ready_dt(&busy)) return -ENODEV;
    int err = gpio_pin_configure_dt(&cs, GPIO_OUTPUT_INACTIVE);
    if (err) return err;
    if ((err = gpio_pin_configure_dt(&busy, GPIO_INPUT))) return err;
    if (!reset_first) return 0;
    if (!gpio_is_ready_dt(&reset)) return -ENODEV;
    /* GPIO0 is also a button. Never drive it high against a pressed button. */
    int pressed = fj_button(0);
    if (pressed < 0) return pressed;
    if (pressed) return -EBUSY;
    if ((err = gpio_pin_configure_dt(&reset, GPIO_OUTPUT_INACTIVE))) return err;
    if ((err = gpio_pin_set_dt(&reset, 1))) return err;
    k_sleep(K_MSEC(10));
    err = gpio_pin_set_dt(&reset, 0);
    if (err) return err;
    k_sleep(K_MSEC(750));
    return 0;
}

static void diagnostic_worker(void *a, void *b, void *c)
{
    (void)a; (void)b; (void)c;
    for (;;) {
        k_sem_take(&request_sem, K_FOREVER);
        k_mutex_lock(&state_lock, K_FOREVER);
        bool reset_first = report.reset_requested;
        report.state = 2;
        k_mutex_unlock(&state_lock);
        uint8_t data[31]; size_t count = 0;
        char version[32] = {0}, mac[18] = {0};
        int stage = 1, connection = -1;
        unsigned queries = 0;
        int err = prepare(reset_first);
        if (!err) { stage = 2; err = query(0x37, data, sizeof(data), &count); }
        if (!err) {
            ++queries; unsigned out = 0;
            for (size_t i = 0; i < count; ++i) {
                if (!data[i]) continue;
                /* Keep JSON safe and reject arbitrary binary version text. */
                if (data[i] < 32 || data[i] > 126 || data[i] == '"' || data[i] == '\\') { err = -EPROTO; break; }
                version[out++] = data[i];
            }
            if (!out) err = -EPROTO;
        }
        if (!err) { stage = 3; err = query(0x22, data, 6, &count); }
        if (!err && count != 6) err = -EPROTO;
        if (!err) {
            ++queries;
            snprintf(mac, sizeof(mac), "%02x:%02x:%02x:%02x:%02x:%02x",
                data[5], data[4], data[3], data[2], data[1], data[0]);
            stage = 4; err = query(0x20, data, 1, &count);
        }
        if (!err && count != 1) err = -EPROTO;
        if (!err) { ++queries; connection = data[0]; }
        /* Release even after a malformed reply. No automatic reset/retry. */
        if (gpio_is_ready_dt(&cs)) gpio_pin_set_dt(&cs, 0);
        int level = gpio_is_ready_dt(&busy) ? gpio_pin_get_dt(&busy) : -1;
        k_mutex_lock(&state_lock, K_FOREVER);
        report.error = err; report.stage = stage; report.queries = queries;
        report.connection = connection; report.busy_level = level;
        memcpy(report.version, version, sizeof(version));
        memcpy(report.mac, mac, sizeof(mac));
        report.state = err ? 4 : 3;
        k_mutex_unlock(&state_lock);
    }
}
K_THREAD_DEFINE(airlift_diagnostic_thread, 2048, diagnostic_worker, NULL, NULL, NULL, 7, 0, 0);

int fj_airlift_request(bool reset_first)
{
    k_mutex_lock(&state_lock, K_FOREVER);
    if (report.state == 1 || report.state == 2) { k_mutex_unlock(&state_lock); return -EBUSY; }
    ++report.generation; report.state = 1; report.error = 0;
    report.reset_requested = reset_first;
    k_mutex_unlock(&state_lock);
    k_sem_give(&request_sem);
    return 0;
}

int fj_airlift_status(char *dst, unsigned size)
{
    k_mutex_lock(&state_lock, K_FOREVER);
    int count = snprintf(dst, size,
        "{\"state\":%u,\"generation\":%u,\"error\":%d,\"stage\":%d,\"queries\":%u,"
        "\"version\":\"%s\",\"mac\":\"%s\",\"connection\":%d,\"busy\":%d,"
        "\"reset_requested\":%s,\"spi_hz\":1000000,\"coprocessor_flashed\":false}",
        report.state, report.generation, report.error, report.stage, report.queries,
        report.version, report.mac, report.connection, report.busy_level,
        report.reset_requested ? "true" : "false");
    k_mutex_unlock(&state_lock);
    return count < 0 || (unsigned)count >= size ? -ENOSPC : 0;
}
