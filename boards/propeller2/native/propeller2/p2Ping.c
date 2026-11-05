/* SPDX-License-Identifier: MPL-2.0 */
/* Single-wire PING))) trigger/echo, bounded to 30 ms and released on exit. */
#include <stdint.h>
#include <propeller2.h>
#include "mem.h"
#include "interp.h"
#include "p2Board.h"
extern void invalidatePinModeTracking(int pin);
OBJ p2PING(int argc,OBJ *args) {
    if(argc!=1||!isInt(args[0])) return fail(needsIntegerError);
    int pin=obj2int(args[0]);if(pin<0||pin>P2_LAST_USER_PIN) return fail(badPinError);
    invalidatePinModeTracking(pin);_pinclear(pin);_pinf(pin);_waitus(200);
    _pinl(pin);_waitus(2);_pinh(pin);_waitus(5);_pinl(pin);_pinf(pin);
    uint32_t start=_getus();
    while(!_pinr(pin)) if((uint32_t)(_getus()-start)>=30000) return int2obj(-1);
    uint32_t rise=_getus();
    while(_pinr(pin)) if((uint32_t)(_getus()-start)>=30000) return int2obj(-1);
    uint32_t width=_getus()-rise;
    return int2obj(width>=100&&width<=19000?(int)width:-1);
}
