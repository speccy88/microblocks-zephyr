/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_PERIPHERAL_HOST_TEST
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2Displays.c"
const unsigned char mbFont[1280]={[5*65]=1};
static int lastError,used,hardwareCalls;
static int bytes[1024],dataFlags[1024];
OBJ fail(int error) { lastError=error;return falseObj; }
void invalidatePinModeTracking(int pin) { assert(pin>=8&&pin<=12);hardwareCalls++; }
void _pinclear(int pin) { assert(pin>=8&&pin<=12);hardwareCalls++; }
void _pinl(int pin) { assert(pin>=8&&pin<=12);hardwareCalls++; }
void _pinh(int pin) { assert(pin>=8&&pin<=12);hardwareCalls++; }
void _waitus(int delay) { assert(delay==20||delay==100||delay==1000); }
void testDisplayByte(int data,int value) { assert(used<1024);dataFlags[used]=data;bytes[used++]=value; }
int main(void) {
    OBJ init[]={int2obj(8),int2obj(9),int2obj(10),int2obj(11),int2obj(40)};
    assert(p2SSDInit(5,init)==falseObj && lastError==badPinError && !hardwareCalls);
    init[4]=int2obj(8);assert(p2SSDInit(5,init)==falseObj && !hardwareCalls);
    init[4]=int2obj(12);assert(p2SSDInit(5,init)==trueObj);
    assert(used==37 && bytes[0]==0xae && bytes[1]==0xa0 && bytes[2]==0x72 && bytes[36]==0xaf);
    for(int i=0;i<used;i++) assert(!dataFlags[i]);
    OBJ pixel[]={int2obj(95),int2obj(63),int2obj(0xff0000)};
    used=0;assert(p2SSDPixel(3,pixel)==trueObj && used==8);
    int expected[]={0x15,95,95,0x75,63,63,0xf8,0};
    for(int i=0;i<8;i++) { assert(bytes[i]==expected[i]);assert(dataFlags[i]==(i>=6)); }
    pixel[0]=int2obj(96);used=0;assert(p2SSDPixel(3,pixel)==falseObj && !used);
    OBJ line[]={zeroObj,zeroObj,int2obj(95),int2obj(63),int2obj(0x00ff00)};
    assert(p2SSDLine(5,line)==trueObj && used==8 && bytes[0]==0x21 && bytes[6]==63);
    OBJ rect[]={zeroObj,zeroObj,int2obj(95),int2obj(63),int2obj(255),trueObj};
    used=0;assert(p2SSDRect(6,rect)==trueObj && used==13);
    assert(bytes[0]==0x26 && bytes[1]==1 && bytes[2]==0x22 && bytes[9]==63 && bytes[12]==63);
    rect[5]=zeroObj;used=0;assert(p2SSDRect(6,rect)==falseObj && !used);
    rect[5]=falseObj;rect[2]=int2obj(-1);assert(p2SSDRect(6,rect)==falseObj && !used);
    OBJ glyph[]={int2obj(65),zeroObj,zeroObj,int2obj(0xffffff),zeroObj};
    assert(p2SSDGlyph(5,glyph)==trueObj && used==102);
    assert(bytes[6]==255&&bytes[7]==255&&bytes[8]==0&&bytes[9]==0);
    for(int i=6;i<102;i++) assert(dataFlags[i]);
    glyph[1]=int2obj(91);used=0;assert(p2SSDGlyph(5,glyph)==falseObj&&!used);
    p2DisplayReset();pixel[0]=zeroObj;assert(p2SSDPixel(3,pixel)==falseObj&&!used);
    puts("SSD1331 production command bytes/RGB565/graphics/glyph/bounds/stop PASS; display untested");
    return 0;
}
