/* SPDX-License-Identifier: MPL-2.0 */
/* Heap-free native producer; only the main cog creates or returns VM objects. */
#include <stdint.h>
#include <string.h>
#include <propeller2.h>
#include <smartpins.h>
#include "interp.h"
#include "p2Board.h"
#include "p2Capture.h"

#define CAPACITY 1024U
#define DMA_PAGE_WORDS 128U
#define DMA_GUARD 0x51c0ffeeU
enum { IDLE, RUNNING, COMPLETE, CANCELED, OVERFLOW, TIMEOUT, TIMING, ARMED };
typedef struct {
    volatile uint32_t ownsCog, state, head, tail, rawCount, emitted;
    volatile uint32_t maxGap, elapsed, expected, wraps, startupSkipped;
    int pin, cog, observedCog, localDIR, order, period, external, trigger, streaming;
    uint32_t channels;
    uint32_t keep, limit, timeout, scale;
    uint32_t record, prePages, postPages, triggerLevel, discarded;
    int triggerWord;
    uint32_t guardBefore, data[CAPACITY], guardAfter;
} Capture;
static Capture capture;

int p2CaptureOwnsPin(int pin) {
    if (!capture.ownsCog) return 0;
    if (capture.order==4 && capture.record && capture.trigger==pin) return 1;
    if (capture.order!=1) return capture.pin==pin;
    return pin>=capture.pin && pin<capture.pin+4 && (capture.channels & (1U<<(pin-capture.pin)));
}
static void stopCapture(void) {
    if (capture.ownsCog) p2NativeStop(capture.cog);
}
void p2CaptureReleasePin(int pin) { if (p2CaptureOwnsPin(pin)) stopCapture(); }

static void dmaJob(void *argument, volatile int *stop) {
    Capture *s=argument;
    uint32_t command=0xc080ffffU|((uint32_t)s->pin<<17),frequency=0x80000000U>>s->period;
    uint32_t base=(uint32_t)s->data,nextAddress=base+512,stopAddress=(uint32_t)stop;
    uint32_t head=0,tail=0,available=0,emitted=0,pages=0,limit=s->limit,ringMask=1023;
    uint32_t now=0,last=0,first=0,haveFirst=0,gap=0,maximum=0,temp=0,status=COMPLETE;
    uint32_t pageClocks=4096U<<s->period,gapLimit=pageClocks+512U,timeout=pageClocks*2U+180000U;
    uint32_t headAddress=(uint32_t)&s->head,tailAddress=(uint32_t)&s->tail,countAddress=(uint32_t)&s->emitted;
    uint32_t gapAddress=(uint32_t)&s->maxGap,wrapAddress=(uint32_t)&s->wraps,wraps=0;
    uint32_t record=s->record,armed=record,pre=s->prePages,preWords=pre*128U,post=s->postPages;
    uint32_t trigger=s->trigger,level=s->triggerLevel,start=0,recordTimeout=s->timeout,discarded=0;
    uint32_t stateAddress=(uint32_t)&s->state,triggerAddress=(uint32_t)&s->triggerWord,discardAddress=(uint32_t)&s->discarded;
    /* WRFAST owns the cog FIFO: no HUB execution or C calls until XSTOP and
       FIFO drain. Two free pages cover the active page and the next FBLOCK. */
    __asm volatile {
        wrfast #8, base
        fblock #8, nextAddress
        setxfrq frequency
        getct last
        mov start, last
        xinit command, #0
capture_dma_wait
        rdlong temp, stopAddress
        tjnz temp, #capture_dma_cancel
        pollfbw wc
 if_c   jmp #capture_dma_page
        getct now
        tjz armed, #capture_dma_clock_check
        mov temp, now
        sub temp, start
        cmp temp, recordTimeout wc
 if_ae  jmp #capture_dma_timeout
capture_dma_clock_check
        sub now, last
        cmp now, timeout wc
 if_b   jmp #capture_dma_wait
        jmp #capture_dma_timeout
capture_dma_page
        getct now
        tjnz haveFirst, #capture_dma_gap
        mov first, now
        mov haveFirst, #1
        jmp #capture_dma_publish
capture_dma_gap
        mov gap, now
        sub gap, last
        cmp gap, maximum wc
 if_ae  mov maximum, gap
        cmp gap, gapLimit wc
 if_ae  jmp #capture_dma_late
capture_dma_publish
        mov last, now
        add head, #128
        and head, ringMask wz
 if_z   add wraps, #1
        add emitted, #128
        add pages, #1
        wrlong head, headAddress
        wrlong emitted, countAddress
        wrlong maximum, gapAddress
        wrlong wraps, wrapAddress
        tjz record, #capture_dma_finite
        tjz armed, #capture_dma_post
        mov temp, pages
        cmp temp, pre wc
 if_ae  mov temp, pre
        shl temp, #7
        mov tail, head
        sub tail, temp
        and tail, ringMask
        wrlong tail, tailAddress
        cmp pages, pre wcz
 if_b   jmp #capture_dma_space
 if_a   add discarded, #128
        wrlong discarded, discardAddress
        testp trigger wc
        mov temp, #0
        muxc temp, #1
        cmp temp, level wz
 if_nz  jmp #capture_dma_space
        mov armed, #0
        wrlong preWords, triggerAddress
        mov temp, #1
        wrlong temp, stateAddress
        jmp #capture_dma_space
capture_dma_post
        djnz post, #capture_dma_space
        jmp #capture_dma_done
capture_dma_finite
        tjz limit, #capture_dma_space
        cmp pages, limit wc
 if_ae  jmp #capture_dma_done
capture_dma_space
        rdlong tail, tailAddress
        mov available, tail
        sub available, head
        sub available, #1
        and available, ringMask
        cmp available, #256 wc
 if_b   jmp #capture_dma_full
        mov nextAddress, head
        add nextAddress, #128
        and nextAddress, ringMask
        shl nextAddress, #2
        add nextAddress, base
        fblock #8, nextAddress
        jmp #capture_dma_wait
capture_dma_full
        mov status, #4
        jmp #capture_dma_done
capture_dma_late
        mov status, #6
        jmp #capture_dma_done
capture_dma_cancel
        mov status, #3
        jmp #capture_dma_done
capture_dma_timeout
        mov status, #5
capture_dma_done
        xstop
        waitx #20
    }
    s->rawCount=emitted;s->emitted=emitted;s->maxGap=maximum;s->wraps=wraps;
    s->elapsed=pages ? last-first : 0;s->expected=pages ? (pages-1U)*pageClocks : 0;
    s->state=status;
}

static void sincJob(void *argument, volatile int *stop) {
    Capture *s = argument;
    uint32_t pin=s->pin, order=s->order, period=s->period, timeout=s->timeout;
    uint32_t keep=s->keep, phase=keep, limit=s->limit, warm=order==2 ? 3 : 5;
    uint32_t head=0, next=0, tail=0, address=0, sample=0, raw=0, previous=0, difference=0, ringMask=1023;
    uint32_t samples=0, emitted=0, wraps=0, temp=0, now=0, last=_cnt(), gap=0, maximum=0;
    uint32_t gapLimit=s->external ? 0 : period+128U, status=COMPLETE;
    uint32_t stopAddress=(uint32_t)stop, headAddress=(uint32_t)&s->head;
    uint32_t tailAddress=(uint32_t)&s->tail, dataAddress=(uint32_t)s->data;
    uint32_t rawAddress=(uint32_t)&s->rawCount, emittedAddress=(uint32_t)&s->emitted;
    uint32_t gapAddress=(uint32_t)&s->maxGap, wrapAddress=(uint32_t)&s->wraps;
    /* This loop is explicitly cached in cog RAM, never interrupted by VM GC.
       The supported internal periods leave a conservative service margin. */
    __asm volatile {
capture_sinc_wait
        rdlong temp, stopAddress
        tjnz temp, #capture_sinc_cancel
        testp pin wc
 if_nc  jmp #capture_sinc_idle
        rdpin raw, pin
        zerox raw, #26
        getct now
        mov gap, now
        sub gap, last
        mov last, now
        tjz samples, #capture_sinc_difference
        cmp gap, maximum wc
 if_ae  mov maximum, gap
        tjz gapLimit, #capture_sinc_difference
        cmp gap, gapLimit wc
 if_ae  jmp #capture_sinc_late
capture_sinc_difference
        add samples, #1
        cmp raw, previous wc
 if_b   add wraps, #1
        mov sample, raw
        sub sample, previous
        mov previous, raw
        zerox sample, #26
        cmp order, #3 wz
 if_nz  jmp #capture_sinc_warmup
        mov temp, sample
        sub sample, difference
        mov difference, temp
        zerox sample, #26
capture_sinc_warmup
        tjz warm, #capture_sinc_decimate
        sub warm, #1
        jmp #capture_sinc_wait
capture_sinc_decimate
        djnz phase, #capture_sinc_wait
        mov phase, keep
        mov next, head
        add next, #1
        and next, ringMask
        rdlong tail, tailAddress
        cmp next, tail wz
 if_z   jmp #capture_sinc_full
        mov address, head
        shl address, #2
        add address, dataAddress
        wrlong sample, address
        mov head, next
        wrlong head, headAddress
        add emitted, #1
        wrlong samples, rawAddress
        wrlong emitted, emittedAddress
        wrlong maximum, gapAddress
        wrlong wraps, wrapAddress
        tjz limit, #capture_sinc_wait
        cmp emitted, limit wc
 if_b   jmp #capture_sinc_wait
        jmp #capture_sinc_done
capture_sinc_idle
        getct now
        sub now, last
        cmp now, timeout wc
 if_b   jmp #capture_sinc_wait
        mov status, #5
        jmp #capture_sinc_done
capture_sinc_full
        mov status, #4
        jmp #capture_sinc_done
capture_sinc_late
        mov status, #6
        jmp #capture_sinc_done
capture_sinc_cancel
        mov status, #3
capture_sinc_done
    }
    s->rawCount=samples; s->emitted=emitted; s->maxGap=maximum; s->wraps=wraps;
    s->state=status;
}

static void bitsStreamJob(void *argument, volatile int *stop) {
    Capture *s=argument;
    uint32_t pin=s->pin,timeout=s->timeout,stopAddress=(uint32_t)stop;
    uint32_t head=0,next=0,tail=0,sample=0,address=0,emitted=0,temp=0,ringMask=1023;
    uint32_t now=0,last=_cnt(),first=0,haveFirst=0,gap=0,maximum=0,status=COMPLETE;
    uint32_t headAddress=(uint32_t)&s->head,tailAddress=(uint32_t)&s->tail,dataAddress=(uint32_t)s->data;
    uint32_t countAddress=(uint32_t)&s->emitted,rawAddress=(uint32_t)&s->rawCount,gapAddress=(uint32_t)&s->maxGap;
    uint32_t warm=1,warmAddress=(uint32_t)&s->startupSkipped;
    /* External clock <=1 MHz: 32 clocks per result leaves time for ring
       bookkeeping. This does not use the internal full-clock finite path. */
    __asm volatile {
        rdpin sample, pin
capture_bitstream_wait
        rdlong temp, stopAddress
        tjnz temp, #capture_bitstream_cancel
        testp pin wc
 if_nc  jmp #capture_bitstream_idle
        tjnz warm, #capture_bitstream_warm
        mov next, head
        add next, #1
        and next, ringMask
        rdlong tail, tailAddress
        cmp next, tail wz
 if_z   jmp #capture_bitstream_full
        rdpin sample, pin
        getct now
        tjnz haveFirst, #capture_bitstream_gap
        mov first, now
        mov haveFirst, #1
        jmp #capture_bitstream_store
capture_bitstream_gap
        mov gap, now
        sub gap, last
        cmp gap, maximum wc
 if_ae  mov maximum, gap
capture_bitstream_store
        mov last, now
        mov address, head
        shl address, #2
        add address, dataAddress
        wrlong sample, address
        mov head, next
        wrlong head, headAddress
        add emitted, #1
        wrlong emitted, countAddress
        wrlong emitted, rawAddress
        wrlong maximum, gapAddress
        jmp #capture_bitstream_wait
capture_bitstream_warm
        rdpin sample, pin
        mov warm, #0
        mov temp, #1
        wrlong temp, warmAddress
        getct last
        jmp #capture_bitstream_wait
capture_bitstream_idle
        getct now
        sub now, last
        cmp now, timeout wc
 if_b   jmp #capture_bitstream_wait
        mov status, #5
        jmp #capture_bitstream_done
capture_bitstream_full
        mov status, #4
        jmp #capture_bitstream_done
capture_bitstream_cancel
        mov status, #3
capture_bitstream_done
    }
    s->rawCount=emitted;s->emitted=emitted;s->maxGap=maximum;
    s->elapsed=emitted ? last-first : 0;s->state=status;
}

static void bitsJob(void *argument, volatile int *stop) {
    Capture *s=argument;
    uint32_t pin=s->pin, remaining=s->limit, address=(uint32_t)s->data, value=0;
    uint32_t start=_cnt(), first=0, last=0, now=0, temp=0, timeout=s->timeout, polls=64, haveFirst=0;
    uint32_t stopAddress=(uint32_t)stop, status=COMPLETE;
    uint32_t warm=1,warmAddress=(uint32_t)&s->startupSkipped;
    if (!s->external) {
        /* At 32 clocks/word the fast path must not publish ring metadata or
           poll HUB stop flags. The whole bounded burst is under 0.2 ms. */
        __asm volatile {
            rdpin value, pin
            nop
capture_bits_first
            testp pin wc
 if_c       jmp #capture_bits_first_read
            djnz polls, #capture_bits_first
            jmp #capture_bits_control
capture_bits_first_read
            rdpin value, pin
            getct first
            mov haveFirst, #1
            wrlong value, address
            add address, #4
            djnz remaining, #capture_bits_next
            jmp #capture_bits_end
capture_bits_next
            mov polls, #64
capture_bits_poll
            testp pin wc
 if_c       jmp #capture_bits_read
            djnz polls, #capture_bits_poll
            jmp #capture_bits_control
capture_bits_read
            rdpin value, pin
            wrlong value, address
            add address, #4
            djnz remaining, #capture_bits_next
            jmp #capture_bits_end
capture_bits_control
            rdlong temp, stopAddress
            tjnz temp, #capture_bits_cancel
            getct now
            sub now, start
            cmp now, timeout wc
 if_ae      jmp #capture_bits_timeout
            mov polls, #64
            tjnz haveFirst, #capture_bits_poll
            jmp #capture_bits_first
capture_bits_cancel
            mov status, #3
            jmp #capture_bits_end
capture_bits_timeout
            mov status, #5
capture_bits_end
            getct last
        }
    } else {
        /* External bit clock contract: <=1 MHz. The slow wait path checks
           cancellation and a whole-burst timeout even when clocks disappear. */
        __asm volatile {
capture_external_wait
            rdlong temp, stopAddress
            tjnz temp, #capture_external_cancel
            getct now
            sub now, start
            cmp now, timeout wc
 if_ae      jmp #capture_external_timeout
            testp pin wc
 if_nc      jmp #capture_external_wait
            rdpin value, pin
            tjz warm, #capture_external_valid
            mov warm, #0
            mov temp, #1
            wrlong temp, warmAddress
            jmp #capture_external_wait
capture_external_valid
            tjnz haveFirst, #capture_external_store
            getct first
            mov haveFirst, #1
capture_external_store
            wrlong value, address
            add address, #4
            djnz remaining, #capture_external_wait
            jmp #capture_external_end
capture_external_cancel
            mov status, #3
            jmp #capture_external_end
capture_external_timeout
            mov status, #5
capture_external_end
            getct last
        }
    }
    uint32_t count=s->limit-remaining;
    s->head=count; s->emitted=count; s->rawCount=count;
    s->elapsed=count ? last-first : 0;
    s->expected=count ? (count-1U)*32U : 0;
    if (!s->external && status==COMPLETE &&
        (s->elapsed>s->expected+28U || s->elapsed+8U<s->expected)) status=TIMING;
    s->state=status;
}

static void scopeJob(void *argument, volatile int *stop) {
    Capture *s=argument;
    uint32_t setting=64U|(uint32_t)s->pin, period=s->period, limit=s->limit;
    uint32_t dataAddress=(uint32_t)s->data, mask=0, value=0, now=0, scheduled=0;
    uint32_t start=_cnt(), first=0, last=0, timeout=s->timeout, status=COMPLETE, haveFirst=0;
    uint32_t stopAddress=(uint32_t)stop, temp=0, trigger=(uint32_t)s->trigger;
    uint32_t head=0,next=0,tail=0,address=0,emitted=0,ringMask=1023,gap=0,maximum=0;
    uint32_t headAddress=(uint32_t)&s->head,tailAddress=(uint32_t)&s->tail;
    uint32_t emittedAddress=(uint32_t)&s->emitted,gapAddress=(uint32_t)&s->maxGap;
    for (int i=0;i<4;i++) if (s->channels&(1U<<i)) mask|=0xffU<<(i*8);
    __asm volatile {
        setscp setting
        cmp trigger, #63 wc
 if_ae  jmp #capture_scope_begin
capture_scope_trigger
        rdlong temp, stopAddress
        tjnz temp, #capture_scope_cancel
        getct now
        sub now, start
        cmp now, timeout wc
 if_ae  jmp #capture_scope_timeout
        testp trigger wc
 if_nc  jmp #capture_scope_trigger
capture_scope_begin
        getct scheduled
        add scheduled, period
capture_scope_loop
        rdlong temp, stopAddress
        tjnz temp, #capture_scope_cancel
        /* Never arm an already elapsed CT1 value: that could wait for a
           full 32-bit clock wrap before honoring cancellation. */
        getct now
        mov temp, scheduled
        sub temp, now
        testb temp, #31 wc
 if_c   jmp #capture_scope_late
        cmp temp, #32 wc
 if_b   jmp #capture_scope_late
        addct1 scheduled, #0
        waitct1
        getscp value
        and value, mask
        getct now
        mov temp, now
        sub temp, scheduled
        cmp temp, period wc
 if_ae  jmp #capture_scope_late
        mov next, head
        add next, #1
        and next, ringMask
        rdlong tail, tailAddress
        cmp next, tail wz
 if_z   jmp #capture_scope_full
        tjnz haveFirst, #capture_scope_gap
        mov first, now
        mov haveFirst, #1
        jmp #capture_scope_store
capture_scope_gap
        mov gap, now
        sub gap, last
        cmp gap, maximum wc
 if_ae  mov maximum, gap
capture_scope_store
        mov address, head
        shl address, #2
        add address, dataAddress
        wrlong value, address
        mov head, next
        wrlong head, headAddress
        add emitted, #1
        wrlong emitted, emittedAddress
        wrlong maximum, gapAddress
        mov last, now
        add scheduled, period
        tjz limit, #capture_scope_loop
        cmp emitted, limit wc
 if_b   jmp #capture_scope_loop
        jmp #capture_scope_done
capture_scope_full
        mov status, #4
        jmp #capture_scope_done
capture_scope_cancel
        mov status, #3
        jmp #capture_scope_done
capture_scope_timeout
        mov status, #5
        jmp #capture_scope_done
capture_scope_late
        mov status, #6
capture_scope_done
        setscp #0
    }
    s->rawCount=emitted;s->emitted=emitted;s->maxGap=maximum;
    s->elapsed=emitted ? last-first : 0;
    s->expected=emitted ? (emitted-1U)*period : 0;
    s->state=status;
}

static void captureJob(void *argument, volatile int *stop) {
    Capture *s=argument;
    s->observedCog=_cogid();
    s->localDIR=s->pin<32 ? (_DIRA>>s->pin)&1 : (_DIRB>>(s->pin-32))&1;
    if (*stop) s->state=CANCELED;
    else if (s->order==4) dmaJob(s,stop);
    else if (s->order==0 && s->streaming) bitsStreamJob(s,stop);
    else if (s->order==0) bitsJob(s,stop);
    else if (s->order==1) scopeJob(s,stop);
    else sincJob(s,stop);
    s->ownsCog=0; /* no more pin-bus acknowledgements after this publication */
}
OBJ primP2ScopeCapture(int argc, OBJ *args) {
    if (p2IsWorker() || argc!=7) return falseObj;
    for (int i=0;i<7;i++) if (!isInt(args[i])) return falseObj;
    int base=obj2int(args[0]), mask=obj2int(args[1]), period=obj2int(args[2]);
    int count=obj2int(args[3]), cog=obj2int(args[4]), trigger=obj2int(args[5]), ms=obj2int(args[6]);
    if (base<0 || (base&3) || base+3>=P2_USER_PIN_COUNT || mask<1 || mask>15 ||
        period<512 || period>1800000 || count<0 || ms<1 || ms>10000 ||
        (trigger!=-1 && (trigger<base || trigger>=base+4 || !(mask&(1<<(trigger-base)))))) return falseObj;
    if (!(capture.ownsCog && capture.cog==cog) && !p2NativeCanStart(cog)) return falseObj;
    if (!p2ScopeCaptureReady(base,mask)) return falseObj;
    stopCapture();memset(&capture,0,sizeof(capture));
    capture.pin=base;capture.cog=cog;capture.order=1;capture.period=period;
    capture.channels=mask;capture.trigger=trigger;capture.limit=count;capture.observedCog=-1;
    capture.timeout=(_clockfreq()/1000U)*(uint32_t)ms;
    if (trigger>=0) _akpin(trigger); /* before transferring bus ownership */
    capture.state=RUNNING;capture.ownsCog=1;
    if (!p2NativeStart(cog,captureJob,&capture)) { capture.ownsCog=0;capture.state=IDLE;return falseObj; }
    return trueObj;
}

OBJ primP2CaptureStart(int argc, OBJ *args) {
    if (p2IsWorker()) return fail(primitiveNotImplemented);
    if ((argc!=9 && argc!=10) || !IS_TYPE(args[1],StringType)) return falseObj;
    for (int i=0;i<9;i++) if (i!=1 && i!=6 && !isInt(args[i])) return falseObj;
    if (objType(args[6])!=BooleanType) return falseObj;
    int pin=obj2int(args[0]), period=obj2int(args[2]), keep=obj2int(args[3]);
    int limit=obj2int(args[4]), cog=obj2int(args[5]), external=args[6]==trueObj;
    int b=obj2int(args[7]), msecs=obj2int(args[8]), order=0;
    const char *kind=obj2str(args[1]);
    if (!strcmp(kind,"SINC2")) order=2;
    else if (!strcmp(kind,"SINC3")) order=3;
    else if (strcmp(kind,"bits")) return falseObj;
    if (pin<0 || pin>=P2_USER_PIN_COUNT || b < -3 || b>3 || pin+b<0 || pin+b>=P2_USER_PIN_COUNT ||
        keep<1 || limit<0 || msecs<1 || msecs>10000) return falseObj;
    if (order && (period<(external ? 16 : 256) || period>(order==2 ? 8192 : 511))) return falseObj;
    if (!order && (period!=32 || keep!=1 || (!external && limit<1) || (uint32_t)limit>=CAPACITY)) return falseObj;
    uint32_t pad=external ? P_SCHMITT_A : P_ADC_1X;
    if (argc==10 && !p2CapturePadBits(args[9],external,&pad)) return falseObj;
    if (!(capture.ownsCog && capture.cog==cog) && !p2NativeCanStart(cog)) return falseObj;
    stopCapture();
    memset(&capture,0,sizeof(capture));
    capture.pin=pin; capture.cog=cog; capture.observedCog=-1;
    capture.order=order; capture.period=period; capture.external=external;
    capture.streaming=!order && external && limit==0;
    capture.keep=keep; capture.limit=limit;
    capture.timeout=(_clockfreq()/1000U)*(uint32_t)msecs;
    capture.scale=order ? (uint32_t)period*(uint32_t)period : 0;
    if (order==3) capture.scale*=period;
    if (!p2PrepareCapturePin(pin,order,period,external,b,pad)) return falseObj;
    capture.state=RUNNING; capture.ownsCog=1;
    if (!p2NativeStart(cog,captureJob,&capture)) {
        capture.ownsCog=0; capture.state=IDLE;
        setPinMode(pin,0); return falseObj;
    }
    return trueObj;
}
OBJ primP2DMACapture(int argc, OBJ *args) {
    if (p2IsWorker() || argc!=5) return falseObj;
    for (int i=0;i<5;i++) if (i!=1 && !isInt(args[i])) return falseObj;
    int pin=obj2int(args[0]),power=obj2int(args[2]),pages=obj2int(args[3]),cog=obj2int(args[4]);uint32_t pad;
    if (pin<0 || pin>=P2_USER_PIN_COUNT || power<0 || power>15 || pages<0 || pages>6 ||
        (!p2CapturePadBits(args[1],0,&pad) && !p2CapturePadBits(args[1],1,&pad))) return falseObj;
    if (!(capture.ownsCog && capture.cog==cog) && !p2NativeCanStart(cog)) return falseObj;
    stopCapture();memset(&capture,0,sizeof(capture));
    capture.pin=pin;capture.cog=cog;capture.order=4;capture.period=power;capture.limit=pages;
    capture.observedCog=-1;capture.streaming=1;capture.guardBefore=capture.guardAfter=DMA_GUARD;
    if (!p2PrepareDMAInput(pin,args[1])) return falseObj;
    capture.state=RUNNING;capture.ownsCog=1;
    if (!p2NativeStart(cog,captureJob,&capture)) {
        capture.ownsCog=0;capture.state=IDLE;setPinMode(pin,0);return falseObj;
    }
    return trueObj;
}
OBJ primP2DMARecord(int argc, OBJ *args) {
    if (p2IsWorker() || argc!=9 || objType(args[7])!=BooleanType) return falseObj;
    for (int i=0;i<9;i++) if (i!=1 && i!=7 && !isInt(args[i])) return falseObj;
    int pin=obj2int(args[0]),power=obj2int(args[2]),pre=obj2int(args[3]),post=obj2int(args[4]);
    int cog=obj2int(args[5]),trigger=obj2int(args[6]),ms=obj2int(args[8]);uint32_t pad;
    if (pin<0 || pin>=P2_USER_PIN_COUNT || trigger<0 || trigger>=P2_USER_PIN_COUNT || trigger==pin ||
        power<0 || power>15 || pre<1 || pre>3 || post<1 || post>3 || pre+post>6 || ms<1 || ms>10000 ||
        (!p2CapturePadBits(args[1],0,&pad) && !p2CapturePadBits(args[1],1,&pad))) return falseObj;
    if (!(capture.ownsCog && capture.cog==cog) && !p2NativeCanStart(cog)) return falseObj;
    stopCapture();memset(&capture,0,sizeof(capture));
    capture.pin=pin;capture.cog=cog;capture.order=4;capture.period=power;
    capture.record=1;capture.prePages=pre;capture.postPages=post;
    capture.trigger=trigger;capture.triggerWord=-1;capture.triggerLevel=args[7]==trueObj;
    capture.timeout=(_clockfreq()/1000U)*(uint32_t)ms;
    capture.observedCog=-1;capture.streaming=1;capture.guardBefore=capture.guardAfter=DMA_GUARD;
    if (!p2PrepareDMAInput(pin,args[1]) || !p2PrepareDMATrigger(trigger)) return falseObj;
    capture.state=ARMED;capture.ownsCog=1;
    if (!p2NativeStart(cog,captureJob,&capture)) {
        capture.ownsCog=0;capture.state=IDLE;setPinMode(pin,0);setPinMode(trigger,0);return falseObj;
    }
    return trueObj;
}
OBJ primP2BitDensity(int argc, OBJ *args) {
    if (argc!=1 || !IS_TYPE(args[0],ByteArrayType)) return falseObj;
    uint32_t count=BYTES(args[0]),ones=0;
    if (!count || count>131072U) return falseObj;
    const uint8_t *bytes=(const uint8_t *)&FIELD(args[0],0);
    for (uint32_t i=0;i<count;i++) {
        uint32_t value=bytes[i];
        value=value-((value>>1)&0x55U);
        value=(value&0x33U)+((value>>2)&0x33U);
        ones+=(value+(value>>4))&15U;
    }
    return int2obj(_muldiv64(ones,1000000U,count*8U));
}
OBJ primP2CaptureStop(int argc, OBJ *args) {
    (void)args;
    if (argc || p2IsWorker()) return falseObj;
    stopCapture(); return trueObj;
}
OBJ primP2CaptureInfo(int argc, OBJ *args) {
    if (argc!=1 || !IS_TYPE(args[0],StringType)) return falseObj;
    const char *name=obj2str(args[0]); uint32_t n=0;
    if (!strcmp(name,"state")) n=capture.state;
    else if (!strcmp(name,"available")) n=capture.record && capture.ownsCog ? 0 : (capture.head-capture.tail)&(CAPACITY-1U);
    else if (!strcmp(name,"raw")) n=capture.order==1 ? capture.emitted : capture.rawCount;
    else if (!strcmp(name,"emitted")) n=capture.emitted;
    else if (!strcmp(name,"cog")) return int2obj(capture.observedCog);
    else if (!strcmp(name,"pin")) return int2obj(capture.pin);
    else if (!strcmp(name,"local DIR")) n=capture.localDIR;
    else if (!strcmp(name,"scale")) n=capture.scale;
    else if (!strcmp(name,"scope channels")) n=capture.channels;
    else if (!strcmp(name,"maximum gap clocks")) n=capture.maxGap;
    else if (!strcmp(name,"elapsed clocks")) n=capture.elapsed;
    else if (!strcmp(name,"expected clocks")) n=capture.expected;
    else if (!strcmp(name,"wraps")) n=capture.wraps;
    else if (!strcmp(name,"continuous bits")) n=capture.order==4 ? !capture.limit && !capture.record : capture.streaming;
    else if (!strcmp(name,"DMA")) n=capture.order==4;
    else if (!strcmp(name,"sample clocks")) n=capture.order==4 ? 1U<<capture.period : 0;
    else if (!strcmp(name,"page words")) n=capture.order==4 ? DMA_PAGE_WORDS : 0;
    else if (!strcmp(name,"buffer guards")) return capture.order==4 && capture.guardBefore==DMA_GUARD && capture.guardAfter==DMA_GUARD ? trueObj : falseObj;
    else if (!strcmp(name,"pretrigger words")) n=capture.prePages*DMA_PAGE_WORDS;
    else if (!strcmp(name,"record words")) n=(capture.prePages+capture.postPages)*DMA_PAGE_WORDS;
    else if (!strcmp(name,"trigger word")) return int2obj(capture.record ? capture.triggerWord : -1);
    else if (!strcmp(name,"history discarded words")) n=capture.discarded;
    else if (!strcmp(name,"startup discarded words")) n=capture.startupSkipped;
    else return falseObj;
    return int2obj(n&0x3fffffffU);
}
static int readCount(int argc, OBJ *args) {
    if (argc!=1 || !isInt(args[0])) return -1;
    int count=obj2int(args[0]);
    if (count<1 || count>256) return -1;
    uint32_t available=(capture.head-capture.tail)&(CAPACITY-1U);
    return count<(int)available ? count : (int)available;
}
OBJ primP2StreamRead(int argc, OBJ *args) {
    int count=readCount(argc,args);
    if (count<0 || (capture.order!=2 && capture.order!=3)) return falseObj;
    OBJ result=newObj(ListType,count+1,falseObj);
    if (!result) return result;
    FIELD(result,0)=int2obj(count);
    uint32_t tail=capture.tail;
    for (int i=0;i<count;i++) { FIELD(result,i+1)=int2obj(capture.data[tail]);tail=(tail+1U)&(CAPACITY-1U); }
    capture.tail=tail;return result;
}
OBJ primP2CaptureRead(int argc, OBJ *args) {
    int count=readCount(argc,args);
    if (count<0 || (capture.record && capture.ownsCog) || (capture.order!=0 && capture.order!=1 && capture.order!=4) || (capture.order==0 && capture.ownsCog && !capture.streaming)) return falseObj;
    OBJ result=newObj(ByteArrayType,count,falseObj);
    if (!result) return result;
    setByteCountAdjust(result,count*4);
    uint32_t tail=capture.tail;
    for (int i=0;i<count;i++) { FIELD(result,i)=(OBJ)capture.data[tail];tail=(tail+1U)&(CAPACITY-1U); }
    capture.tail=tail;return result;
}


OBJ primP2ScaleSample(int argc, OBJ *args) {
    if (argc!=4) return falseObj;
    for (int i=0;i<4;i++) if (!isInt(args[i])) return falseObj;
    int value=obj2int(args[0]), low=obj2int(args[1]), high=obj2int(args[2]), maximum=obj2int(args[3]);
    if (low<0 || high<=low || maximum<1) return falseObj;
    if (value<=low) return int2obj(0);
    if (value>=high) return int2obj(maximum);
    return int2obj(_muldiv64((uint32_t)(value-low),(uint32_t)maximum,(uint32_t)(high-low)));
}
