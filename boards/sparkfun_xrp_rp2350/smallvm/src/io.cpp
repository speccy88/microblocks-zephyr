/* SPDX-License-Identifier: MIT */
#include "generic_io.h"
#include "xrp.h"
#include "vm/interp.h"
#include <Arduino.h>
#include <Wire.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/pwm.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#ifndef ARDUINO_SPARKFUN_XRP_ZEPHYR
#error "The isolated XRP Arduino variant is required"
#endif
static_assert(NUM_OF_DIGITAL_PINS == 48, "Raw XRP mapping changed");
static const device *const bus = DEVICE_DT_GET(DT_NODELABEL(i2c1));
static const device *const hi = DEVICE_DT_GET(DT_NODELABEL(gpio0_hi));
static const device *const pwm = DEVICE_DT_GET(DT_NODELABEL(pwm));
static const device *const adc = DEVICE_DT_GET(DT_NODELABEL(adc));
/* SDK PWM_GPIO_SLICE_NUM: GPIO16..31 alias slices0..7. */
static unsigned pwm_channel(unsigned p) { return p & 15u; }
static int last_error;
static uint8_t pending_data[32];
static size_t pending_count;
static unsigned pending_address;
K_MUTEX_DEFINE(adc_job_lock);
K_SEM_DEFINE(adc_request,0,1);
K_SEM_DEFINE(adc_done,0,1);
static bool adc_busy,adc_finished,adc_abandoned;
static unsigned adc_pin;
static int adc_value,adc_error;
static void adc_worker(void *a,void *b,void *c)
{
    (void)a;(void)b;(void)c;
    for(;;){
        k_sem_take(&adc_request,K_FOREVER);
        k_mutex_lock(&adc_job_lock,K_FOREVER);unsigned pin=adc_pin;k_mutex_unlock(&adc_job_lock);
        analogReadResolution(10);
        int sample=analogRead(pin);
        int error=sample<0 ? sample : sample>1023 ? -ERANGE : 0;
        k_mutex_lock(&adc_job_lock,K_FOREVER);
        if(adc_abandoned){adc_busy=false;adc_finished=false;}
        else {adc_value=sample;adc_error=error;adc_finished=true;k_sem_give(&adc_done);}
        k_mutex_unlock(&adc_job_lock);
    }
}
K_THREAD_DEFINE(xrp_adc_worker,2048,adc_worker,NULL,NULL,NULL,8,0,0);
static bool output_allowed(unsigned p) { return sparkfun_xrp_output_allowed(p); }
extern "C" void xrp_io_init(void)
{
    xrp_motors_coast();
    if(device_is_ready(hi))gpio_pin_configure(hi,4,GPIO_INPUT | GPIO_PULL_UP);
}
extern "C" int xrp_button(unsigned n)
{
    if(n || !device_is_ready(hi))return -EINVAL;
    int v=gpio_pin_get(hi,4);return v<0 ? v : !v;
}
extern "C" void hardwareInit(void) { initTasks();xrp_io_init();Wire.begin(); }
extern "C" uint32 microsecs(void) { return micros(); }
extern "C" uint32 millisecs(void) { return millis(); }
extern "C" uint64 totalMicrosecs(void) { return k_ticks_to_us_floor64(k_uptime_ticks()); }
extern "C" uint32 seconds(void) { return millis()/1000; }
extern "C" void handleMicosecondClockWrap(void) {}
extern "C" void smallvmDelay(unsigned long ms) { delay(ms); }
extern "C" void lightSleep(int ms) { if(ms>0)delay(ms); }
extern "C" void deepSleep(int sec) { (void)sec;fail(primitiveNotImplemented); }
extern "C" int pinCount(void) { return 48; }
extern "C" int mapDigitalPinNum(int p) { return p>=0 && sparkfun_xrp_pin_allowed(p) ? p : -1; }
extern "C" void setPinMode(int p,int mode) { if(mapDigitalPinNum(p)>=0)pinMode(p,(PinMode)mode); }
extern "C" OBJ primDigitalPins(OBJ *) { return int2obj(48); }
extern "C" OBJ primAnalogPins(OBJ *) { return int2obj(7); }
extern "C" void xrp_io_prepare_gpio(unsigned p) { (void)p; }
extern "C" OBJ primDigitalRead(int n,OBJ *a)
{
    if(n<1)return fail(notEnoughArguments);
    if(!isInt(a[0]))return fail(needsIntegerError);
    int p=mapDigitalPinNum(obj2int(a[0]));if(p<0)return fail(badPinError);
    PinMode mode=INPUT;
    if(n>1 && a[1]==trueObj)mode=INPUT_PULLUP;
    else if(n>1 && IS_TYPE(a[1],StringType)) {
        if(!strcmp(obj2str(a[1]),"up"))mode=INPUT_PULLUP;
        else if(!strcmp(obj2str(a[1]),"down"))mode=INPUT_PULLDOWN;
    }
    pinMode(p,mode);
    int v=gpio_pin_get(digitalPinToPortDevice(p),digitalPinToPinIndex(p));
    return v<0 ? fail(primitiveNotImplemented) : v ? trueObj : falseObj;
}
extern "C" void primDigitalSet(int p,int v)
{
    if(p<0 || !output_allowed(p)){fail(badPinError);return;}
    pinMode(p,OUTPUT);digitalWrite(p,v?HIGH:LOW);
}
extern "C" void primDigitalWrite(OBJ *a)
{ if(!isInt(a[0]))fail(needsIntegerError);else primDigitalSet(obj2int(a[0]),a[1]!=falseObj); }
extern "C" void xrp_io_pwm_stop(void)
{
    if(device_is_ready(pwm))for(unsigned p=12;p<=19;++p){pwm_set(pwm,pwm_channel(p),1000000,0,0);pinMode(p,INPUT);}
    xrp_motors_coast();
}
extern "C" void turnOffPins(void) { xrp_capture_stop();xrp_io_i2c_cancel();xrp_io_pwm_stop(); }
extern "C" int xrp_io_analog_read(unsigned p,unsigned mode,int *v)
{
    if(p<40 || p>46 || mode || !v)return -EINVAL;
    if(!device_is_ready(adc))return last_error=-ENODEV;
    k_mutex_lock(&adc_job_lock,K_FOREVER);
    if(adc_busy){k_mutex_unlock(&adc_job_lock);return last_error=-EBUSY;}
    adc_pin=p;adc_busy=true;adc_finished=false;adc_abandoned=false;
    k_sem_reset(&adc_done);k_sem_give(&adc_request);k_mutex_unlock(&adc_job_lock);
    int wait_error=k_sem_take(&adc_done,K_MSEC(50));
    k_mutex_lock(&adc_job_lock,K_FOREVER);
    int error;
    if(!adc_finished){adc_abandoned=true;error=wait_error ? -ETIMEDOUT : -EIO;}
    else {error=adc_error;if(!error)*v=adc_value;adc_busy=false;adc_finished=false;}
    k_mutex_unlock(&adc_job_lock);
    return last_error=error;
}
extern "C" int xrp_io_pwm_write(unsigned p,unsigned v)
{
    if(p<12 || p>19 || v>1023)return -ENOTSUP;
    if(!device_is_ready(pwm))return -ENODEV;
    int e=pwm_set(pwm,pwm_channel(p),1000000,(uint64_t)v*1000000/1023,0);
    if(!e)sparkfun_xrp_pwm_mux(p);
    return last_error=e;
}
extern "C" void xrp_io_i2c_cancel(void) { pending_count = 0; }
extern "C" int xrp_io_i2c_get(unsigned address, unsigned reg, uint8_t *value)
{
    xrp_io_i2c_cancel();
    if (address > 127 || reg > 255 || !value) return -EINVAL;
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    return last_error = i2c_reg_read_byte(bus, address, reg, value);
}
extern "C" int xrp_io_i2c_set(unsigned address, unsigned reg, uint8_t value)
{
    xrp_io_i2c_cancel();
    if (address > 127 || reg > 255) return -EINVAL;
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    return last_error = i2c_reg_write_byte(bus, address, reg, value);
}
extern "C" int xrp_io_i2c_read(unsigned address, uint8_t *data, size_t count)
{
    if (address > 127 || count > 32 || (!data && count)) return -EINVAL;
    if (!count) return 0;
    size_t pending = pending_count;
    xrp_io_i2c_cancel();
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    if (pending) {
        if (address != pending_address) return last_error = -EINVAL;
        return last_error = i2c_write_read(bus, address, pending_data, pending, data, count);
    }
    return last_error = i2c_read(bus, data, count, address);
}
extern "C" int xrp_io_i2c_write(unsigned address, const uint8_t *data, size_t count, bool stop)
{
    if (address > 127 || count > 32 || (!data && count)) return -EINVAL;
    if (!count) return 0;
    if (pending_count) { xrp_io_i2c_cancel(); return last_error = -EBUSY; }
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    if (!stop) {
        memcpy(pending_data, data, count); pending_count = count; pending_address = address;
        return last_error = 0;
    }
    return last_error = i2c_write(bus, data, count, address);
}
extern "C" int xrp_io_i2c_exists(unsigned address)
{
    xrp_io_i2c_cancel();
    if (address > 127) return -EINVAL;
    if (!device_is_ready(bus)) return last_error = -ENODEV;
    uint8_t unused = 0;
    return last_error = i2c_write(bus, &unused, 0, address);
}
/* Both onboard SPI buses stay reserved. Never drive SD/AirLift via raw blocks. */
extern "C" int xrp_io_spi_setup(unsigned hz, unsigned mode, bool lsb)
{ (void)hz; (void)mode; (void)lsb; return -ENOTSUP; }
extern "C" int xrp_io_spi_transfer(const uint8_t *tx, uint8_t *rx, size_t count)
{ (void)tx; (void)rx; (void)count; return -ENOTSUP; }

extern "C" int xrp_io_info(char *dst,unsigned n)
{
    snprintf(dst,n,"{\"digital_raw\":true,\"analog_gpio\":[40,41,42,43,44,45,46],\"i2c_gpio\":[38,39],\"actuators_enabled\":false,\"adc_ready\":%s,\"pwm_ready\":%s,\"adc_timeout_ms\":50,\"hardware_tested\":false,\"error\":%d}",device_is_ready(adc)?"true":"false",device_is_ready(pwm)?"true":"false",last_error);
    return 0;
}
