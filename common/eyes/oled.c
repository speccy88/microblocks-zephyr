/* SPDX-License-Identifier: MIT */
#include "eyes.h"
#include <string.h>
int eyes_normalize_address(int address) {
    if(address==0x78||address==0x7a)return address>>1;
    return address==0x3c||address==0x3d?address:-1;
}
int eyes_find_address(eyes_probe probe,void *context) {
    if(!probe)return 0;
    bool c=probe(context,0x3c)==0,d=probe(context,0x3d)==0;
    return c&&d?-1:(c?0x3c:(d?0x3d:0));
}
eyes_config eyes_defaults(int height,int controller,int address) {
    eyes_config c={0};
    c.height=height;c.controller=controller;c.address=eyes_normalize_address(address);
    c.x=c.y=500;c.width=36;c.eye_height=height==32?24:36;
    c.radius=8;c.spacing=10;c.autoblink=true;
    c.blink_interval=3;c.blink_variation=2;c.idle_interval=2;c.idle_variation=2;
    return c;
}
bool eyes_config_valid(const eyes_config *c) {
    return c && (c->height==32||c->height==64) && c->controller>=0 && c->controller<=1 &&
        !(c->controller==1&&c->height!=64) && (c->address==0x3c||c->address==0x3d) &&
        c->mood>=0&&c->mood<=3 && c->x>=0&&c->x<=1000&&c->y>=0&&c->y<=1000 &&
        c->width>=8&&c->width<=52&&c->eye_height>=8&&c->eye_height<=c->height-4 &&
        c->radius>=0&&c->radius<=c->width/2&&c->radius<=c->eye_height/2 &&
        c->spacing>=0&&2*c->width+c->spacing<=120 &&
        c->blink_interval>=1&&c->blink_interval<=60&&c->blink_variation>=0&&c->blink_variation<=60 &&
        c->idle_interval>=1&&c->idle_interval<=60&&c->idle_variation>=0&&c->idle_variation<=60 &&
        c->horizontal_flicker>=0&&c->horizontal_flicker<=8&&c->vertical_flicker>=0&&c->vertical_flicker<=8;
}
static int command(const eyes_config *c,uint8_t value,eyes_write write,void *context) {
    uint8_t data[2]={0,value};return write(context,c->address,data,sizeof(data));
}
int eyes_oled_init(const eyes_config *c,eyes_write write,void *context) {
    if(!eyes_config_valid(c)||!write)return -1;
    /* Explicitly selected controller. Page mode works for both controllers. */
    uint8_t commands[]={0xae,0xd5,0x80,0xa8,(uint8_t)(c->height-1),0xd3,0x00,0x40,
        0xa1,0xc8,0xda,(uint8_t)(c->height==64?0x12:0x02),0x81,0x7f,0xd9,0xf1,
        0xdb,0x40,0xa4,0xa6};
    for(size_t i=0;i<sizeof(commands);i++) {int r=command(c,commands[i],write,context);if(r)return r;}
    const uint8_t ssd[]={0x8d,0x14,0x20,0x02};
    const uint8_t sh[]={0xad,0x8b};
    const uint8_t *tail=c->controller?sh:ssd;size_t n=c->controller?sizeof(sh):sizeof(ssd);
    for(size_t i=0;i<n;i++){int r=command(c,tail[i],write,context);if(r)return r;}
    /* Remain off until the worker has written the first complete frame. */
    return 0;
}
int eyes_oled_page(const eyes_config *c,unsigned page,const uint8_t *frame,eyes_write write,void *context) {
    if(!eyes_config_valid(c)||!frame||!write||page>=(unsigned)c->height/8)return -1;
    uint8_t columns=c->controller?2:0;
    uint8_t commands[4]={0,(uint8_t)(0xb0+page),columns,0x10};
    int r=write(context,c->address,commands,sizeof(commands));if(r)return r;
    for(unsigned x=0;x<128;x+=16){
        uint8_t data[17]={0x40};memcpy(data+1,frame+128*page+x,16);
        r=write(context,c->address,data,sizeof(data));if(r)return r;
    }
    if(page==(unsigned)c->height/8-1)return command(c,0xaf,write,context);
    return 0;
}
