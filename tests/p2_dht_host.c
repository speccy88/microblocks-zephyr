/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_PERIPHERAL_HOST_TEST
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2DHT.c"
static uint32_t ticks;
static int stuck,mode;
static uint8_t frame[5];
uint32_t _getus(void) { return ticks++; }
int _pinr(int pin) {
    assert(pin==13);uint32_t time=ticks++;
    if(stuck) return mode;
    if(time<22) return 1;
    time-=22;
    if(time<80) return 0;
    time-=80;
    if(time<80) return 1;
    time-=80;
    for(int i=0;i<40;i++) {
        if(time<50) return 0;
        time-=50;
        int high=frame[i/8]&(128>>(i%8))?70:27;
        if(time<(uint32_t)high) return 1;
        time-=high;
    }
    return 0;
}
static void makeFrame(int humidity,int temperature) {
    frame[0]=humidity>>8;frame[1]=humidity;
    int raw=temperature<0?(-temperature)|0x8000:temperature;
    frame[2]=raw>>8;frame[3]=raw;frame[4]=frame[0]+frame[1]+frame[2]+frame[3];
}
int main(void) {
    uint8_t bytes[5];int temperature,humidity;
    makeFrame(653,234);assert(decode(frame,&temperature,&humidity)&&temperature==234&&humidity==653);
    ticks=0;assert(readFrame(13,bytes)&&!memcmp(bytes,frame,5));
    makeFrame(1000,-123);ticks=0;assert(readFrame(13,bytes)&&decode(bytes,&temperature,&humidity)&&temperature==-123&&humidity==1000);
    frame[4]^=1;assert(!decode(frame,&temperature,&humidity));
    makeFrame(1001,100);assert(!decode(frame,&temperature,&humidity));
    makeFrame(300,-401);assert(!decode(frame,&temperature,&humidity));
    for(mode=0;mode<=1;mode++) { stuck=1;ticks=0;assert(!readFrame(13,bytes)&&ticks<500); }
    puts("DHT22 production pulse parser/negative temperature/checksum/ranges/stuck-line timeout PASS; real sensor untested");
    return 0;
}
