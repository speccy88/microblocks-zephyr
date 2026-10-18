/* SPDX-License-Identifier: Apache-2.0
 * PIO bit timings derived from Zephyr ws2812_rpi_pico_pio.c
 * Copyright (c) 2023 TOKITA Hiroshi
 * Copyright (c) 2025 The Zephyr Project Contributors
 * Fruit Jam integration: reserve PIO1 with GPIO base 16 for physical GPIO32.
 * No DMA or interrupt masking; five pixels take less than 1 ms per update.
 */
#include <zephyr/kernel.h>
#include <hardware/clocks.h>
#include <hardware/gpio.h>
#include <hardware/pio.h>
#include <errno.h>

static const uint16_t instructions[] = {0x6321, 0x1223, 0x1200, 0x0200};
static const struct pio_program program = {
    .instructions = instructions, .length = 4, .origin = -1
};
static int sm = -1;
static uint32_t pixels[5];

static int pixels_init(void)
{
    if (sm >= 0) return 0;
    /* Changing GPIO base would affect every SM in this PIO instance. */
    for (unsigned i = 0; i < 4; ++i)
        if (pio_sm_is_claimed(pio1, i)) return -EBUSY;
    if (!pio_can_add_program(pio1, &program)) return -ENOMEM;
    int err = pio_set_gpio_base(pio1, 16);
    if (err) return err;
    int selected = pio_claim_unused_sm(pio1, false);
    if (selected < 0) return -EBUSY;
    unsigned offset = pio_add_program(pio1, &program);
    pio_sm_config config = pio_get_default_sm_config();
    sm_config_set_wrap(&config, offset, offset + 3);
    sm_config_set_sideset(&config, 1, false, false);
    sm_config_set_sideset_pins(&config, 32);
    sm_config_set_out_shift(&config, false, true, 24);
    sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv(&config, (float)clock_get_hz(clk_sys) / 8000000);
    pio_gpio_init(pio1, 32);
    pio_sm_set_consecutive_pindirs(pio1, selected, 32, 1, true);
    pio_sm_init(pio1, selected, offset, &config);
    pio_sm_set_enabled(pio1, selected, true);
    sm = selected;
    return 0;
}

static int pixels_send(void)
{
    int64_t deadline = k_uptime_get() + 20;
    for (unsigned i = 0; i < 5; ++i) {
        while (pio_sm_is_tx_fifo_full(pio1, sm)) {
            if (k_uptime_get() >= deadline) return -ETIMEDOUT;
            k_yield();
        }
        pio_sm_put(pio1, sm, pixels[i]);
    }
    while (!pio_sm_is_tx_fifo_empty(pio1, sm)) {
        if (k_uptime_get() >= deadline) return -ETIMEDOUT;
        k_yield();
    }
    /* Last shift word may still be transmitting (30 us), then reset >=80 us. */
    k_busy_wait(120);
    return 0;
}

int fj_pixels_set(unsigned index, unsigned red, unsigned green, unsigned blue)
{
    if (index >= 5 || red > 255 || green > 255 || blue > 255) return -EINVAL;
    int err = pixels_init();
    if (err) return err;
    pixels[index] = (green << 24) | (red << 16) | (blue << 8);
    return pixels_send();
}

int fj_pixels_off(void)
{
    if (sm < 0) return 0; /* Quiet boot: do not claim pins until explicitly used. */
    for (unsigned i = 0; i < 5; ++i) pixels[i] = 0;
    return pixels_send();
}

int fj_pixels_initialized(void) { return sm >= 0; }
