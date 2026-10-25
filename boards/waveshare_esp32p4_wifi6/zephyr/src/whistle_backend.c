/* SPDX-License-Identifier: MPL-2.0 */
#include "whistle_backend.h"
#include "audio_store.h"
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <stdio.h>
#include <string.h>
#if defined(P4_WHISTLE)
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <zephyr/sys/sys_heap.h>
#include <setjmp.h>
/* Select the independent C99 API without importing ESP-IDF heap glue. */
#undef ESP_PLATFORM
#include "nd_whistle.h"
#include "nd_quant.h"
#define ARENA_BYTES (12u*1024u*1024u)
#define MAX_FRAMES 64000u
#define DEADLINE_MS 180000
extern const unsigned char p4_whistle_model_start[],p4_whistle_model_end[];
#ifdef P4_WHISTLE_FIXTURE
extern const unsigned char p4_whistle_fixture_start[],p4_whistle_fixture_end[];
#endif
K_SEM_DEFINE(whistle_requested,0,1);
K_MUTEX_DEFINE(whistle_mutex);
static atomic_t cancelled;
static int running,language,fixture_mode;
static unsigned frames;
static int16_t *input;
static char text[512],message[160]="idle; model in flash; microphone off";
static unsigned elapsed_ms,encode_ms,decode_ms,peak_bytes,live_bytes,stack_unused;
static const char *phase="idle";
static void *arena;
static struct sys_heap heap;
static jmp_buf unwind;
static int64_t deadline,last_yield;
typedef struct { size_t size; uint32_t magic,pad[2]; } allocation;
static void checkpoint(void)
{
    if(atomic_get(&cancelled))longjmp(unwind,2);
    int64_t now=k_uptime_get();
    if(now>=deadline)longjmp(unwind,3);
    if(now-last_yield>=20){last_yield=now;k_sleep(K_MSEC(1));}
}
/* Engine calls occur only on this worker, with no OS lock or DMA resource.
 * A failed allocation unwinds instead of letting unchecked upstream scratch
 * allocation sites dereference NULL. The whole private arena is then freed. */
void *p4_whistle_alloc(size_t n)
{
    checkpoint();
    if(n>ARENA_BYTES-sizeof(allocation))longjmp(unwind,1);
    if(!n)n=1;
    allocation *a=sys_heap_aligned_alloc(&heap,16,n+sizeof(*a));
    if(!a)longjmp(unwind,1);
    a->size=n;a->magic=0x57484953;
    live_bytes+=n;if(live_bytes>peak_bytes)peak_bytes=live_bytes;
    return a+1;
}
void *p4_whistle_calloc(size_t n,size_t s)
{
    if(s && n>ARENA_BYTES/s)longjmp(unwind,1);
    size_t bytes=n*s;void *p=p4_whistle_alloc(bytes);memset(p,0,bytes);return p;
}
void p4_whistle_free(void *p)
{
    if(!p)return;
    allocation *a=(allocation *)p-1;
    if((uintptr_t)a<(uintptr_t)arena || (uintptr_t)a+sizeof(*a)>=(uintptr_t)arena+ARENA_BYTES || a->magic!=0x57484953)longjmp(unwind,4);
    live_bytes-=a->size;a->magic=0;sys_heap_free(&heap,a);
}
static void rows_checked(nd_row_fn fn,void *ctx,uint32_t n)
{
    for(uint32_t i=0;i<n;i+=64){checkpoint();fn(ctx,i,MIN(n,i+64));}
}
static void set_phase(const char *s)
{
    k_mutex_lock(&whistle_mutex,K_FOREVER);phase=s;k_mutex_unlock(&whistle_mutex);
}
static int infer(void)
{
    int reason=setjmp(unwind);
    if(reason)return -reason;
    nd_parallel_rows=rows_checked;
    nd_whistle *w=p4_whistle_calloc(1,sizeof(*w));
    set_phase("open");
    int rc=nd_whistle_open(w,p4_whistle_model_start,p4_whistle_model_end-p4_whistle_model_start);
    if(rc){snprintf(message,sizeof(message),"model open error %d",rc);return -5;}
    if(nd_whistle_set_depth(w,4))return -5;
    float *pcm=p4_whistle_alloc(frames*sizeof(float));
    const int16_t *source=input;
#ifdef P4_WHISTLE_FIXTURE
    if(fixture_mode)source=(const int16_t *)p4_whistle_fixture_start;
#endif
    for(unsigned i=0;i<frames;i++)pcm[i]=(float)source[i]/32768.0f;
    checkpoint();
    /* Require 100ms above an estimated floor; fixture bypasses trimming for
     * exact comparison with the established host baseline. */
    unsigned first=0,end=frames;
    if(!fixture_mode && !nd_whistle_find_speech(pcm,frames,0,12,200,&first,&end)){
        text[0]=0;snprintf(message,sizeof(message),"no speech above the local noise floor");return 0;
    }
    pcm+=first;unsigned count=end-first;
    uint32_t T=nd_whistle_frames(w,count);
    float *enc=p4_whistle_alloc((size_t)T*w->d*sizeof(float));
    set_phase("encode");int64_t start=k_uptime_get();
    if(nd_whistle_encode(w,pcm,count,enc))return -5;
    encode_ms=k_uptime_get()-start;checkpoint();
    set_phase("decode");start=k_uptime_get();uint32_t ids[64];
    rc=nd_whistle_decode(w,enc,T,language,ids,ARRAY_SIZE(ids));
    decode_ms=k_uptime_get()-start;checkpoint();
    if(rc<0 || nd_whistle_detok(w,ids,rc,text,sizeof(text))<0)return -5;
    snprintf(message,sizeof(message),"local text ready; %d tokens; input PCM released",rc);
    /* Whole arena release also covers upstream temporaries on any exit. */
    return 0;
}
static void worker(void *a,void *b,void *c)
{
    (void)a;(void)b;(void)c;
    for(;;){
        k_sem_take(&whistle_requested,K_FOREVER);
        int64_t start=k_uptime_get();deadline=start+DEADLINE_MS;last_yield=start;
        peak_bytes=live_bytes=encode_ms=decode_ms=0;
        arena=shared_multi_heap_aligned_alloc(SMH_REG_ATTR_EXTERNAL,64,ARENA_BYTES);
        int rc=-1;
        if(arena){sys_heap_init(&heap,arena,ARENA_BYTES);rc=infer();
            shared_multi_heap_free(arena);arena=NULL;}
        if(input){memset(input,0,frames*sizeof(*input));audio_free(input);input=NULL;}
        size_t unused=0;
        if(k_thread_stack_space_get(k_current_get(),&unused))unused=0;
        k_mutex_lock(&whistle_mutex,K_FOREVER);
        elapsed_ms=k_uptime_get()-start;live_bytes=0;stack_unused=unused;
        if(rc){text[0]=0;snprintf(message,sizeof(message),"%s",
            rc==-1?"PSRAM budget exhausted; release images and retry":rc==-2?"cancelled; all inference buffers released":
            rc==-3?"180 second deadline; all inference buffers released":rc==-4?"allocation ownership error":"model/inference error");}
        phase=rc?"error":"ready";running=0;k_mutex_unlock(&whistle_mutex);
    }
}
/* RV32 compiler stack data: decode->decode_pass->dec_step->dec_block->MLP
 * nests more than 40 KiB. A 24 KiB stack overwrote the adjacent idle audio
 * stack even while transcription appeared correct. Guard and measure 64KiB. */
K_THREAD_DEFINE(whistle_thread,65536,worker,NULL,NULL,NULL,8,0,0);
static int request(int handle,int lang,int fixture)
{
    if(lang < -1 || lang>=ND_WH_LANGS)return 0;
    k_mutex_lock(&whistle_mutex,K_FOREVER);
    if(running){k_mutex_unlock(&whistle_mutex);return 0;}
    unsigned n=0;int16_t *copy=NULL;
    if(fixture){
#ifdef P4_WHISTLE_FIXTURE
        n=(p4_whistle_fixture_end-p4_whistle_fixture_start)/2;
#endif
    }else{
        const audio_view *v=audio_get(handle);
        if(v && v->rate==16000 && v->channels==1 && v->frames<=MAX_FRAMES && v->frames>=1600){
            n=v->frames;copy=audio_alloc(n*sizeof(*copy));
            if(copy)memcpy(copy,v->samples,n*sizeof(*copy));else n=0;
        }
    }
    if(!n){snprintf(message,sizeof(message),"expected immutable 16kHz mono PCM, 0.1..4 seconds");k_mutex_unlock(&whistle_mutex);return 0;}
    input=copy;frames=n;language=lang;fixture_mode=fixture;text[0]=0;
    atomic_clear(&cancelled);running=1;phase="queued";elapsed_ms=encode_ms=decode_ms=peak_bytes=0;
    k_sem_give(&whistle_requested);k_mutex_unlock(&whistle_mutex);return 1;
}
int p4_whistle_request(int h,int l){return request(h,l,0);}
int p4_whistle_fixture(int l){return request(0,l,1);}
int p4_whistle_available(void){return 1;}
int p4_whistle_busy(void){k_mutex_lock(&whistle_mutex,K_FOREVER);int b=running;k_mutex_unlock(&whistle_mutex);return b;}
void p4_whistle_cancel(void){atomic_set(&cancelled,1);k_mutex_lock(&whistle_mutex,K_FOREVER);if(!running){text[0]=0;phase="idle";}k_mutex_unlock(&whistle_mutex);}
void p4_whistle_status(char *out,size_t n)
{
    k_mutex_lock(&whistle_mutex,K_FOREVER);
    /* Worker-owned metrics/text are published by the running=0 transition
     * under this mutex; do not read them while inference is writing. */
    snprintf(out,n,"{\"phase\":\"%s\",\"message\":\"%s\",\"frames\":%u,\"elapsed_ms\":%u,\"encode_ms\":%u,\"decode_ms\":%u,\"peak_requested_bytes\":%u,\"reserved_arena_bytes\":%u,\"stack_unused_bytes\":%u,\"buffers_released\":%s}",phase,running?"inference active":message,frames,running?0:elapsed_ms,running?0:encode_ms,running?0:decode_ms,running?0:peak_bytes,ARENA_BYTES,running?0:stack_unused,running?"false":"true");
    k_mutex_unlock(&whistle_mutex);
}
void p4_whistle_result(char *out,size_t n){k_mutex_lock(&whistle_mutex,K_FOREVER);snprintf(out,n,"%s",running?"":text);k_mutex_unlock(&whistle_mutex);}
#else
int p4_whistle_request(int h,int l){(void)h;(void)l;return 0;}
int p4_whistle_fixture(int l){(void)l;return 0;}
int p4_whistle_available(void){return 0;}
int p4_whistle_busy(void){return 0;}
void p4_whistle_cancel(void){}
void p4_whistle_status(char *out,size_t n){snprintf(out,n,"{\"phase\":\"unsupported\",\"message\":\"build the verified Whistle model profile\"}");}
void p4_whistle_result(char *out,size_t n){if(n)out[0]=0;}
#endif
