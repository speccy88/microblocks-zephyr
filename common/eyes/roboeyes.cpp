/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native facade for FluxGarage RoboEyes, Dennis Hoelscher, GPL-3.0-or-later.
 * The upstream header is unmodified, external, pinned in dependencies/roboeyes.json.
 * This framebuffer surface is independently authored; no Adafruit implementation. */
#include "eyes.h"
#include <string.h>
static int minimum(int a,int b){return a<b?a:b;}
static int maximum(int a,int b){return a>b?a:b;}
using byte=uint8_t;
static uint32_t clock_ms, rng=0x8a5cd789u;
static unsigned long millis(){return clock_ms;}
static long random(long limit){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return limit>0?rng%(unsigned long)limit:0;}
class Framebuffer {
public:
    uint8_t pixels[1024]{};int height=64;
    void clearDisplay(){memset(pixels,0,sizeof(pixels));}
    void display(){} /* Native worker transmits pages separately. */
    void pixel(int x,int y,int color){
        if(x<0||x>=128||y<0||y>=height)return;
        uint8_t &v=pixels[x+(y/8)*128];uint8_t mask=1u<<(y%8);
        if(color)v|=mask;else v&=~mask;
    }
    void fillRoundRect(int x,int y,int w,int h,int radius,int color){
        if(w<=0||h<=0)return;
        int r=maximum(0,minimum(radius,minimum(w,h)/2));
        for(int yy=maximum(0,y);yy<minimum(height,y+h);yy++)
            for(int xx=maximum(0,x);xx<minimum(128,x+w);xx++){
                int dx=xx<x+r?x+r-xx-1:(xx>=x+w-r?xx-(x+w-r):0);
                int dy=yy<y+r?y+r-yy-1:(yy>=y+h-r?yy-(y+h-r):0);
                if(dx*dx+dy*dy<=r*r)pixel(xx,yy,color);
            }
    }
    void fillTriangle(int ax,int ay,int bx,int by,int cx,int cy,int color){
        auto edge=[](int x,int y,int x1,int y1,int x2,int y2){return (x-x1)*(y2-y1)-(y-y1)*(x2-x1);};
        for(int y=maximum(0,minimum(ay,minimum(by,cy)));y<=minimum(height-1,maximum(ay,maximum(by,cy)));y++)
            for(int x=maximum(0,minimum(ax,minimum(bx,cx)));x<=minimum(127,maximum(ax,maximum(bx,cx)));x++){
                int a=edge(x,y,ax,ay,bx,by),b=edge(x,y,bx,by,cx,cy),c=edge(x,y,cx,cy,ax,ay);
                if((a>=0&&b>=0&&c>=0)||(a<=0&&b<=0&&c<=0))pixel(x,y,color);
            }
    }
};
#include "FluxGarage_RoboEyes.h"
static Framebuffer framebuffer;
// Static zero initialization avoids an upstream member-initialization-order
// read in a stack-allocated temporary. Reset from the immutable initial copy.
static const RoboEyes<Framebuffer> pristine(framebuffer);
static RoboEyes<Framebuffer> robot(pristine);
static eyes_config previous;
static bool configured;
void eyes_engine_configure(const eyes_config *c){
    if(!configured||c->width!=previous.width)robot.setWidth(c->width,c->width);
    /* Gaze updates must not reopen a blink/closed eye by resetting its height. */
    if(!configured||c->eye_height!=previous.eye_height)robot.setHeight(c->eye_height,c->eye_height);
    if(!configured||c->radius!=previous.radius)robot.setBorderradius(c->radius,c->radius);
    if(!configured||c->spacing!=previous.spacing)robot.setSpacebetween(c->spacing);
    robot.setMood(c->mood);robot.setCuriosity(c->curious);robot.setCyclops(c->cyclops);
    robot.setSweat(c->sweat);robot.setAutoblinker(c->autoblink,c->blink_interval,c->blink_variation);
    robot.setIdleMode(c->idle,c->idle_interval,c->idle_variation);
    robot.setHFlicker(c->horizontal_flicker>0,c->horizontal_flicker);
    robot.setVFlicker(c->vertical_flicker>0,c->vertical_flicker);
    robot.eyeLxNext=(128-(c->cyclops?c->width:2*c->width+c->spacing))*c->x/1000;
    robot.eyeLyNext=(c->height-c->eye_height)*c->y/1000;
    previous=*c;configured=true;
}
void eyes_engine_begin(const eyes_config *c,uint32_t now){
    clock_ms=now;framebuffer.height=c->height;
    robot=pristine;configured=false;
    robot.begin(128,c->height,8);eyes_engine_configure(c);robot.open();
}
void eyes_engine_action(unsigned a){
    switch(a){
    case EYES_BLINK:robot.blink();break;
    case EYES_WINK_LEFT:robot.blink(1,0);break;
    case EYES_WINK_RIGHT:robot.blink(0,1);break;
    case EYES_OPEN:robot.open();break;
    case EYES_CLOSE:robot.close();break;
    case EYES_LAUGH:robot.anim_laugh();break;
    case EYES_CONFUSED:robot.anim_confused();break;
    }
}
const uint8_t *eyes_engine_frame(uint32_t now){clock_ms=now;robot.drawEyes();return framebuffer.pixels;}
const uint8_t *eyes_engine_alignment(){
    framebuffer.clearDisplay();int height=framebuffer.height;
    for(int x=0;x<128;x++){framebuffer.pixel(x,0,1);framebuffer.pixel(x,height-1,1);}
    for(int y=0;y<height;y++){framebuffer.pixel(0,y,1);framebuffer.pixel(127,y,1);}
    for(int x=8;x<120;x++)framebuffer.pixel(x,height/2,1);
    for(int y=8;y<height-8;y++)framebuffer.pixel(64,y,1);
    /* Distinct edge marks reveal the two-column SH1106 offset. */
    for(int y=3;y<height-3;y+=4){framebuffer.pixel(2,y,1);framebuffer.pixel(125,y,1);}
    return framebuffer.pixels;
}
