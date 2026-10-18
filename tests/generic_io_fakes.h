/* SPDX-License-Identifier: MIT
 * Driver doubles for generic_io.cpp; never included in a firmware build. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#define DT_NODELABEL(name) name
enum { i2c0=1, spi3=2, ledc0=3, gpio0=4 };
struct device { int id; };
extern const device fake_devices[5];
#define DEVICE_DT_GET(node) (&fake_devices[node])
#define PINCTRL_DT_DEFINE(node)
#define PINCTRL_DT_DEV_CONFIG_GET(node) (node)
#define PINCTRL_STATE_DEFAULT 0
#define GPIO_INPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
#define INPUT_PULLDOWN 3
#define SPI_OP_MODE_MASTER 0
#define SPI_WORD_SET(bits) ((bits)<<8)
#define SPI_MODE_CPHA 1
#define SPI_MODE_CPOL 2
#define SPI_TRANSFER_LSB 4
#define SPI_TRANSFER_MSB 0
struct spi_config { unsigned frequency; unsigned operation; };
struct spi_buf { void *buf; size_t len; };
struct spi_buf_set { spi_buf *buffers; size_t count; };
bool device_is_ready(const device *);
int device_init(const device *);
int pinctrl_apply_state(int,int);
int gpio_pin_configure(const device *,unsigned,int);
int i2c_reg_read_byte(const device *,unsigned,unsigned,uint8_t *);
int i2c_reg_write_byte(const device *,unsigned,unsigned,uint8_t);
int spi_transceive(const device *,const spi_config *,const spi_buf_set *,const spi_buf_set *);
int pwm_set(const device *,unsigned,uint32_t,uint32_t,int);
void pinMode(unsigned,int);
void analogReadResolution(int);
int analogRead(unsigned);
