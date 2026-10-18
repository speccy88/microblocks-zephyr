/* SPDX-License-Identifier: MIT */
#include "generic_io_fakes.h"
#include "generic_io.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

const device fake_devices[5]={{0},{1},{2},{3},{4}};
static bool ready[5]={false,true,false,false,true};
static unsigned init_count, transfer_count, release_count, pwm_count, ctrl_count;
static unsigned actual_hz, actual_op, period, pulse, adc_pin, adc_mode, adc_bits;
static int transfer_error, pwm_error, adc_value=1023;
static const spi_config *cached;
static uint8_t sent[256];
bool device_is_ready(const device *d) { return ready[d->id]; }
int device_init(const device *d) { assert(d->id==spi3||d->id==ledc0);++init_count;ready[d->id]=true;return 0; }
int pinctrl_apply_state(int node,int state) { assert((node==spi3||node==ledc0)&&state==0);++ctrl_count;return 0; }
int gpio_pin_configure(const device *d,unsigned pin,int flags)
{ assert(d->id==gpio0&&(pin==1||pin==2||pin==17)&&flags==GPIO_INPUT);++release_count;return 0; }
int i2c_reg_read_byte(const device *d,unsigned address,unsigned reg,uint8_t *value)
{ assert(d->id==i2c0&&address==24&&reg==253);*value=0x83;return 0; }
int i2c_reg_write_byte(const device *d,unsigned address,unsigned reg,uint8_t value)
{ assert(d->id==i2c0&&address==42&&reg==7&&value==9);return 0; }
int spi_transceive(const device *d,const spi_config *cfg,const spi_buf_set *tx,const spi_buf_set *rx)
{
    assert(d->id==spi3&&tx->count==1&&tx->buffers[0].len<=256);
    ++transfer_count;
    /* Match the real driver's pointer-identity cache. */
    if(cached!=cfg){actual_hz=cfg->frequency;actual_op=cfg->operation;cached=cfg;}
    size_t n=tx->buffers[0].len;memcpy(sent,tx->buffers[0].buf,n);
    if(rx){assert(rx->count==1&&rx->buffers[0].len==n);
        for(size_t i=0;i<n;++i)((uint8_t *)rx->buffers[0].buf)[i]=sent[i]^0x5a;}
    return transfer_error;
}
int pwm_set(const device *d,unsigned channel,uint32_t p,uint32_t duty,int flags)
{ assert(d->id==ledc0&&channel==0&&flags==0);++pwm_count;period=p;pulse=duty;return pwm_error; }
void pinMode(unsigned pin,int mode){assert(pin<=1);adc_pin=pin;adc_mode=mode;}
void analogReadResolution(int bits){adc_bits=bits;}
int analogRead(unsigned pin){assert(pin==adc_pin);return adc_value;}

int main()
{
    char info[384];rlcd_io_info(info,sizeof(info));
    assert(!init_count&&!transfer_count&&!pwm_count&&!ctrl_count);
    assert(strstr(info,"\"spi_initialized\":0")&&strstr(info,"\"pwm_initialized\":0"));
    assert(!rlcd_io_spi_setup(250000,3,true));
    assert(!rlcd_io_spi_transfer(nullptr,nullptr,0)&&!init_count);
    uint8_t data[3]={1,2,3};
    assert(!rlcd_io_spi_transfer(data,data,3));
    assert(init_count==1&&release_count==3&&actual_hz==250000&&actual_op==(SPI_WORD_SET(8)|7));
    assert(data[0]==0x5b&&data[2]==0x59);
    assert(!rlcd_io_spi_setup(1000000,0,false));
    assert(!rlcd_io_spi_transfer(data,nullptr,3));
    assert(init_count==1&&actual_hz==1000000&&actual_op==SPI_WORD_SET(8)&&release_count==6);
    transfer_error=-EIO;assert(rlcd_io_spi_transfer(data,nullptr,3)==-EIO&&release_count==9);transfer_error=0;
    assert(rlcd_io_spi_setup(1,0,false)==-EINVAL);
    assert(rlcd_io_spi_transfer(data,nullptr,257)==-EINVAL);
    uint8_t value;assert(!rlcd_io_i2c_get(24,253,&value)&&value==0x83);
    assert(!rlcd_io_i2c_set(42,7,9));
    assert(rlcd_io_i2c_set(128,0,0)==-EINVAL);
    int sample;assert(!rlcd_io_analog_read(1,2,&sample)&&sample==1023&&adc_pin==1&&adc_mode==INPUT_PULLDOWN&&adc_bits==10);
    adc_value=-EIO;assert(rlcd_io_analog_read(0,0,&sample)==-EIO);
    assert(rlcd_io_analog_read(2,0,&sample)==-EINVAL);
    assert(!rlcd_io_pwm_write(2,512)&&init_count==2&&period==1000000&&pulse==500488);
    rlcd_io_info(info,sizeof(info));assert(strstr(info,"\"pwm_active\":1"));
    rlcd_io_prepare_gpio(0);assert(pwm_count==1);
    rlcd_io_prepare_gpio(2);assert(pwm_count==2&&pulse==0&&release_count==10);
    assert(!rlcd_io_pwm_write(2,1023)&&pulse==1000000);
    assert(!rlcd_io_spi_transfer(data,nullptr,3)&&pulse==0&&release_count==14);
    assert(rlcd_io_pwm_write(0,100)==-EINVAL);
    assert(rlcd_io_pwm_write(2,1024)==-EINVAL);
    pwm_error=-EIO;assert(rlcd_io_pwm_write(2,1)==-EIO&&release_count==15);
    printf("{\"result\":\"PASS\",\"scope\":\"actual C++ backend with driver doubles\",\"deferred_init\":true,\"spi_cache_refresh\":true,\"spi_release_on_error\":true,\"adc_mapping_errors\":true,\"pwm_stop_and_duty\":true,\"physical_outputs\":false}\n");
}
