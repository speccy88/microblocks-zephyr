/* SPDX-License-Identifier: MPL-2.0
 * Pulse-list contract follows SmallVM v417 sensorPrims. Only production XRP
 * echo GPIO1 is accepted, with bounded storage and no VM-thread busy wait. */
#include "vm/interp.h"
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>

static const struct device *const port=DEVICE_DT_GET(DT_NODELABEL(gpio0));
static struct gpio_callback callback;
static volatile unsigned count;
static volatile bool active;
static uint32_t last_edge;
static int32_t durations[4];
static bool initialized;
static uint32_t now_us(void) { return microsecs(); }
void xrp_capture_stop(void)
{
    active=false;
    if(device_is_ready(port))gpio_pin_interrupt_configure(port,1,GPIO_INT_DISABLE);
}
static void edge(const struct device *dev,struct gpio_callback *cb,uint32_t pins)
{
    ARG_UNUSED(dev);ARG_UNUSED(cb);ARG_UNUSED(pins);
    if(!active || count>=ARRAY_SIZE(durations))return;
    uint32_t now=now_us(),delta=now-last_edge;
    if(delta>30000){xrp_capture_stop();return;}
    int level=gpio_pin_get(port,1);
    if(level<0){xrp_capture_stop();return;}
    durations[count++]=level ? -(int32_t)delta : (int32_t)delta;last_edge=now;
    if(count==ARRAY_SIZE(durations))xrp_capture_stop();
}
OBJ xrp_capture_start(int n,OBJ *a)
{
    if(n!=1)return fail(notEnoughArguments);
    if(!isInt(a[0]))return fail(needsIntegerError);
    if(obj2int(a[0])!=1)return fail(badPinError);
    xrp_capture_stop();
    if(!device_is_ready(port))return fail(primitiveNotImplemented);
    int e=gpio_pin_configure(port,1,GPIO_INPUT);
    if(!e && !initialized){gpio_init_callback(&callback,edge,BIT(1));e=gpio_add_callback(port,&callback);if(!e)initialized=true;}
    if(e)return fail(primitiveNotImplemented);
    unsigned key=irq_lock();count=0;last_edge=now_us();active=true;
    e=gpio_pin_interrupt_configure(port,1,GPIO_INT_EDGE_BOTH);irq_unlock(key);
    if(e){active=false;return fail(primitiveNotImplemented);}return trueObj;
}
OBJ xrp_capture_count(int n,OBJ *a)
{ (void)a;return n ? fail(notEnoughArguments) : int2obj(count); }
OBJ xrp_capture_end(int n,OBJ *a)
{
    (void)a;if(n)return fail(notEnoughArguments);
    unsigned key=irq_lock();xrp_capture_stop();unsigned used=count;count=0;irq_unlock(key);
    OBJ out=newObj(ListType,used+1,falseObj);if(!out)return falseObj;
    FIELD(out,0)=int2obj(used);
    for(unsigned i=0;i<used;++i)FIELD(out,i+1)=int2obj(durations[i]);
    return out;
}
