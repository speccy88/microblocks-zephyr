/*
 * SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
 * SPDX-FileCopyrightText: 2026 MicroBlocks Zephyr contributors
 * SPDX-License-Identifier: Apache-2.0
 *
 * ES8311 register initialization adapted from Espressif esp_codec_dev,
 * distributed in Waveshare ESP32-S3-RLCD-4.2 revision a861929d91f25e7fbe2e0e014691f0fbedcaa64e.
 * See docs/AUDIO.md and LICENSES.md. Fixed-rate DAC output only.
 */
#include "rlcd_audio.h"
#include <errno.h>
#include <stdio.h>
#include <zephyr/kernel.h>

#if defined(CONFIG_I2S)
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/i2s.h>
#include <zephyr/init.h>
#include <hal/gpio_ll.h>
#include <soc/gpio_struct.h>
#include <soc/i2s_struct.h>
#include <zephyr/sys/atomic.h>

#define RATE 24000u
#define FRAMES 256u
#define BLOCK_BYTES (FRAMES * 2u * sizeof(int16_t))
#define BLOCKS 4
static const struct device *const bus = DEVICE_DT_GET(DT_NODELABEL(i2c0));
static const struct device *const output = DEVICE_DT_GET(DT_NODELABEL(i2s0));
static const struct gpio_dt_spec amp = GPIO_DT_SPEC_GET(DT_PATH(zephyr_user), audio_amp_gpios);
K_MEM_SLAB_DEFINE(audio_slab, BLOCK_BYTES, BLOCKS, 4);
K_MUTEX_DEFINE(audio_lock);
K_SEM_DEFINE(audio_request, 0, 1);
static atomic_t busy, cancelled, initialized, blocks_queued, frames_queued;
static atomic_t completed_frames, last_error, elapsed_ms, starts;
static atomic_t lrck_hz;
static atomic_t lrck_edges;
static struct gpio_callback lrck_callback;
static int tone_hz, tone_ms, tone_volume;

static int audio_boot(void)
{
    return gpio_is_ready_dt(&amp) ? gpio_pin_configure_dt(&amp, GPIO_OUTPUT_INACTIVE) : -ENODEV;
}
SYS_INIT(audio_boot, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY);

static const int16_t sine[64] = {
    0,803,1598,2378,3135,3862,4551,5197,5793,6333,6811,7225,7568,7839,8035,8153,
    8192,8153,8035,7839,7568,7225,6811,6333,5793,5197,4551,3862,3135,2378,1598,803,
    0,-803,-1598,-2378,-3135,-3862,-4551,-5197,-5793,-6333,-6811,-7225,-7568,-7839,-8035,-8153,
    -8192,-8153,-8035,-7839,-7568,-7225,-6811,-6333,-5793,-5197,-4551,-3862,-3135,-2378,-1598,-803
};

static int reg_write(uint8_t reg, uint8_t value)
{
    return i2c_reg_write_byte(bus, 0x18, reg, value);
}

static int reg_read(uint8_t reg, uint8_t *value)
{
    return i2c_reg_read_byte(bus, 0x18, reg, value);
}

static int mute(bool value)
{
    uint8_t reg;
    int err = reg_read(0x31, &reg);
    return err ? err : reg_write(0x31, (reg & 0x9f) | (value ? 0x60 : 0));
}

static int codec_init(void)
{
    if (atomic_get(&initialized)) return 0;
    if (!device_is_ready(bus) || !device_is_ready(output) || !gpio_is_ready_dt(&amp))
        return -ENODEV;
    int err = gpio_pin_configure_dt(&amp, GPIO_OUTPUT_INACTIVE);
    if (err) return err;
    uint8_t id1, id2;
    if ((err = reg_read(0xfd, &id1)) || (err = reg_read(0xfe, &id2))) return err;
    if (id1 != 0x83 || id2 != 0x11) return -ENODEV;
    /* Vendor open/start sequence; PA stays off. ADC serial output disabled.
     * MCLK/FS = 256, pre_div=1, pre_multi=1, DAC OSR=16 at 24 kHz.
     * 0x32=0xbf is 0 dB DAC gain; amplitude is bounded in PCM, not positive gain. */
    static const uint8_t setup[][2] = {
        {0x44,0x08},{0x44,0x08},{0x01,0x30},{0x02,0x00},{0x03,0x10},
        {0x16,0x24},{0x04,0x10},{0x05,0x00},{0x0b,0x00},{0x0c,0x00},
        {0x10,0x1f},{0x11,0x7f},{0x00,0x80},{0x01,0x3f},{0x06,0x03},
        {0x13,0x10},{0x1b,0x0a},{0x1c,0x6a},{0x44,0x58},
        {0x02,0x00},{0x03,0x10},{0x04,0x10},{0x05,0x00},{0x07,0x00},{0x08,0xff},
        {0x09,0x0c},{0x0a,0x4c},{0x17,0xbf},{0x0e,0x02},{0x12,0x00},
        {0x14,0x1a},{0x0d,0x01},{0x15,0x40},{0x37,0x08},{0x45,0x00},
        {0x32,0xbf},{0x31,0x60}
    };
    for (unsigned i = 0; i < ARRAY_SIZE(setup); ++i)
        if ((err = reg_write(setup[i][0], setup[i][1]))) return err;
    k_sleep(K_MSEC(20));
    atomic_set(&initialized, 1);
    return 0;
}

static int configure(void)
{
    struct i2s_config cfg = {
        .word_size = 16, .channels = 2,
        .format = I2S_FMT_DATA_FORMAT_I2S,
        .options = I2S_OPT_FRAME_CLK_CONTROLLER | I2S_OPT_BIT_CLK_CONTROLLER,
        .frame_clk_freq = RATE, .mem_slab = &audio_slab,
        .block_size = BLOCK_BYTES, .timeout = 100
    };
    return i2s_configure(output, I2S_DIR_TX, &cfg);
}

static void count_lrck(const struct device *port, struct gpio_callback *cb, gpio_port_pins_t pins)
{
    ARG_UNUSED(port); ARG_UNUSED(cb); ARG_UNUSED(pins);
    atomic_inc(&lrck_edges);
}

static void measure_lrck(void)
{
    /* Count edges with the GPIO peripheral, avoiding polling aliasing. The
     * input-enable bit does not change the I2S output matrix. */
    gpio_ll_input_enable(&GPIO, 45);
    gpio_init_callback(&lrck_callback, count_lrck, BIT(13));
    gpio_add_callback(amp.port, &lrck_callback);
    atomic_clear(&lrck_edges);
    uint32_t start = k_cycle_get_32();
    int err = gpio_pin_interrupt_configure(amp.port, 13, GPIO_INT_EDGE_RISING);
    if (!err) k_sleep(K_MSEC(5));
    gpio_pin_interrupt_configure(amp.port, 13, GPIO_INT_DISABLE);
    uint32_t usecs = k_cyc_to_us_floor32(k_cycle_get_32() - start);
    gpio_remove_callback(amp.port, &lrck_callback);
    atomic_set(&lrck_hz, err ? err : atomic_get(&lrck_edges) * 1000000u / usecs);
}

static void audio_worker(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);
    for (;;) {
        k_sem_take(&audio_request, K_FOREVER);
        k_mutex_lock(&audio_lock, K_FOREVER);
        int frequency = tone_hz, duration = tone_ms, volume = tone_volume;
        k_mutex_unlock(&audio_lock);
        int64_t began = k_uptime_get();
        uint32_t total = duration * (RATE / 1000), generated = 0, phase = 0;
        uint32_t step = (uint64_t)frequency * UINT64_C(4294967296) / RATE;
        int err = configure();
        bool started = false;
        while (!err && generated < total && !atomic_get(&cancelled)) {
            void *block;
            err = k_mem_slab_alloc(&audio_slab, &block, K_MSEC(100));
            if (err) break;
            int16_t *pcm = block;
            unsigned count = MIN(FRAMES, total - generated);
            for (unsigned i = 0; i < count; ++i) {
                unsigned pos = generated + i;
                unsigned ramp = MIN(120u, MIN(pos, total - 1u - pos));
                int32_t sample = (int32_t)sine[phase >> 26] * volume / 100;
                sample = sample * (int32_t)ramp / 120;
                pcm[2*i] = pcm[2*i+1] = (int16_t)sample;
                phase += step;
            }
            err = i2s_write(output, block, count * 2u * sizeof(int16_t));
            if (err) { k_mem_slab_free(&audio_slab, block); break; }
            generated += count;
            atomic_inc(&blocks_queued);
            atomic_add(&frames_queued, count);
            /* Prequeue two DMA blocks before enabling the amplifier. */
            if (!started && (generated >= 2 * FRAMES || generated == total)) {
                err = i2s_trigger(output, I2S_DIR_TX, I2S_TRIGGER_START);
                if (!err) started = true;
                if (!err && !atomic_get(&cancelled)) err = mute(false);
                if (!err && !atomic_get(&cancelled) && volume) err = gpio_pin_set_dt(&amp, 1);
                if (!err) measure_lrck();
            }
        }
        if (!err && started && !atomic_get(&cancelled)) {
            err = i2s_trigger(output, I2S_DIR_TX, I2S_TRIGGER_DRAIN);
            /* Driver releases DMA blocks only from completion callbacks.
             * A bounded wait proves reclamation; timeout mutes and drops. */
            int64_t deadline = k_uptime_get() + 300;
            while (!err && k_mem_slab_num_free_get(&audio_slab) != BLOCKS && !atomic_get(&cancelled)) {
                if (k_uptime_get() > deadline) { err = -ETIMEDOUT; break; }
                k_sleep(K_MSEC(1));
            }
            if (!err && !atomic_get(&cancelled)) atomic_set(&completed_frames, generated);
        }
        gpio_pin_set_dt(&amp, 0);
        int mute_err = mute(true);
        if (!err) err = mute_err;
        i2s_trigger(output, I2S_DIR_TX, I2S_TRIGGER_DROP);
        atomic_set(&elapsed_ms, (atomic_val_t)(k_uptime_get() - began));
        atomic_set(&last_error, err);
        atomic_clear(&busy);
    }
}
K_THREAD_DEFINE(audio_thread, 2048, audio_worker, NULL, NULL, NULL, 6, 0, 0);

int rlcd_audio_play(int frequency, int duration_ms, int volume)
{
    if (frequency < 50 || frequency > 4000 || duration_ms < 1 || duration_ms > 5000 || volume < 0 || volume > 100)
        return -EINVAL;
    k_mutex_lock(&audio_lock, K_FOREVER);
    if (atomic_get(&busy)) { k_mutex_unlock(&audio_lock); return -EBUSY; }
    int err = codec_init();
    if (!err) {
        tone_hz = frequency; tone_ms = duration_ms; tone_volume = volume;
        atomic_clear(&cancelled); atomic_clear(&blocks_queued); atomic_clear(&frames_queued);
        atomic_clear(&completed_frames); atomic_clear(&last_error); atomic_clear(&elapsed_ms);
        atomic_set(&busy, 1); atomic_inc(&starts); k_sem_give(&audio_request);
    } else atomic_set(&last_error, err);
    k_mutex_unlock(&audio_lock);
    return err;
}

void rlcd_audio_stop(void)
{
    atomic_set(&cancelled, 1);
    if (atomic_get(&initialized)) gpio_pin_set_dt(&amp, 0);
}

bool rlcd_audio_busy(void) { return atomic_get(&busy) != 0; }

int rlcd_audio_status(char *dst, unsigned size)
{
    if (!device_is_ready(bus)) return -ENODEV;
    uint8_t id1, id2, format, clock, dac, gain, muted;
    int err = reg_read(0xfd, &id1);
    if (!err) err = reg_read(0xfe, &id2);
    if (!err) err = reg_read(0x09, &format);
    if (!err) err = reg_read(0x01, &clock);
    if (!err) err = reg_read(0x04, &dac);
    if (!err) err = reg_read(0x32, &gain);
    if (!err) err = reg_read(0x31, &muted);
    if (err) return err;
    snprintf(dst, size, "{\"id\":\"%02x%02x\",\"ready\":%d,\"busy\":%d,\"format\":%u,\"clock\":%u,\"dac_osr\":%u,\"gain\":%u,\"mute\":%u,\"amp\":%d,\"rate\":%u,\"lrck_hz\":%ld,\"bits\":%u,\"slot\":%u,\"channels\":%u,\"blocks\":%ld,\"queued_frames\":%ld,\"completed_frames\":%ld,\"free_blocks\":%u,\"starts\":%ld,\"elapsed_ms\":%ld,\"error\":%ld}",
        id1, id2, (int)atomic_get(&initialized), (int)atomic_get(&busy), format, clock, dac, gain, muted,
        atomic_get(&initialized) ? gpio_pin_get_dt(&amp) : 0, RATE, (long)atomic_get(&lrck_hz),
        I2S0.tx_conf1.tx_bits_mod+1u, I2S0.tx_conf1.tx_tdm_chan_bits+1u, I2S0.tx_tdm_ctrl.tx_tdm_tot_chan_num+1u,
        (long)atomic_get(&blocks_queued), (long)atomic_get(&frames_queued), (long)atomic_get(&completed_frames),
        k_mem_slab_num_free_get(&audio_slab), (long)atomic_get(&starts), (long)atomic_get(&elapsed_ms), (long)atomic_get(&last_error));
    return 0;
}
#else
int rlcd_audio_play(int frequency, int duration_ms, int volume)
{ ARG_UNUSED(frequency); ARG_UNUSED(duration_ms); ARG_UNUSED(volume); return -ENOTSUP; }
void rlcd_audio_stop(void) {}
bool rlcd_audio_busy(void) { return false; }
int rlcd_audio_status(char *dst, unsigned size)
{ ARG_UNUSED(dst); ARG_UNUSED(size); return -ENOTSUP; }
#endif
