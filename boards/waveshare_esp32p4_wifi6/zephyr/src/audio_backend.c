/* SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
 * SPDX-License-Identifier: Apache-2.0
 * ES8311 register setup adapted from esp_codec_dev 1.5.4 es8311.c.
 * Zephyr transport/worker/lifetime integration: microblocks-zephyr authors.
 * ADC-only, analog microphone, 16 kHz/16 bit, MCLK=256*Fs. No speaker/TX.
 */
#include <zephyr/kernel.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/i2s.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <zephyr/sys/atomic.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "audio_backend.h"
#include "audio_store.h"
#ifdef P4_AUDIO_DIAGNOSTIC
#include <zephyr/drivers/uart.h>
#include <zephyr/fatal.h>
static void trace(const char *s){const struct device *d=DEVICE_DT_GET(DT_NODELABEL(uart0));while(*s)uart_poll_out(d,*s++);uart_poll_out(d,'\n');}
void k_sys_fatal_error_handler(unsigned int reason,const struct arch_esf *esf){
    char s[128];snprintf(s,sizeof(s),"audio: fatal reason=%u pc=%lx ra=%lx",reason,esf?esf->mepc:0ul,esf?esf->ra:0ul);trace(s);
    for(;;)arch_cpu_idle();
}
#else
#define trace(s) do{}while(0)
#endif
static const struct device *const bus=DEVICE_DT_GET(DT_NODELABEL(i2c0));
static const struct device *const rx=DEVICE_DT_GET(DT_NODELABEL(i2s0));
static const struct device *const amp_gpio=DEVICE_DT_GET(DT_NODELABEL(gpio1));
#define CODEC 0x18
#define BLOCK 1024u
#define SLABS 6u
K_MEM_SLAB_DEFINE_STATIC(dma_slab,BLOCK,SLABS,64);
K_SEM_DEFINE(audio_requested,0,1);
K_MUTEX_DEFINE(audio_mutex);
static atomic_t cancelled;
enum { IDLE,RECORDING,READY,ERROR,FAULT };
static int state,identity;
static unsigned requested_frames;
static int16_t *pending;
static char message[192]="idle; microphone is off";
void *audio_alloc(size_t n){return shared_multi_heap_aligned_alloc(SMH_REG_ATTR_EXTERNAL,64,n);}
void audio_free(void *p){if(p)shared_multi_heap_free(p);}
static int wr(uint8_t r,uint8_t v){return i2c_reg_write_byte(bus,CODEC,r,v);}
static int probe(void)
{
    uint8_t a,b;
    if(!device_is_ready(bus) || i2c_reg_read_byte(bus,CODEC,0xfd,&a) ||
       i2c_reg_read_byte(bus,CODEC,0xfe,&b))return 0;
    return ((unsigned)a<<8)|b;
}
int p4_audio_codec_id(void)
{
    k_mutex_lock(&audio_mutex,K_FOREVER);
    if(state!=RECORDING)identity=probe();
    int result=identity;k_mutex_unlock(&audio_mutex);return result;
}
int p4_audio_available(void){return identity==0x8311 && device_is_ready(rx);}
static int codec_stop(void)
{
    /* Disable serial ADC output before powering down. Keep DAC and PA off. */
    static const uint8_t stop[][2]={{0x0a,0x4c},{0x09,0x4c},{0x31,0x60},{0x17,0},
        {0x0e,0xff},{0x12,2},{0x14,0},{0x0d,0xfa},{0x15,0},{0x02,0x10},
        {0x00,0},{0x00,0x1f},{0x01,0x30},{0x01,0},{0x45,0}};
    int error=0;
    for(unsigned i=0;i<ARRAY_SIZE(stop);i++){int e=wr(stop[i][0],stop[i][1]);if(e && !error)error=e;}
    return error;
}
void p4_audio_init(void)
{
    if(device_is_ready(amp_gpio))gpio_pin_configure(amp_gpio,21,GPIO_OUTPUT_INACTIVE);
    identity=probe();
    if(identity==0x8311){int error=codec_stop();
        snprintf(message,sizeof(message),error?"ES8311 detected; stop error %d":"ES8311 detected; microphone off",error);}
}
static int codec_start(void)
{
    /* Vendor 4.096 MHz/16 kHz clock table: prediv1, ADC/DAC div1,
     * single-speed, LRCK divider256, BCLK div4, ADC OSR0x10. */
    static const uint8_t start[][2]={{0x44,8},{0x44,8},{0x01,0x30},{0x02,0},
        {0x03,0x10},{0x16,4},{0x04,0x20},{0x05,0},{0x0b,0},{0x0c,0},
        {0x10,0x1f},{0x11,0x7f},{0x00,0x80},{0x01,0x3f},{0x06,3},
        {0x07,0},{0x08,0xff},{0x09,0x4c},{0x0a,0x4c},
        {0x13,0x10},{0x1b,0x0a},{0x1c,0x6a},{0x44,8},
        {0x17,0xbf},{0x0e,2},{0x12,2},{0x14,0x1a},{0x0d,1},
        {0x15,0x40},{0x37,8},{0x45,0},{0x0a,0x0c}};
    for(unsigned i=0;i<ARRAY_SIZE(start);i++){int e=wr(start[i][0],start[i][1]);if(e)return e;}
    return 0;
}
static int capture(int16_t *pcm,unsigned frames,char *detail,size_t size)
{
    trace("audio: amp");
    if(!device_is_ready(amp_gpio))return -ENODEV;
    int error=gpio_pin_configure(amp_gpio,21,GPIO_OUTPUT_INACTIVE);
    if(error)return error;
    trace("audio: probe");if(probe()!=0x8311)return -ENODEV;
    struct i2s_config cfg={.word_size=16,.channels=2,.format=I2S_FMT_DATA_FORMAT_I2S,
        .options=I2S_OPT_BIT_CLK_MASTER|I2S_OPT_FRAME_CLK_MASTER,
        .frame_clk_freq=AUDIO_RATE,.mem_slab=&dma_slab,.block_size=BLOCK,.timeout=100};
    trace("audio: configure");error=i2s_configure(rx,I2S_DIR_RX,&cfg);
    if(error){snprintf(detail,size,"configure %d",error);return error;}
    trace("audio: codec start");error=codec_start();
    uint64_t started_us=k_cyc_to_us_floor64(k_cycle_get_64());
    trace("audio: trigger");if(!error)error=i2s_trigger(rx,I2S_DIR_RX,I2S_TRIGGER_START);
    trace("audio: reading");
    unsigned copied=0,skip=2,blocks=0;
    uint64_t left_energy=0,right_energy=0;
    int64_t deadline=k_uptime_get()+frames*1000/AUDIO_RATE+1500;
    while(!error && copied<frames){
        if(atomic_get(&cancelled)){error=-ECANCELED;break;}
        if(k_uptime_get()>deadline){error=-ETIMEDOUT;break;}
        void *data=NULL;size_t bytes=0;
        error=i2s_read(rx,&data,&bytes);
        if(error)break;
        if(!data || bytes!=BLOCK){if(data)k_mem_slab_free(&dma_slab,data);error=-EIO;break;}
        int16_t *s=data;blocks++;
        if(skip)skip--;
        else for(unsigned i=0;i<bytes/4 && copied<frames;i++){
            int32_t l=s[2*i],r=s[2*i+1];
            left_energy+=(int64_t)l*l;right_energy+=(int64_t)r*r;
            pcm[copied++]=(int16_t)l; /* ES8311 mono ADC in the left slot */
        }
        k_mem_slab_free(&dma_slab,data);
    }
    uint64_t dma_us=k_cyc_to_us_floor64(k_cycle_get_64())-started_us;
    trace("audio: stop");int off=codec_stop();
    int dropped=i2s_trigger(rx,I2S_DIR_RX,I2S_TRIGGER_DROP);
    unsigned inuse=k_mem_slab_num_used_get(&dma_slab);
    snprintf(detail,size,"%u/%u frames, %u blocks, %llu us, L=%llu R=%llu, drop=%d slab=%u off=%d",
        copied,frames,blocks,(unsigned long long)dma_us,(unsigned long long)left_energy,(unsigned long long)right_energy,dropped,inuse,off);
    /* A failed DROP never permits reuse of the permanently allocated DMA slab.
     * PCM is CPU-only, so it can be erased/released independently. */
    if(dropped || inuse)return -EBUSY;
    if(!error)error=off;
    return error;
}
static void worker(void *a,void *b,void *c)
{
    ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);
    for(;;){
        k_sem_take(&audio_requested,K_FOREVER);
        unsigned frames=requested_frames;
        int16_t *pcm=audio_alloc(frames*sizeof(int16_t));
        char detail[144]="allocation failed";
        int error=pcm?capture(pcm,frames,detail,sizeof(detail)):-ENOMEM;
        k_mutex_lock(&audio_mutex,K_FOREVER);
        if(error || atomic_get(&cancelled)){
            if(pcm){memset(pcm,0,frames*sizeof(int16_t));audio_free(pcm);}
            state=error==-EBUSY?FAULT:atomic_get(&cancelled)?IDLE:ERROR;
            snprintf(message,sizeof(message),"record error %d; %s",error,detail);
        }else{pending=pcm;state=READY;snprintf(message,sizeof(message),"PCM ready; mic stopped; %s",detail);}
        k_mutex_unlock(&audio_mutex);
    }
}
K_THREAD_DEFINE(audio_thread,8192,worker,NULL,NULL,NULL,7,0,0);
int p4_audio_request(unsigned ms)
{
    k_mutex_lock(&audio_mutex,K_FOREVER);
    if(state==RECORDING || state==READY || state==FAULT || ms<20 || ms>8000 ||
       audio_count()>=AUDIO_SLOTS || !device_is_ready(rx)){
        k_mutex_unlock(&audio_mutex);return 0;
    }
    identity=probe();
    if(identity!=0x8311){snprintf(message,sizeof(message),"ES8311 identity unavailable: %04x",identity);k_mutex_unlock(&audio_mutex);return 0;}
    requested_frames=ms*(AUDIO_RATE/1000);atomic_clear(&cancelled);state=RECORDING;
    snprintf(message,sizeof(message),"recording bounded %u ms",ms);
    k_sem_give(&audio_requested);k_mutex_unlock(&audio_mutex);return 1;
}
int p4_audio_busy(void){k_mutex_lock(&audio_mutex,K_FOREVER);int b=state==RECORDING;k_mutex_unlock(&audio_mutex);return b;}
int p4_audio_result(void)
{
    k_mutex_lock(&audio_mutex,K_FOREVER);int h=0;
    if(state==READY){h=audio_adopt(pending,requested_frames);
        if(!h){memset(pending,0,requested_frames*2);audio_free(pending);}
        pending=NULL;state=IDLE;}
    else if(state==ERROR)state=IDLE;
    k_mutex_unlock(&audio_mutex);return h;
}
void p4_audio_discard(void)
{
    k_mutex_lock(&audio_mutex,K_FOREVER);atomic_set(&cancelled,1);
    if(state==READY){memset(pending,0,requested_frames*2);audio_free(pending);pending=NULL;state=IDLE;}
    if(state==ERROR)state=IDLE;
    k_mutex_unlock(&audio_mutex);
}
const char *p4_audio_status(void)
{
    static char snapshot[sizeof(message)];k_mutex_lock(&audio_mutex,K_FOREVER);
    memcpy(snapshot,message,sizeof(message));k_mutex_unlock(&audio_mutex);return snapshot;
}
