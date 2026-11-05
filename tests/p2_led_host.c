/* SPDX-License-Identifier: MIT */
/* Execute actual production buffer, scaling, validation and GRB conversion. */
#include <assert.h>
#include <stdio.h>
#define P2_PERIPHERAL_HOST_TEST
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2LEDs.c"
static int lastError, writes, hardwareCalls;
static uint32_t sent[128];
OBJ fail(int error) { lastError = error; return falseObj; }
void invalidatePinModeTracking(int pin) { assert(pin == 8); hardwareCalls++; }
void _pinclear(int pin) { assert(pin == 8); hardwareCalls++; }
void _pinl(int pin) { assert(pin == 8); hardwareCalls++; }
void _waitus(int delay) { assert(delay == 300); hardwareCalls++; }
void testLEDWord(int pin, uint32_t value) { assert(pin == 8); sent[writes++] = value; }
int main(void) {
    OBJ init[] = {int2obj(8),int2obj(2)};
    assert(p2LEDInit(2,init)==trueObj && !hardwareCalls);
    OBJ set[] = {int2obj(1),int2obj(0x123456)};
    assert(p2LEDSet(2,set)==trueObj && !hardwareCalls);
    assert(p2LEDUpdate(0,NULL)==trueObj && writes==2);
    assert(sent[0]==0x34125600U && sent[1]==0);
    OBJ bright[] = {int2obj(128)};
    assert(p2LEDBrightness(1,bright)==trueObj);
    writes=0; p2LEDUpdate(0,NULL); assert(sent[0]==0x1a092b00U);
    bright[0]=int2obj(255); p2LEDBrightness(1,bright);
    writes=0; p2LEDUpdate(0,NULL); assert(sent[0]==0x34125600U);
    OBJ fill[]={int2obj(0xaabbcc)}; p2LEDFill(1,fill);
    writes=0; p2LEDUpdate(0,NULL); assert(sent[0]==0xbbaacc00U && sent[1]==sent[0]);
    int calls=hardwareCalls;
    for (int pin=40; pin<64; pin++) { init[0]=int2obj(pin); assert(p2LEDInit(2,init)==falseObj && lastError==badPinError); }
    init[0]=int2obj(-1); assert(p2LEDInit(2,init)==falseObj);
    init[0]=int2obj(8); init[1]=int2obj(129); assert(p2LEDInit(2,init)==falseObj);
    init[1]=zeroObj; assert(p2LEDInit(2,init)==falseObj);
    set[0]=zeroObj; assert(p2LEDSet(2,set)==falseObj);
    set[0]=int2obj(3); assert(p2LEDSet(2,set)==falseObj);
    set[0]=int2obj(1);set[1]=int2obj(-1);assert(p2LEDSet(2,set)==falseObj);
    bright[0]=int2obj(256);assert(p2LEDBrightness(1,bright)==falseObj);
    OBJ pin[]={int2obj(8),trueObj}; assert(p2NeoPixelSetPin(2,pin)==falseObj && lastError==primitiveNotImplemented);
    assert(hardwareCalls==calls);
    TestObject list={ListType,0,{int2obj(2),int2obj(0xff0000),int2obj(0x0000ff)}};
    OBJ data[]={(OBJ)&list}; writes=0;
    assert(p2NeoPixelSend(1,data)==trueObj && sent[0]==0x00ff0000U && sent[1]==0x0000ff00U);
    list.fields[2]=falseObj;calls=hardwareCalls;assert(p2NeoPixelSend(1,data)==falseObj && hardwareCalls==calls);
    p2LEDReset();assert(p2LEDUpdate(0,NULL)==falseObj && hardwareCalls==calls);
    puts("WS2812 production buffer/GRB/brightness/bounds/reset/shared API PASS; waveform not tested");
    return 0;
}
