/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2PeripheralIO.c"
static int calls,input,bitIndex,latches,dataLevel;static uint32_t transmitted;
static TestObject result;
OBJ fail(int error) { (void)error;return falseObj; }
OBJ newObj(int type,int words,OBJ fill) { (void)fill;memset(&result,0,sizeof(result));result.type=type;result.count=words*4;return (OBJ)&result; }
void setByteCountAdjust(OBJ obj,int count) { ((TestObject *)obj)->count=count; }
void invalidatePinModeTracking(int pin) { assert(pin>=8&&pin<=10);calls++; }
void _pinclear(int pin) { (void)pin;calls++; }
void _pinf(int pin) { (void)pin;calls++; }
void _wrpin(int pin,uint32_t mode) { (void)pin;(void)mode;assert(0); }
void _pinh(int pin) {
    calls++;
    if(pin==9) { if(input)bitIndex++;else transmitted=(transmitted<<1)|dataLevel; }
    if(pin==10) { latches++;if(input)bitIndex=0; }
}
void _pinl(int pin) { (void)pin;calls++; }
void _pinw(int pin,int value) { assert(pin==8);dataLevel=value;calls++; }
void _waitus(int us) { assert(us==1||us==2); }
int _pinr(int pin) { assert(pin==8&&input);return ((bitIndex/8)%2?0x53:0x96)&(128>>(bitIndex%8))?1:0; }
int main(void) {
    TestObject bytes={ListType,0,{int2obj(2),int2obj(0x96),int2obj(0x53)}};
    OBJ out[]={int2obj(8),int2obj(9),int2obj(10),(OBJ)&bytes,trueObj};
    assert(p2ShiftOut(5,out)==trueObj&&transmitted==0x9653&&latches==1);
    out[4]=falseObj;transmitted=0;latches=0;assert(p2ShiftOut(5,out)==trueObj&&transmitted==0x69ca&&latches==1);
    int saved=calls;out[0]=int2obj(40);assert(p2ShiftOut(5,out)==falseObj&&calls==saved);
    out[0]=int2obj(9);assert(p2ShiftOut(5,out)==falseObj&&calls==saved);
    out[0]=int2obj(8);bytes.fields[1]=int2obj(256);assert(p2ShiftOut(5,out)==falseObj&&calls==saved);
    OBJ in[]={int2obj(8),int2obj(9),int2obj(10),int2obj(2),trueObj};input=1;
    OBJ data=p2ShiftIn(5,in);assert(IS_TYPE(data,ByteArrayType)&&BYTES(data)==2);
    uint8_t *values=(uint8_t *)&FIELD(data,0);assert(values[0]==0x96&&values[1]==0x53);
    in[4]=falseObj;data=p2ShiftIn(5,in);assert(values[0]==0x69&&values[1]==0xca);
    in[3]=int2obj(33);saved=calls;assert(p2ShiftIn(5,in)==falseObj&&calls==saved);
    puts("Shift-register production bit order/latch/binary read/limits/reserved pins PASS; chips untested");
    return 0;
}
