/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_PERIPHERAL_HOST_TEST
#define P2_EDGE32MB_BOARD
#include "../boards/propeller2/native/propeller2/p2BufferedUART.c"
static int hardwareCalls,lastError;
OBJ fail(int error) { lastError=error;return falseObj; }
void invalidatePinModeTracking(int pin) { assert(pin==8||pin==9);hardwareCalls++; }
void _pinclear(int pin) { assert(pin==8||pin==9);hardwareCalls++; }
void _pinf(int pin) { assert(pin==8||pin==9);hardwareCalls++; }
int main(void) {
    OBJ setup[]={int2obj(8),int2obj(40),int2obj(9600),int2obj(2)};
    assert(p2BufferedOpen(4,setup)==falseObj && lastError==badPinError && !hardwareCalls);
    setup[1]=int2obj(8);assert(p2BufferedOpen(4,setup)==falseObj && !hardwareCalls);
    setup[1]=int2obj(9);setup[3]=int2obj(1);assert(p2BufferedOpen(4,setup)==falseObj && !hardwareCalls);
    setup[3]=int2obj(2);setup[2]=int2obj(1200);assert(p2BufferedOpen(4,setup)==falseObj && !hardwareCalls);
    setup[2]=int2obj(9600);assert(p2BufferedOpen(4,setup)==trueObj);
    assert(obj2int(p2SerialReadByte(0,NULL))==-1);
    for(int round=0;round<4;round++) {
        for(int i=0;i<255;i++) { OBJ byte[]={int2obj(i)};assert(p2SerialWriteByte(1,byte)==trueObj);receiveByte(&uart,255-i); }
        OBJ byte[]={int2obj(99)};assert(p2SerialWriteByte(1,byte)==falseObj);
        assert(obj2int(p2SerialAvailable(0,NULL))==255);
        receiveByte(&uart,99);assert(obj2int(p2SerialDropped(0,NULL))==round+1);
        for(int i=0;i<255;i++) {
            assert(pop(uart.tx,&uart.txWrite,&uart.txRead)==i);
            assert(obj2int(p2SerialReadByte(0,NULL))==255-i);
        }
        assert(obj2int(p2SerialAvailable(0,NULL))==0 && obj2int(p2SerialReadByte(0,NULL))==-1);
    }
    TestObject bytes={ByteArrayType,4,{0}};uint8_t *data=(uint8_t *)bytes.fields;
    data[0]=0;data[1]=255;data[2]=0x80;data[3]=42;
    OBJ argv[]={(OBJ)&bytes,int2obj(2)};assert(obj2int(p2SerialWrite(2,argv))==3);
    assert(pop(uart.tx,&uart.txWrite,&uart.txRead)==255);
    assert(pop(uart.tx,&uart.txWrite,&uart.txRead)==128);
    assert(pop(uart.tx,&uart.txWrite,&uart.txRead)==42);
    TestObject text={StringType,8,{0}};strcpy((char *)text.fields,"abc");
    OBJ stringArgs[]={(OBJ)&text,int2obj(2)};
    assert(obj2int(p2SerialWrite(2,stringArgs))==2);
    assert(pop(uart.tx,&uart.txWrite,&uart.txRead)=='b');
    assert(pop(uart.tx,&uart.txWrite,&uart.txRead)=='c');
    ((char *)text.fields)[0]=0;assert(obj2int(p2SerialWrite(1,stringArgs))==0);
    receiveByte(&uart,0);receiveByte(&uart,255);
    assert(obj2int(p2SerialReadInto(1,argv))==2 && data[0]==0 && data[1]==255);
    int calls=hardwareCalls;p2SerialReleasePin(20);assert(uart.active);
    p2SerialReleasePin(9);assert(!uart.active && calls==hardwareCalls);
    OBJ byte[]={int2obj(2)};assert(p2SerialWriteByte(1,byte)==falseObj);
    assert(obj2int(p2SerialReadByte(0,NULL))==-1);
    assert(p2SerialSetPins(2,setup)==falseObj);OBJ baud[]={int2obj(9600)};
    assert(p2SerialOpen(1,baud)==trueObj);p2SerialClose(0,NULL);assert(!uart.active);
    puts("UART production rings/full duplex wrap/backpressure/drop/bytes/pins/close PASS; wire timing untested");
    return 0;
}
