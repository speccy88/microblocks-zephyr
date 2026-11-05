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
