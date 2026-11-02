/* SPDX-License-Identifier: MPL-2.0 */
/* VM-thread service; settings are protected by the native sensor's mutex. */
#include "camera_tuning.h"
#include "camera_backend.h"
#include "p4_video.h"
#include "serial_speed.h"
#include "vm/interp.h"
#include <zephyr/kernel.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
enum {IDLE,CAPTURING,READY,ERROR};
static unsigned state;
static uint32_t session;
static int image,last_error;
static int64_t deadline;
static p4_camera_settings used;
static unsigned frame_width=320,frame_height=180,capture_ms;
static int64_t capture_began;
static unsigned u16(const uint8_t *p){return p[0]|(unsigned)p[1]<<8;}
static uint32_t u32(const uint8_t *p){return u16(p)|(uint32_t)u16(p+2)<<16;}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=v>>(8*i);}
int p4_camera_tuning_settings(int exposure,int analog,int digital){
    if(camera_busy())return -EBUSY;
    if(exposure<0||analog<0||digital<0)return -EINVAL;
    p4_camera_settings s={(unsigned)exposure,(unsigned)analog,(unsigned)digital};return p4_sensor_settings_set(&s);
}
void p4_camera_tuning_status(char *out,size_t n){
    p4_camera_settings s;bool supported=p4_sensor_settings(&s);
    snprintf(out,n,"{\"supported\":%s,\"exposure\":%u,\"analog\":%u,\"digital\":%u,\"pattern\":%u,\"state\":%u,\"handle\":%d,\"used_exposure\":%u,\"used_analog\":%u,\"used_digital\":%u,\"error\":%d,\"width\":%u,\"height\":%u,\"capture_ms\":%u,\"baud\":%u}",
        supported?"true":"false",s.exposure,s.analog,s.digital,CONFIG_P4_IMX219_TEST_PATTERN,state,image,used.exposure,used.analog,used.digital,last_error,frame_width,frame_height,capture_ms,p4_serial_speed_baud());
}
void p4_camera_tuning_reset(void){
    if(state==CAPTURING)camera_discard_owned(CAMERA_OWNER_TUNER);
    if(image)image_release(image);
    image=0;session=0;state=IDLE;last_error=0;
}
void p4_camera_tuning_poll(void){
    if(!session)return;
    if(k_uptime_get()>=deadline){p4_camera_tuning_reset();return;}
    if(state!=CAPTURING||camera_busy())return;
    int original=camera_result_owned(CAMERA_OWNER_TUNER);
    if(original){image=image_resize(original,frame_width,frame_height,IMAGE_RGB565);image_release(original);}
    if(!image){state=ERROR;last_error=-EIO;deadline=k_uptime_get()+3000;return;}
    capture_ms=(unsigned)(k_uptime_get()-capture_began);
    /* Baseline UART wire time plus bounded per-chunk/browser overhead. */
    uint64_t bytes=(uint64_t)frame_width*frame_height*2;
    uint64_t lease=10000+bytes*10000/115200+((bytes+511)/512)*12;
    if(lease>300000)lease=300000;
    state=READY;deadline=k_uptime_get()+lease;
}
static void reply(unsigned op,uint32_t request,uint32_t client,int status){
    uint8_t out[352]={0};memcpy(out,"P4CC",4);out[4]=1;out[5]=op;out[6]=status;out[7]=state;put32(out+8,request);put32(out+12,client);
    p4_camera_tuning_status((char *)out+16,sizeof(out)-16);
    waitAndSendMessage(213,0,16+strlen((char *)out+16),(char *)out);
}
void p4_camera_tuning_open(void){if(hasOutputSpace(357))reply(128,0,0,0);}
void p4_camera_tuning_message(int type,int n,const char *body){
    const uint8_t *p=(const uint8_t *)body;
    if(type!=213||n!=24||memcmp(p,"P4CC",4)||p[4]!=1||p[5]>5||u16(p+6)||u16(p+22)||!hasOutputSpace(357))return;
    unsigned op=p[5],exposure=u16(p+16),analog=u16(p+18),digital=u16(p+20);uint32_t request=u32(p+8),client=u32(p+12);int status=0;
    if((op!=1&&op!=3&&(exposure||analog||digital))||((op<=2)&&client)||((op>=3)&&(!client||client>0x1fffffffu))){reply(op,request,client,1);return;}
    if(op==3&&(digital||((exposure||analog)&&(exposure<16||exposure>1280||analog<16||analog>720)))){reply(op,request,client,1);return;}
    p4_camera_tuning_poll();
    if(op==1){int e=p4_camera_tuning_settings(exposure,analog,digital);status=e==-EBUSY?3:(e==-ENOTSUP?2:(e?1:0));}
    else if(op==2){if(camera_busy())status=3;else{p4_camera_settings s;if(!p4_sensor_settings(&s))status=2;else p4_sensor_settings_reset();}}
    else if(op==3){
        if(session||!p4_sensor_settings(&used)||!camera_request_owned(CAMERA_OWNER_TUNER))status=3;
        else{frame_width=exposure?exposure:320;frame_height=analog?analog:180;capture_ms=0;capture_began=k_uptime_get();session=client;state=CAPTURING;last_error=0;deadline=k_uptime_get()+8000;}
    }else if(op>=4){if(client!=session)status=1;else if(op==5)p4_camera_tuning_reset();}
    reply(op,request,client,status);
}
