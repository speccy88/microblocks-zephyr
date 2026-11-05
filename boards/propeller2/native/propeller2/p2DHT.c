/* SPDX-License-Identifier: MPL-2.0 */
/* DHT22: bounded single-wire capture, checksum and signed tenths. */
#include <stdint.h>
#include <string.h>
#include <propeller2.h>
#include <smartpins.h>
#include "mem.h"
#include "interp.h"
#include "p2Board.h"
extern void invalidatePinModeTracking(int pin);

static int pulse(int pin,int level) {
    uint32_t start=_getus();
    while(_pinr(pin)==level) if((uint32_t)(_getus()-start)>=120) return -1;
    return _getus()-start;
}
static int readFrame(int pin,uint8_t *bytes) {
    memset(bytes,0,5);
    if(pulse(pin,1)<0||pulse(pin,0)<0||pulse(pin,1)<0) return 0;
    for(int bit=0;bit<40;bit++) {
        if(pulse(pin,0)<0) return 0;
        int high=pulse(pin,1);if(high<0) return 0;
        bytes[bit/8]=(bytes[bit/8]<<1)|(high>50);
    }
    return 1;
}
static int decode(const uint8_t *bytes,int *temperature,int *humidity) {
    if(((bytes[0]+bytes[1]+bytes[2]+bytes[3])&255)!=bytes[4]) return 0;
    *humidity=(bytes[0]<<8)|bytes[1];
    *temperature=((bytes[2]&127)<<8)|bytes[3];
    if(bytes[2]&128) *temperature=-*temperature;
    return *humidity<=1000 && *temperature>=-400 && *temperature<=800;
}
#ifndef P2_PERIPHERAL_HOST_TEST
OBJ p2DHT22(int argc,OBJ *args) {
    static int lastPin=-1,lastOK,temperature,humidity;
    static uint32_t lastTime;
    if(argc!=1||!isInt(args[0])) return fail(needsIntegerError);
    int pin=obj2int(args[0]);if(pin<0||pin>P2_LAST_USER_PIN) return fail(badPinError);
    uint32_t now=_getms();
    if(now<2000 && lastPin<0) return falseObj; /* sensor power-on settling */
    if(lastPin<0||(uint32_t)(now-lastTime)>=2000) {
        lastPin=pin;lastTime=now;
        invalidatePinModeTracking(pin);_pinclear(pin);
        _wrpin(pin,P_HIGH_15K|P_LOW_FAST);_pinl(pin);_waitus(1100);_pinh(pin);
        uint8_t bytes[5];lastOK=readFrame(pin,bytes)&&decode(bytes,&temperature,&humidity);
        _pinclear(pin);_pinf(pin);
    }
    if(!lastOK||lastPin!=pin) return falseObj;
    OBJ result=newObj(ListType,3,zeroObj);if(!result) return falseObj;
    FIELD(result,0)=int2obj(2);FIELD(result,1)=int2obj(temperature);FIELD(result,2)=int2obj(humidity);
    return result;
}
#endif
