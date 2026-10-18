/* SPDX-License-Identifier: MIT */
#include "generic_io.h"
#include <Arduino.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/drivers/pwm.h>
#include <zephyr/drivers/pinctrl.h>
#include <errno.h>
#include <stdio.h>

static const device *const bus=DEVICE_DT_GET(DT_NODELABEL(i2c0));
static const device *const spi=DEVICE_DT_GET(DT_NODELABEL(spi3));
static const device *const pwm=DEVICE_DT_GET(DT_NODELABEL(ledc0));
static const device *const gpio=DEVICE_DT_GET(DT_NODELABEL(gpio0));
PINCTRL_DT_DEFINE(DT_NODELABEL(spi3));
PINCTRL_DT_DEFINE(DT_NODELABEL(ledc0));
static bool spi_initialized, pwm_initialized, pwm_active;
static unsigned spi_hz=1000000, spi_mode;
static bool spi_lsb;
static int last_error;
/* Zephyr caches configuration by pointer identity. Alternate stable objects so
 * setup changes and retries are reapplied, without leaving a stack pointer. */
static spi_config spi_configs[2];
static unsigned spi_config_index;

static int initialize(const device *dev, bool *initialized)
{
    if (*initialized) return device_is_ready(dev) ? 0 : -ENODEV;
    int err=device_init(dev);
    if (err && err!=-EALREADY) return err;
    if (!device_is_ready(dev)) return -ENODEV;
    *initialized=true;
    return 0;
}

extern "C" int rlcd_io_i2c_get(unsigned address, unsigned reg, uint8_t *value)
{
    if (address>127 || reg>255 || !value) return -EINVAL;
    if (!device_is_ready(bus)) return last_error=-ENODEV;
    return last_error=i2c_reg_read_byte(bus,address,reg,value);
}

extern "C" int rlcd_io_i2c_set(unsigned address, unsigned reg, uint8_t value)
{
    if (address>127 || reg>255) return -EINVAL;
    if (!device_is_ready(bus)) return last_error=-ENODEV;
    return last_error=i2c_reg_write_byte(bus,address,reg,value);
}

extern "C" int rlcd_io_spi_setup(unsigned hz, unsigned mode, bool lsb)
{
    if (hz<10000 || hz>8000000 || mode>3) return -EINVAL;
    spi_hz=hz;spi_mode=mode;spi_lsb=lsb;
    return 0; /* Configuration alone never initializes or drives external pins. */
}

extern "C" void rlcd_io_pwm_stop(void)
{
    if (!pwm_initialized || !pwm_active) return;
    pwm_set(pwm,0,1000000,0,0);
    gpio_pin_configure(gpio,17,GPIO_INPUT);
    pwm_active=false;
}

extern "C" void rlcd_io_prepare_gpio(unsigned pin)
{
    if (pin==2) rlcd_io_pwm_stop();
}

extern "C" int rlcd_io_spi_transfer(const uint8_t *tx, uint8_t *rx, size_t count)
{
    if (!count) return 0;
    if (!tx || count>256) return -EINVAL;
    rlcd_io_pwm_stop();
    int err=initialize(spi,&spi_initialized);
    if (!err) err=pinctrl_apply_state(PINCTRL_DT_DEV_CONFIG_GET(DT_NODELABEL(spi3)),PINCTRL_STATE_DEFAULT);
    if (!err) {
        spi_config &cfg=spi_configs[spi_config_index^=1];
        cfg={};
        cfg.frequency=spi_hz;
        cfg.operation=SPI_OP_MODE_MASTER | SPI_WORD_SET(8) |
            ((spi_mode&1) ? SPI_MODE_CPHA : 0) | ((spi_mode&2) ? SPI_MODE_CPOL : 0) |
            (spi_lsb ? SPI_TRANSFER_LSB : SPI_TRANSFER_MSB);
        spi_buf out={.buf=const_cast<uint8_t *>(tx),.len=count};
        spi_buf in={.buf=rx,.len=count};
        spi_buf_set outs={.buffers=&out,.count=1},ins={.buffers=&in,.count=1};
        err=spi_transceive(spi,&cfg,&outs,rx ? &ins : nullptr);
    }
    /* Restore high impedance after the explicitly requested transaction. */
    static const unsigned pins[]={1,2,17};
    for (unsigned pin: pins) {
        int release=gpio_pin_configure(gpio,pin,GPIO_INPUT);
        if (!err) err=release;
    }
    return last_error=err;
}

extern "C" int rlcd_io_analog_read(unsigned pin, unsigned mode, int *value)
{
    if (pin>1 || mode>2 || !value) return -EINVAL;
    pinMode(pin,mode==1 ? INPUT_PULLUP : mode==2 ? INPUT_PULLDOWN : INPUT);
    analogReadResolution(10);
    int sample=analogRead(pin);
    if (sample<0) return last_error=sample;
    if (sample>1023) return last_error=-ERANGE;
    *value=sample;
    return last_error=0;
}

extern "C" int rlcd_io_pwm_write(unsigned pin, unsigned value)
{
    if (pin!=2 || value>1023) return -EINVAL;
    int err=initialize(pwm,&pwm_initialized);
    if (!err) err=pinctrl_apply_state(PINCTRL_DT_DEV_CONFIG_GET(DT_NODELABEL(ledc0)),PINCTRL_STATE_DEFAULT);
    if (!err) err=pwm_set(pwm,0,1000000,(uint64_t)value*1000000/1023,0);
    if (!err) pwm_active=true;
    else gpio_pin_configure(gpio,17,GPIO_INPUT);
    return last_error=err;
}

extern "C" int rlcd_io_info(char *dst, unsigned size)
{
    snprintf(dst,size,"{\"digital_gpio\":[1,2,17],\"analog_gpio\":[1,2],\"analog_max\":1023,\"pwm_pin\":2,\"pwm_hz\":1000,\"dac\":false,\"i2c_gpio\":[13,14],\"spi_gpio\":[1,2,17],\"spi_cs\":null,\"spi_hz\":%u,\"spi_mode\":%u,\"spi_lsb\":%d,\"spi_initialized\":%d,\"pwm_initialized\":%d,\"pwm_active\":%d,\"error\":%d}",
        spi_hz,spi_mode,spi_lsb,spi_initialized,pwm_initialized,pwm_active,last_error);
    return 0;
}
