/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2PeripheralIO.c"
static int calls,activeRow=-1;static unsigned pressed;
OBJ fail(int error) { (void)error;return falseObj; }
void invalidatePinModeTracking(int pin) { assert(pin>=8&&pin<=15);calls++; }
void _pinclear(int pin) { assert(pin>=8&&pin<=15);calls++; }
void _pinf(int pin) { if(pin<12)activeRow=-1;calls++; }
void _wrpin(int pin,uint32_t mode) { assert(pin>=12&&pin<=15&&mode==P_HIGH_15K);calls++; }
void _pinh(int pin) { assert(pin>=12&&pin<=15);calls++; }
void _pinl(int pin) { assert(pin>=8&&pin<=11);activeRow=pin-8;calls++; }
void _waitus(int us) { assert(us==10); }
void _pinw(int pin,int value) { (void)pin;(void)value;assert(0); }
OBJ newObj(int type,int words,OBJ fill) { (void)type;(void)words;(void)fill;return falseObj; }
void setByteCountAdjust(OBJ obj,int count) { (void)obj;(void)count; }
int _pinr(int pin) {
    assert(pin>=12&&pin<=15&&activeRow>=0);
    unsigned rows=1U<<activeRow,cols=0,old;
    do {
        old=(rows<<4)|cols;
        for(int r=0;r<4;r++)for(int c=0;c<4;c++) if(pressed&(1U<<(r*4+c))) {
            if(rows&(1U<<r))cols|=1U<<c;
            if(cols&(1U<<c))rows|=1U<<r;
        }
    }while(old!=((rows<<4)|cols));
    return !(cols&(1U<<(pin-12)));
}
int main(void) {
    TestObject rows={ListType,0,{int2obj(4),int2obj(8),int2obj(9),int2obj(10),int2obj(11)}};
    TestObject cols={ListType,0,{int2obj(4),int2obj(12),int2obj(13),int2obj(14),int2obj(15)}};
    OBJ args[]={(OBJ)&rows,(OBJ)&cols};
    assert(obj2int(p2KeypadScan(0,NULL))==-2);
    cols.fields[4]=int2obj(40);assert(p2KeypadInit(2,args)==falseObj&&!calls);
    cols.fields[4]=int2obj(8);assert(p2KeypadInit(2,args)==falseObj&&!calls);
    cols.fields[4]=int2obj(15);assert(p2KeypadInit(2,args)==trueObj&&!calls);
    for(int i=0;i<16;i++) { pressed=1U<<i;assert(obj2int(p2KeypadScan(0,NULL))==(int)pressed&&activeRow==-1); }
    pressed=0;assert(obj2int(p2KeypadScan(0,NULL))==0);
    pressed=(1U<<0)|(1U<<1)|(1U<<4);assert(obj2int(p2KeypadScan(0,NULL))==-1);
    p2PeripheralIOReset();assert(obj2int(p2KeypadScan(0,NULL))==-2);
    puts("Keypad production 16 keys/ghost graph/reserved pins/inert init/floating rows/stop PASS; matrix untested");
    return 0;
}
