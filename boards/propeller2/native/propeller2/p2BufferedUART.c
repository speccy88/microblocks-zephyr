/* SPDX-License-Identifier: MPL-2.0 */
/* One explicit 8N1 UART, independent of the IDE. Worker owns GPIO; each
   heap-free ring has one producer and one consumer with ordered publication. */
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
#define UART_RING 256U
#define UART_MASK (UART_RING-1U)
typedef struct {
    volatile uint8_t rx[UART_RING],tx[UART_RING];
    volatile uint32_t rxRead,rxWrite,txRead,txWrite,dropped,active;
    int rxPin,txPin,cog,baud;
} BufferedUART;
static BufferedUART uart;
static int configuredRX=-1,configuredTX=-1;
extern void invalidatePinModeTracking(int pin);
static int pinOK(int pin) { return pin>=0 && pin<=P2_LAST_USER_PIN; }
static int push(volatile uint8_t *ring,volatile uint32_t *head,volatile uint32_t *tail,int byte) {
    uint32_t at=*head,next=(at+1U)&UART_MASK;
    if(next==*tail) return 0;
    ring[at]=byte;*head=next;return 1;
}
static int pop(volatile uint8_t *ring,volatile uint32_t *head,volatile uint32_t *tail) {
    uint32_t at=*tail;if(at==*head) return -1;
    int byte=ring[at];*tail=(at+1U)&UART_MASK;return byte;
}
static void receiveByte(BufferedUART *s,int value) {
    if(!push(s->rx,&s->rxWrite,&s->rxRead,value)) s->dropped++;
}
#ifndef P2_PERIPHERAL_HOST_TEST
static int txBusy(int pin) {
    uint32_t value;__asm { rqpin value, pin wc; muxc value, #1; }
    return value&1;
}
static void serialJob(void *argument,volatile int *stop) {
    BufferedUART *s=argument;
    uint32_t x=(_clockfreq()/s->baud<<16)|7;
    _pinclear(s->rxPin);_pinclear(s->txPin);
    _wrpin(s->rxPin,P_ASYNC_RX|P_SCHMITT_A);_wxpin(s->rxPin,x);
    _wrpin(s->txPin,P_ASYNC_TX|P_OE);_wxpin(s->txPin,x);
    /* Enable without WYPIN, which would transmit an unwanted initial byte. */
    if(s->rxPin<32) _DIRA|=1U<<s->rxPin;else _DIRB|=1U<<(s->rxPin-32);
    if(s->txPin<32) _DIRA|=1U<<s->txPin;else _DIRB|=1U<<(s->txPin-32);
    s->active=1;
    while(!*stop) {
        if(_pinr(s->rxPin)) {
            int value=(_rdpin(s->rxPin)>>24)&255;
            receiveByte(s,value);
        }
        if(s->txRead!=s->txWrite && (_pinr(s->txPin)||!txBusy(s->txPin)))
            _wypin(s->txPin,pop(s->tx,&s->txWrite,&s->txRead));
        _waitx(64);
    }
    _pinclear(s->rxPin);_pinf(s->rxPin);_pinclear(s->txPin);_pinf(s->txPin);
    s->active=0;
}
#endif
void p2SerialReset(void) {
#ifndef P2_PERIPHERAL_HOST_TEST
    if(uart.active) p2NativeStop(uart.cog);
#endif
    uart.active=0;
}
void p2SerialReleasePin(int pin) {
    if(uart.active && (pin==uart.rxPin||pin==uart.txPin)) p2SerialReset();
}
static OBJ startUART(int rx,int tx,int baud,int cog) {
    if(!pinOK(rx)||!pinOK(tx)||rx==tx) return fail(badPinError);
    if(baud<3000||baud>115200||cog<2||cog>7) return falseObj;
#ifndef P2_PERIPHERAL_HOST_TEST
    if(p2IsWorker()||(!(uart.active&&uart.cog==cog)&&!p2NativeCanStart(cog))) return falseObj;
#endif
    p2SerialReset();invalidatePinModeTracking(rx);invalidatePinModeTracking(tx);
    _pinclear(rx);_pinf(rx);_pinclear(tx);_pinf(tx);
    memset(&uart,0,sizeof(uart));uart.rxPin=rx;uart.txPin=tx;uart.cog=cog;uart.baud=baud;
#ifdef P2_PERIPHERAL_HOST_TEST
    uart.active=1;return trueObj;
#else
    return p2NativeStart(cog,serialJob,&uart)?trueObj:falseObj;
#endif
}
OBJ p2BufferedOpen(int argc,OBJ *args) {
    if(argc!=4) return fail(notEnoughArguments);
    for(int i=0;i<4;i++) if(!isInt(args[i])) return fail(needsIntegerError);
    return startUART(obj2int(args[0]),obj2int(args[1]),obj2int(args[2]),obj2int(args[3]));
}
OBJ p2SerialSetPins(int argc,OBJ *args) {
    if(argc!=2||!isInt(args[0])||!isInt(args[1])) return fail(needsIntegerError);
    int rx=obj2int(args[0]),tx=obj2int(args[1]);
    if(!pinOK(rx)||!pinOK(tx)||rx==tx) return fail(badPinError);
    p2SerialReset();configuredRX=rx;configuredTX=tx;return falseObj;
}
OBJ p2SerialOpen(int argc,OBJ *args) {
    if(argc!=1||!isInt(args[0])) return fail(needsIntegerError);
    for(int cog=2;cog<8;cog++) {
#ifndef P2_PERIPHERAL_HOST_TEST
        if(!p2NativeCanStart(cog)) continue;
#endif
        return startUART(configuredRX,configuredTX,obj2int(args[0]),cog);
    }
    return falseObj;
}
OBJ p2SerialClose(int argc,OBJ *args) { (void)argc;(void)args;p2SerialReset();return falseObj; }
OBJ p2SerialAvailable(int argc,OBJ *args) {
    (void)argc;(void)args;return int2obj(uart.active?((uart.rxWrite-uart.rxRead)&UART_MASK):0);
}
OBJ p2SerialDropped(int argc,OBJ *args) { (void)argc;(void)args;return int2obj(uart.dropped&0x3fffffff); }
OBJ p2SerialReadByte(int argc,OBJ *args) {
    (void)argc;(void)args;return int2obj(uart.active?pop(uart.rx,&uart.rxWrite,&uart.rxRead):-1);
}
OBJ p2SerialWriteByte(int argc,OBJ *args) {
    if(argc!=1||!isInt(args[0])) return fail(needsIntegerError);
    int byte=obj2int(args[0]);if(byte<0||byte>255) return fail(byteOutOfRange);
    return uart.active && push(uart.tx,&uart.txWrite,&uart.txRead,byte)?trueObj:falseObj;
}
OBJ p2SerialWrite(int argc,OBJ *args) {
    if(argc<1) return fail(notEnoughArguments);
    if(isInt(args[0])) return int2obj(p2SerialWriteByte(1,args)==trueObj?1:0);
    if(!IS_TYPE(args[0],ByteArrayType)&&!IS_TYPE(args[0],StringType)) return fail(needsByteArray);
    uint8_t *bytes=(uint8_t *)&FIELD(args[0],0);
    int count=IS_TYPE(args[0],StringType)?strlen((char *)bytes):BYTES(args[0]);
    int start=argc>1&&isInt(args[1])?obj2int(args[1])-1:0;
    if(start<0||start>count) return fail(indexOutOfRangeError);
    int written=0;
    while(uart.active&&start+written<count&&push(uart.tx,&uart.txWrite,&uart.txRead,bytes[start+written])) written++;
    return int2obj(written);
}
OBJ p2SerialReadInto(int argc,OBJ *args) {
    if(argc!=1||!IS_TYPE(args[0],ByteArrayType)) return fail(needsByteArray);
    uint8_t *bytes=(uint8_t *)&FIELD(args[0],0);int count=0;
    while(uart.active&&count<BYTES(args[0])) {
        int byte=pop(uart.rx,&uart.rxWrite,&uart.rxRead);if(byte<0) break;bytes[count++]=byte;
    }
    return int2obj(count);
}
#ifndef P2_PERIPHERAL_HOST_TEST
OBJ p2SerialRead(int argc,OBJ *args) {
    (void)argc;(void)args;int count=obj2int(p2SerialAvailable(0,NULL));
    OBJ result=newObj(ByteArrayType,(count+3)/4,zeroObj);
    if(!result) return falseObj;
    setByteCountAdjust(result,count);OBJ argv[]={result};p2SerialReadInto(1,argv);return result;
}
#endif
