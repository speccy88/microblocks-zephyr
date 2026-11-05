/* SPDX-License-Identifier: MPL-2.0 */
/* Heap-free DAC consumer on a reserved worker; main cog alone queues PCM. */
#include <stdint.h>
#include <string.h>
#include <propeller2.h>
#include <smartpins.h>
#include "mem.h"
#include "interp.h"
#include "p2Board.h"
#ifndef P2_PERIPHERAL_HOST_TEST
#include "p2Cogs.h"
#endif
#define AUDIO_MASK 1023U
typedef struct {
    volatile uint16_t data[1024];
    volatile uint32_t head,tail,active,finish,played,underruns,late,volume;
    int pin,cog,rate;
} Audio;
static Audio audio;
static uint32_t configuredVolume=25;
extern void invalidatePinModeTracking(int pin);
static int queueSample(uint16_t value) {
    uint32_t at=audio.head,next=(at+1U)&AUDIO_MASK;
    if(next==audio.tail)return 0;
    audio.data[at]=value;audio.head=next;return 1;
}
static int takeSample(uint16_t *value) {
    uint32_t at=audio.tail;if(at==audio.head)return 0;
    int sample=audio.data[at];audio.tail=(at+1U)&AUDIO_MASK;
    *value=32768+((sample-32768)*(int)audio.volume)/100;
    audio.played++;return 1;
}
#ifndef P2_PERIPHERAL_HOST_TEST
static void audioJob(void *argument,volatile int *stop) {
    Audio *s=argument;uint32_t period=_clockfreq()/s->rate,next=0;int started=0;
    _pinclear(s->pin);_wrpin(s->pin,P_DAC_990R_3V|P_DAC_DITHER_RND|P_OE);
    _wxpin(s->pin,256);_wypin(s->pin,32768);
    if(s->pin<32)_DIRA|=1U<<s->pin;else _DIRB|=1U<<(s->pin-32);
    while(!*stop) {
        if(!started&&s->head==s->tail) { if(s->finish)break;_waitx(64);continue; }
        if(!started) {next=_cnt();started=1;}
        uint16_t value;
        if(takeSample(&value))_wypin(s->pin,value);
        else {if(s->finish)break;s->underruns++;_wypin(s->pin,32768);}
        next+=period;
        while((int32_t)(_cnt()-next)<0&&!*stop)_waitx(64);
        if((int32_t)(_cnt()-next)>(int32_t)period) {s->late++;next=_cnt();}
    }
    _pinclear(s->pin);_pinf(s->pin);s->active=0;
}
#endif
void p2AudioReset(void) {
#ifndef P2_PERIPHERAL_HOST_TEST
    if(audio.active)p2NativeStop(audio.cog);
#endif
    audio.active=0;
    audio.tail=audio.head;
}
void p2AudioReleasePin(int pin) {if(audio.active&&pin==audio.pin)p2AudioReset();}
static OBJ startAudio(int pin,int rate,int cog) {
    if(pin<0||pin>P2_LAST_USER_PIN)return fail(badPinError);
    if(rate<8000||rate>22050||cog<2||cog>7)return falseObj;
#ifndef P2_PERIPHERAL_HOST_TEST
    if(p2IsWorker()||(!(audio.active&&audio.cog==cog)&&!p2NativeCanStart(cog)))return falseObj;
#endif
    p2AudioReset();invalidatePinModeTracking(pin);_pinclear(pin);_pinf(pin);
    memset(&audio,0,sizeof(audio));audio.pin=pin;audio.rate=rate;audio.cog=cog;audio.volume=configuredVolume;audio.active=1;
#ifndef P2_PERIPHERAL_HOST_TEST
    if(!p2NativeStart(cog,audioJob,&audio)) {audio.active=0;return falseObj;}
#endif
    return trueObj;
}
OBJ p2AudioInit(int argc,OBJ *args) {
    if(argc!=3)return fail(notEnoughArguments);
    for(int i=0;i<3;i++)if(!isInt(args[i]))return fail(needsIntegerError);
    return startAudio(obj2int(args[0]),obj2int(args[1]),obj2int(args[2]));
}
static int pcmValue(const uint8_t *bytes,int bits) {
    if(bits==8)return bytes[0]*257;
    int value=bytes[0]|(bytes[1]<<8);if(value>=32768)value-=65536;return value+32768;
}
OBJ p2AudioPCM(int argc,OBJ *args) {
    if(argc!=4||!IS_TYPE(args[0],ByteArrayType))return fail(needsByteArray);
    for(int i=1;i<4;i++)if(!isInt(args[i]))return fail(needsIntegerError);
    int channels=obj2int(args[1]),bits=obj2int(args[2]),start=obj2int(args[3])-1;
    if((channels!=1&&channels!=2)||(bits!=8&&bits!=16))return fail(indexOutOfRangeError);
    int stride=channels*(bits/8),count=BYTES(args[0]);
    if(start<0||start>count||start%stride||(count-start)%stride)return fail(indexOutOfRangeError);
    if(!audio.active||audio.finish)return int2obj(-1);
    uint8_t *bytes=(uint8_t *)&FIELD(args[0],0);int accepted=0;
    while(start<count) {
        int value=pcmValue(bytes+start,bits);
        if(channels==2)value=(value+pcmValue(bytes+start+bits/8,bits))/2;
        if(!queueSample(value))break;
        accepted++;start+=stride;
    }
    return int2obj(accepted);
}
OBJ p2AudioVolume(int argc,OBJ *args) {
    if(argc!=1||!isInt(args[0]))return fail(needsIntegerError);
    int value=obj2int(args[0]);if(value<0||value>100)return fail(indexOutOfRangeError);
    configuredVolume=value;audio.volume=value;return trueObj;
}
OBJ p2AudioFinish(int argc,OBJ *args) { (void)argc;(void)args;audio.finish=1;return trueObj; }
OBJ p2AudioStop(int argc,OBJ *args) { (void)argc;(void)args;p2AudioReset();return falseObj; }
OBJ p2AudioRunning(int argc,OBJ *args) { (void)argc;(void)args;return audio.active?trueObj:falseObj; }
OBJ p2AudioQueued(int argc,OBJ *args) { (void)argc;(void)args;return int2obj((audio.head-audio.tail)&AUDIO_MASK); }
OBJ p2AudioUnderruns(int argc,OBJ *args) { (void)argc;(void)args;return int2obj(audio.underruns&0x3fffffff); }
OBJ p2AudioLate(int argc,OBJ *args) { (void)argc;(void)args;return int2obj(audio.late&0x3fffffff); }
OBJ p2StandardDACInit(int argc,OBJ *args) {
    if(argc!=2||!isInt(args[0])||!isInt(args[1]))return fail(needsIntegerError);
    int pin=obj2int(args[0]),rate=obj2int(args[1]);
    if(pin<0||pin>P2_LAST_USER_PIN)return fail(badPinError);
    if(rate<8000||rate>22050)return fail(indexOutOfRangeError);
    for(int cog=2;cog<8;cog++) {
#ifndef P2_PERIPHERAL_HOST_TEST
        if(!(audio.active&&audio.cog==cog)&&!p2NativeCanStart(cog))continue;
#endif
        if(startAudio(pin,rate,cog)==trueObj) {audio.volume=100;return falseObj;}
        break;
    }
    return fail(primitiveNotImplemented);
}
OBJ p2StandardDACWrite(int argc,OBJ *args) {
    if(argc!=1||!isInt(args[0]))return fail(needsIntegerError);
    int sample=obj2int(args[0]);if(sample<0||sample>255)return fail(byteOutOfRange);
    if(!audio.active||audio.finish)return fail(primitiveNotImplemented);
    return int2obj(queueSample(sample*257));
}
