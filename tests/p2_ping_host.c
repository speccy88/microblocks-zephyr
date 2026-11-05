/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2Ping.c"
static uint32_t ticks,releaseTime;static int calls,mode=2,width=5800,released;
OBJ fail(int error) { (void)error;return falseObj; }
void invalidatePinModeTracking(int pin) { assert(pin==16);calls++; }
void _pinclear(int pin) { assert(pin==16);calls++; }
void _pinl(int pin) { assert(pin==16);released=0;calls++; }
void _pinh(int pin) { assert(pin==16);calls++; }
void _pinf(int pin) { assert(pin==16);released=1;releaseTime=ticks;calls++; }
void _waitus(int us) { assert(us==2||us==5||us==200);ticks+=us; }
uint32_t _getus(void) { return ticks++; }
int _pinr(int pin) {
    assert(pin==16&&released);uint32_t elapsed=ticks++-releaseTime;
    if(mode<2)return mode;
    return elapsed>=500&&elapsed<(uint32_t)(500+width);
}
int main(void) {
    OBJ args[]={int2obj(40)};assert(p2PING(1,args)==falseObj&&!calls);
    args[0]=int2obj(16);int measured=obj2int(p2PING(1,args));assert(measured>=5795&&measured<=5805&&released);
    width=20;ticks=0;assert(obj2int(p2PING(1,args))==-1);
    for(mode=0;mode<2;mode++){ticks=0;assert(obj2int(p2PING(1,args))==-1&&ticks<30300&&released);}
    puts("PING production echo/short-pulse/stuck-low/stuck-high/reserved pin/released line PASS; distance untested");
    return 0;
}
