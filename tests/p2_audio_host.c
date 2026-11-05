/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_PERIPHERAL_HOST_TEST
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2Audio.c"
static int calls,lastError;
OBJ fail(int error) {lastError=error;return falseObj;}
void invalidatePinModeTracking(int pin) {assert(pin==16);calls++;}
void _pinclear(int pin) {assert(pin==16);calls++;}
void _pinf(int pin) {assert(pin==16);calls++;}
int main(void) {
    OBJ init[]={int2obj(40),int2obj(8000),int2obj(3)};assert(p2AudioInit(3,init)==falseObj&&!calls);
    init[0]=int2obj(16);init[1]=int2obj(48000);assert(p2AudioInit(3,init)==falseObj&&!calls);
    init[1]=int2obj(8000);assert(p2AudioInit(3,init)==trueObj);
    OBJ volume[]={int2obj(100)};p2AudioVolume(1,volume);
    TestObject data={ByteArrayType,3,{0}};uint8_t *bytes=(uint8_t *)data.fields;
    bytes[0]=0;bytes[1]=128;bytes[2]=255;
    OBJ pcm[]={(OBJ)&data,int2obj(1),int2obj(8),int2obj(1)};
    assert(obj2int(p2AudioPCM(4,pcm))==3);uint16_t value;
    assert(takeSample(&value)&&value==0);assert(takeSample(&value)&&value==32896);assert(takeSample(&value)&&value==65535);
    data.count=4;bytes[0]=0;bytes[1]=0x80;bytes[2]=0xff;bytes[3]=0x7f;
    pcm[2]=int2obj(16);assert(obj2int(p2AudioPCM(4,pcm))==2);
    assert(takeSample(&value)&&value==0);assert(takeSample(&value)&&value==65535);
    pcm[1]=int2obj(2);assert(obj2int(p2AudioPCM(4,pcm))==1);assert(takeSample(&value)&&value==32767);
    volume[0]=zeroObj;p2AudioVolume(1,volume);assert(obj2int(p2AudioPCM(4,pcm))==1);assert(takeSample(&value)&&value==32768);
    pcm[3]=int2obj(2);assert(p2AudioPCM(4,pcm)==falseObj&&lastError==indexOutOfRangeError);
    for(int i=0;i<1023;i++)assert(queueSample(i));
    assert(!queueSample(9999));assert(obj2int(p2AudioQueued(0,NULL))==1023);
    for(int i=0;i<1023;i++)assert(takeSample(&value));
    assert(!takeSample(&value));
    p2AudioFinish(0,NULL);pcm[3]=int2obj(1);assert(obj2int(p2AudioPCM(4,pcm))==-1);
    p2AudioStop(0,NULL);assert(p2AudioRunning(0,NULL)==falseObj&&obj2int(p2AudioQueued(0,NULL))==0);
    assert(p2AudioInit(3,init)==trueObj&&audio.volume==0);p2AudioReleasePin(16);assert(!audio.active);
    OBJ standard[]={int2obj(16),int2obj(8000)};p2StandardDACInit(2,standard);
    assert(audio.active&&audio.volume==100);OBJ sample[]={int2obj(255)};
    assert(obj2int(p2StandardDACWrite(1,sample))==1&&takeSample(&value)&&value==65535);
    p2AudioReset();assert(p2StandardDACWrite(1,sample)==falseObj&&lastError==primitiveNotImplemented);
    puts("Audio production PCM8/16/stereo/midscale/volume/ring/backpressure/offset/finish/stop/pins PASS; cadence and sound untested");
    return 0;
}
