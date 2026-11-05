/* SPDX-License-Identifier: MPL-2.0 */
/* SSD1331 96x64 RGB OLED. Init register values reviewed against Parallax's
   MIT driver, Copyright Parallax Inc. 2016, Matthew Matz. See
   third_party/parallax-peripherals/NOTICE.md. Other code newly written. */
#include <stdint.h>
#include <string.h>
#include <propeller2.h>
#include "mem.h"
#include "interp.h"
#include "p2Board.h"

static int pins[5], active; /* MOSI, SCK, CS, DC, RESET */
extern void invalidatePinModeTracking(int pin);
extern const unsigned char mbFont[];
static void sendByte(int data, int value) {
#ifdef P2_PERIPHERAL_HOST_TEST
    extern void testDisplayByte(int data, int value);
    testDisplayByte(data,value);
#else
    _pinw(pins[3],data); _pinl(pins[2]);
    for(int mask=128;mask;mask>>=1) {
        _pinl(pins[1]); _pinw(pins[0],!!(value&mask)); _pinh(pins[1]);
    }
    _pinl(pins[1]); _pinh(pins[2]);
#endif
}
static void command(const uint8_t *bytes, int count) {
    for(int i=0;i<count;i++) sendByte(0,bytes[i]);
}
static int xy(int x,int y) { return x>=0 && x<96 && y>=0 && y<64; }
static int integers(int count,OBJ *args) {
    for(int i=0;i<count;i++) if(!isInt(args[i])) return 0;
    return 1;
}
static int colorOK(int rgb) { return rgb>=0 && rgb<=0xffffff; }
static void rgb6(uint8_t *out,int rgb) { out[0]=(rgb>>18)&63;out[1]=(rgb>>10)&63;out[2]=(rgb>>2)&63; }
void p2DisplayReset(void) { active=0; }

OBJ p2SSDInit(int argc,OBJ *args) {
    if(argc!=5 || !integers(5,args)) return fail(needsIntegerError);
    for(int i=0;i<5;i++) {
        int pin=obj2int(args[i]);
        if(pin<0 || pin>P2_LAST_USER_PIN) return fail(badPinError);
        for(int j=0;j<i;j++) if(args[i]==args[j]) return fail(badPinError);
    }
    /* All validation precedes any side effect. */
    for(int i=0;i<5;i++) {
        pins[i]=obj2int(args[i]); invalidatePinModeTracking(pins[i]); _pinclear(pins[i]);
    }
    _pinh(pins[2]); _pinl(pins[1]); _pinl(pins[0]); _pinl(pins[3]);
    _pinl(pins[4]); _waitus(20); _pinh(pins[4]); _waitus(1000);
    const uint8_t init[]={0xae,0xa0,0x72,0xa1,0,0xa2,0,0xa4,0xa8,63,
        0xad,0x8e,0xb0,0x0b,0xb1,0x31,0xb3,0xf0,0x8a,0x64,0x8b,0x78,
        0x8c,0x64,0xbb,0x3a,0xbe,0x3e,0x87,6,0x81,0x91,0x82,0x50,0x83,0x7d,0xaf};
    command(init,sizeof(init)); active=1; return trueObj;
}
OBJ p2SSDLine(int argc,OBJ *args) {
    if(argc!=5 || !integers(5,args)) return fail(needsIntegerError);
    int x=obj2int(args[0]),y=obj2int(args[1]),x2=obj2int(args[2]),y2=obj2int(args[3]),rgb=obj2int(args[4]);
    if(!active || !xy(x,y) || !xy(x2,y2) || !colorOK(rgb)) return fail(indexOutOfRangeError);
    uint8_t bytes[]={0x21,x,y,x2,y2,0,0,0};rgb6(bytes+5,rgb);command(bytes,8);
    _waitus(100); return trueObj;
}
OBJ p2SSDRect(int argc,OBJ *args) {
    if(argc!=6 || !integers(5,args)) return fail(needsIntegerError);
    if(args[5]!=trueObj && args[5]!=falseObj) return fail(needsBooleanError);
    int x=obj2int(args[0]),y=obj2int(args[1]),x2=obj2int(args[2]),y2=obj2int(args[3]),rgb=obj2int(args[4]);
    if(!active || !xy(x,y) || !xy(x2,y2) || x2<x || y2<y || !colorOK(rgb)) return fail(indexOutOfRangeError);
    uint8_t fill[]={0x26,args[5]==trueObj?1:0};command(fill,2);
    uint8_t bytes[]={0x22,x,y,x2,y2,0,0,0,0,0,0};
    rgb6(bytes+5,rgb);rgb6(bytes+8,rgb);command(bytes,11);_waitus(1000);return trueObj;
}
static void window(int x,int y,int width,int height) {
    uint8_t bytes[]={0x15,x,x+width-1,0x75,y,y+height-1}; command(bytes,6);
}
static void pixelData(int rgb) {
    int rgb565=((rgb>>8)&0xf800)|((rgb>>5)&0x7e0)|((rgb>>3)&31);
    sendByte(1,rgb565>>8);sendByte(1,rgb565&255);
}
OBJ p2SSDPixel(int argc,OBJ *args) {
    if(argc!=3 || !integers(3,args)) return fail(needsIntegerError);
    int x=obj2int(args[0]),y=obj2int(args[1]),rgb=obj2int(args[2]);
    if(!active || !xy(x,y) || !colorOK(rgb)) return fail(indexOutOfRangeError);
    window(x,y,1,1);pixelData(rgb);return trueObj;
}
/* One glyph per call keeps text output cooperative in the library. */
OBJ p2SSDGlyph(int argc,OBJ *args) {
    if(argc!=5 || !integers(5,args)) return fail(needsIntegerError);
    int ch=obj2int(args[0]),x=obj2int(args[1]),y=obj2int(args[2]),fg=obj2int(args[3]),bg=obj2int(args[4]);
    if(!active || ch<32 || ch>126 || !xy(x,y) || !xy(x+5,y+7) || !colorOK(fg) || !colorOK(bg)) return fail(indexOutOfRangeError);
    window(x,y,6,8);
    for(int row=0;row<8;row++) for(int col=0;col<6;col++) {
        int on=col<5 && (mbFont[5*ch+col]&(1<<row));pixelData(on?fg:bg);
    }
    return trueObj;
}
