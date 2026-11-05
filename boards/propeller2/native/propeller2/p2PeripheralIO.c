/* SPDX-License-Identifier: MPL-2.0 */
/* Bounded, explicit peripheral transactions on user pins only. */
#include <stdint.h>
#include <propeller2.h>
#include <smartpins.h>
#include "mem.h"
#include "interp.h"
#include "p2Board.h"
extern void invalidatePinModeTracking(int pin);
static int keypadPins[8],keypadReady;
static int pinOK(int pin) { return pin>=0&&pin<=P2_LAST_USER_PIN; }
static void prepare(int pin) { invalidatePinModeTracking(pin);_pinclear(pin);_pinf(pin); }
void p2PeripheralIOReset(void) { keypadReady=0; }
OBJ p2KeypadInit(int argc,OBJ *args) {
    if(argc!=2||!IS_TYPE(args[0],ListType)||!IS_TYPE(args[1],ListType)) return fail(needsListError);
    if(obj2int(FIELD(args[0],0))!=4||obj2int(FIELD(args[1],0))!=4) return fail(indexOutOfRangeError);
    int pins[8];
    for(int i=0;i<8;i++) {
        OBJ value=FIELD(args[i/4],1+i%4);if(!isInt(value)) return fail(needsIntegerError);
        pins[i]=obj2int(value);if(!pinOK(pins[i])) return fail(badPinError);
        for(int j=0;j<i;j++) if(pins[i]==pins[j]) return fail(badPinError);
    }
    for(int i=0;i<8;i++) keypadPins[i]=pins[i];
    keypadReady=1;return trueObj; /* inert until scan */
}
OBJ p2KeypadScan(int argc,OBJ *args) {
    (void)argc;(void)args;if(!keypadReady) return int2obj(-2);
    for(int i=0;i<8;i++) prepare(keypadPins[i]);
    for(int i=4;i<8;i++) { _wrpin(keypadPins[i],P_HIGH_15K);_pinh(keypadPins[i]); }
    int mask=0;
    for(int row=0;row<4;row++) {
        _pinl(keypadPins[row]);_waitus(10);
        for(int col=0;col<4;col++) if(!_pinr(keypadPins[4+col])) mask|=1<<(4*row+col);
        _pinf(keypadPins[row]);
    }
    /* No inactive row is driven high. Reject ambiguous diode-less rectangles. */
    for(int row=0;row<4;row++) for(int other=row+1;other<4;other++) {
        int common=((mask>>(4*row))&(mask>>(4*other)))&15;
        if(common&(common-1)) return int2obj(-1);
    }
    return int2obj(mask);
}
static int threePins(OBJ *args,int *pins) {
    for(int i=0;i<3;i++) {
        if(!isInt(args[i])) { fail(needsIntegerError);return 0; }
        pins[i]=obj2int(args[i]);if(!pinOK(pins[i])) { fail(badPinError);return 0; }
        for(int j=0;j<i;j++) if(pins[i]==pins[j]) { fail(badPinError);return 0; }
    }
    return 1;
}
OBJ p2ShiftOut(int argc,OBJ *args) {
    int pins[3];if(argc!=5) return fail(notEnoughArguments);
    if(!threePins(args,pins)) return falseObj;
    if(args[4]!=trueObj&&args[4]!=falseObj) return fail(needsBooleanError);
    int msb=args[4]==trueObj,count;uint8_t bytes[32];
    if(IS_TYPE(args[3],ByteArrayType)) {
        count=BYTES(args[3]);if(count<1||count>32) return fail(indexOutOfRangeError);
        uint8_t *source=(uint8_t *)&FIELD(args[3],0);for(int i=0;i<count;i++)bytes[i]=source[i];
    } else if(IS_TYPE(args[3],ListType)) {
        count=obj2int(FIELD(args[3],0));if(count<1||count>32) return fail(indexOutOfRangeError);
        for(int i=0;i<count;i++) {
            OBJ value=FIELD(args[3],i+1);
            if(!isInt(value)||obj2int(value)<0||obj2int(value)>255) return fail(byteOutOfRange);
            bytes[i]=obj2int(value);
        }
    } else return fail(needsByteArray);
    for(int i=0;i<3;i++) prepare(pins[i]);
    _pinl(pins[1]);_pinl(pins[2]);
    for(int i=0;i<count;i++) for(int bit=0;bit<8;bit++) {
        _pinw(pins[0],!!(bytes[i]&(msb?(128>>bit):(1<<bit))));
        _pinh(pins[1]);_waitus(1);_pinl(pins[1]);_waitus(1);
    }
    _pinh(pins[2]);return trueObj;
}
OBJ p2ShiftIn(int argc,OBJ *args) {
    int pins[3];if(argc!=5) return fail(notEnoughArguments);
    if(!threePins(args,pins)) return falseObj;
    if(!isInt(args[3])) return fail(needsIntegerError);
    if(args[4]!=trueObj&&args[4]!=falseObj) return fail(needsBooleanError);
    int count=obj2int(args[3]),msb=args[4]==trueObj;
    if(count<1||count>32) return fail(indexOutOfRangeError);
    uint8_t bytes[32];
    for(int i=0;i<3;i++) prepare(pins[i]);
    _pinl(pins[1]);_pinl(pins[2]);_waitus(2);_pinh(pins[2]);_waitus(2);
    for(int i=0;i<count;i++) {
        int byte=0;
        for(int bit=0;bit<8;bit++) {
            if(_pinr(pins[0])) byte|=msb?(128>>bit):(1<<bit);
            _pinh(pins[1]);_waitus(1);_pinl(pins[1]);_waitus(1);
        }
        bytes[i]=byte;
    }
    OBJ result=newObj(ByteArrayType,(count+3)/4,falseObj);if(!result)return falseObj;
    setByteCountAdjust(result,count);uint8_t *dest=(uint8_t *)&FIELD(result,0);
    for(int i=0;i<count;i++)dest[i]=bytes[i];
    return result;
}
