/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
int fj_io_i2c_get(unsigned address, unsigned reg, uint8_t *value);
int fj_io_i2c_set(unsigned address, unsigned reg, uint8_t value);
int fj_io_i2c_read(unsigned address, uint8_t *data, size_t count);
int fj_io_i2c_write(unsigned address, const uint8_t *data, size_t count, bool stop);
int fj_io_i2c_exists(unsigned address);
void fj_io_i2c_cancel(void);
int fj_io_spi_setup(unsigned hz, unsigned mode, bool lsb);
int fj_io_spi_transfer(const uint8_t *tx, uint8_t *rx, size_t count);
int fj_io_analog_read(unsigned pin, unsigned mode, int *value);
int fj_io_pwm_write(unsigned pin, unsigned value);
void fj_io_pwm_stop(void);
void fj_io_prepare_gpio(unsigned pin);
int fj_io_info(char *dst, unsigned size);
#ifdef __cplusplus
}
#endif
