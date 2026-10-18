/* SPDX-License-Identifier: MIT
 * SHT4x no-heater protocol, from Sensirion's published command/CRC contract.
 * Address identifies a protocol endpoint, not the exact SHT40/41 variant.
 */
#include <zephyr/kernel.h>
#include <errno.h>
#include <stdio.h>
#include "generic_io.h"

static int last_error = -ENODATA;
static int temperature, humidity;
static int64_t attempted_at = -1000, sampled_at;
static unsigned attempts, samples;
static uint8_t frame[6];
static bool valid;

static uint8_t crc8(const uint8_t *data)
{
    uint8_t crc = 0xff;
    for (unsigned i = 0; i < 2; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = crc & 0x80 ? (uint8_t)((crc << 1) ^ 0x31) : (uint8_t)(crc << 1);
    }
    return crc;
}

int fj_sht4x_read(int *milli_c, int *milli_percent)
{
    int64_t now = k_uptime_get();
    if (now - attempted_at >= 250) {
        uint8_t command = 0xfd; /* High precision, no heater. */
        attempted_at = now;
        attempts++;
        valid = false;
        fj_io_i2c_cancel();
        last_error = fj_io_i2c_write(0x44, &command, 1, true);
        if (!last_error) {
            k_sleep(K_MSEC(10));
            last_error = fj_io_i2c_read(0x44, frame, sizeof(frame));
        }
        if (!last_error && (crc8(frame) != frame[2] || crc8(frame + 3) != frame[5]))
            last_error = -EBADMSG;
        if (!last_error) {
            unsigned raw_t = ((unsigned)frame[0] << 8) | frame[1];
            unsigned raw_h = ((unsigned)frame[3] << 8) | frame[4];
            temperature = (int)((175000ULL * raw_t + 32767) / 65535) - 45000;
            humidity = (int)((125000ULL * raw_h + 32767) / 65535) - 6000;
            if (humidity < 0) humidity = 0;
            if (humidity > 100000) humidity = 100000;
            sampled_at = k_uptime_get();
            samples++;
            valid = true;
        }
    }
    if (last_error) return last_error;
    *milli_c = temperature;
    *milli_percent = humidity;
    return 0;
}

int fj_sht4x_status(char *dst, unsigned size)
{
    return snprintf(dst, size,
        "{\"address\":68,\"variant\":\"SHT4x, exact variant unknown\","
        "\"valid\":%s,\"error\":%d,\"attempts\":%u,\"samples\":%u,"
        "\"age_ms\":%lld,\"raw\":\"%02x%02x%02x%02x%02x%02x\",\"heater\":false}",
        valid ? "true" : "false", last_error, attempts, samples,
        (long long)(valid ? k_uptime_get() - sampled_at : -1),
        frame[0], frame[1], frame[2], frame[3], frame[4], frame[5]);
}
