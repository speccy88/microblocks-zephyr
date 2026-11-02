/* SPDX-License-Identifier: MIT */
#include "eyes.h"
extern "C" {
#include "pose.h"
#include "camera_wire.h"
#include "face.h"
#include "serial_rate.h"
}
#include <cassert>
#include <cstring>
#include <cstdio>
#include <initializer_list>
struct Bus {unsigned calls=0,data=0;int fail=-1;uint8_t column=255;};
static int write(void *ctx,uint8_t address,const uint8_t *data,size_t bytes){
    Bus &b=*static_cast<Bus *>(ctx);assert(address==0x3c||address==0x3d);
    assert(bytes>=2&&bytes<=17);assert(data[0]==0||data[0]==0x40);
    if((int)b.calls++==b.fail)return -5;
    if(data[0]==0x40){assert(bytes==17);b.data+=16;}
    if(bytes==4&&data[0]==0){assert((data[1]&0xf8)==0xb0);b.column=data[2];}
    return 0;
}
static uint32_t hash(const uint8_t *p,size_t bytes){uint32_t h=2166136261u;for(size_t i=0;i<bytes;i++)h=(h^p[i])*16777619u;return h;}
static unsigned lit(const uint8_t *p){unsigned total=0;for(unsigned i=0;i<1024;i++)for(unsigned bit=0;bit<8;bit++)total+=(p[i]>>bit)&1;return total;}
static int probe(void *ctx,uint8_t address){assert(address==0x3c||address==0x3d);return (*(unsigned *)ctx&(address==0x3c?1:2))?0:-1;}
static int apply_rate(uint32_t baud,void *context){*(uint32_t *)context=baud;return 0;}
int main(){
    assert(eyes_normalize_address(0x78)==0x3c);assert(eyes_normalize_address(0x7a)==0x3d);
    assert(eyes_normalize_address(0x3c)==0x3c);assert(eyes_normalize_address(0x79)==-1);
    for(unsigned mask=0;mask<4;mask++)assert(eyes_find_address(probe,&mask)==(mask==3?-1:(mask==1?0x3c:(mask==2?0x3d:0))));
    uint8_t blank[1024]={0};
    unsigned render_cases=0;
    for(int controller=0;controller<2;controller++)for(int height:{32,64}){
        eyes_config c=eyes_defaults(height,controller,0x3c);Bus b;
        if(controller&&height==32){assert(!eyes_config_valid(&c));continue;}
        assert(eyes_oled_init(&c,write,&b)==0);
        eyes_engine_begin(&c,0);
        const uint8_t *alignment=eyes_engine_alignment();
        for(unsigned y=0;y<(unsigned)height;y++){assert(alignment[(y/8)*128]&(1u<<(y%8)));assert(alignment[(y/8)*128+127]&(1u<<(y%8)));}
        for(unsigned x=0;x<128;x++){assert(alignment[x]&1);assert(alignment[(height/8-1)*128+x]&128);}
        for(unsigned mood=0;mood<4;mood++)for(int x:{0,500,1000}){
            c.mood=mood;c.x=x;c.y=1000-x;eyes_engine_configure(&c);
            uint32_t sum=0;
            for(unsigned t=0;t<20;t++)sum=hash(eyes_engine_frame(t*125),128*height/8);
            assert(sum!=hash(blank,128*height/8));render_cases++;
        }
        for(unsigned action=1;action<=7;action++){eyes_engine_action(action);for(unsigned t=0;t<25;t++)eyes_engine_frame(3000+t*125);}
        const uint8_t *frame=eyes_engine_frame(7000);
        for(unsigned page=0;page<(unsigned)height/8;page++)assert(eyes_oled_page(&c,page,frame,write,&b)==0);
        assert(b.data==(unsigned)128*height/8);assert(b.column==(controller?2:0));
        assert(eyes_oled_page(&c,height/8,frame,write,&b)!=0);
        for(int fail=0;fail<9;fail++){Bus failed;failed.fail=fail;assert(eyes_oled_page(&c,0,frame,write,&failed)==-5);assert(failed.calls==(unsigned)fail+1);}
        c.cyclops=c.curious=c.sweat=true;c.horizontal_flicker=c.vertical_flicker=8;
        eyes_engine_configure(&c);for(unsigned t=0;t<100;t++)eyes_engine_frame(8000+t*125);
    }
    eyes_config c=eyes_defaults(64,0,0x18);assert(!eyes_config_valid(&c));c.address=0x3c;c.width=60;assert(!eyes_config_valid(&c));
    c=eyes_defaults(64,0,0x3c);c.autoblink=false;eyes_engine_begin(&c,0);
    for(unsigned t=0;t<20;t++)eyes_engine_frame(t*125);
    unsigned opened=lit(eyes_engine_frame(3000));assert(opened>1000);
    eyes_engine_action(EYES_CLOSE);
    for(unsigned t=0;t<20;t++){c.x=100+t*20;eyes_engine_configure(&c);eyes_engine_frame(4000+t*125);}
    assert(lit(eyes_engine_frame(7000))<opened/8); /* tracking must not cancel close */
    eyes_engine_action(EYES_OPEN);for(unsigned t=0;t<20;t++)eyes_engine_frame(8000+t*125);
    assert(lit(eyes_engine_frame(11000))>opened/2);
    uint8_t packet[20]={'P','4','P','S',1,1,3,0,1,0,0,0,0xf4,1,0xf4,1,0x84,3,0,0};
    pose_state p={};assert(pose_receive(&p,packet,20,100));assert(pose_fresh(&p,1100));assert(!pose_fresh(&p,1101));
    assert(!pose_receive(&p,packet,20,101));packet[8]=2;assert(pose_receive(&p,packet,20,102));
    pose_state old=p;
    for(unsigned i=0;i<20;i++){
        uint8_t bad[20];memcpy(bad,packet,20);bad[8]=3;bad[i]=255;
        if((i>=8&&i<=12)||i==14)continue;
        assert(!pose_receive(&p,bad,20,103));assert(!memcmp(&p,&old,sizeof(p)));
    }
    for(unsigned n=0;n<30;n++)if(n!=20)assert(!pose_receive(&p,packet,n,104));
    packet[8]=1;assert(pose_receive(&p,packet,20,1200)); /* expired sender lease */
    packet[5]=0;assert(!pose_receive(&p,packet,20,2400));
    packet[6]=packet[16]=packet[17]=0;assert(pose_receive(&p,packet,20,2400));assert(!pose_fresh(&p,2400));
    uint8_t rpc[24]={'P','4','C','P',1,0,0,0,7,0,0,0,1,0,0,0};pose_camera_request request;
    for(unsigned op=0;op<=4;op++){rpc[5]=op;rpc[20]=op==3?16:0;assert(pose_camera_decode(rpc,24,&request));assert(request.operation==op&&request.request==7&&request.session==1);}
    for(unsigned index:{0u,1u,2u,3u,4u,5u,6u,7u,22u,23u}){
        uint8_t bad[24];memcpy(bad,rpc,24);bad[index]=255;assert(!pose_camera_decode(bad,24,&request));
    }
    rpc[5]=3;rpc[20]=1;rpc[21]=2;assert(!pose_camera_decode(rpc,24,&request));
    rpc[20]=1;rpc[21]=0;memset(rpc+16,255,4);assert(!pose_camera_decode(rpc,24,&request));
    for(unsigned n=0;n<32;n++)if(n!=24)assert(!pose_camera_decode(rpc,n,&request));
    face_state f={};uint8_t fc[20]={'P','4','F','C',1,1,1,2,1,0,0,0,0xf4,1,0xf4,1,2,3,0,0};
    assert(face_receive(&f,fc,20,100));assert(face_fresh(&f,2100));assert(!face_fresh(&f,2101));
    assert(!face_receive(&f,fc,20,101));fc[8]=2;assert(face_receive(&f,fc,20,102));
    for(unsigned i:{0u,1u,2u,3u,4u,5u,6u,7u,12u,13u,14u,15u,16u,17u,18u,19u}){
        uint8_t bad[20];memcpy(bad,fc,20);bad[8]=3;bad[i]=255;
        /* Low coordinate bytes alone can still encode a valid coordinate. */
        if(i==12||i==14)continue;
        assert(!face_receive(&f,bad,20,103));
    }
    eyes_attention att={};attention_enable(&att,true,2,0);
    face_state empty={};assert(attention_update(&att,&empty,0)==ATTENTION_WANDER);
    assert(attention_update(&att,&empty,8000)==ATTENTION_DROWSY);
    assert(attention_update(&att,&empty,12000)==ATTENTION_SLEEP);
    fc[8]=3;assert(face_receive(&f,fc,20,13000));
    assert(attention_update(&att,&f,13000)==ATTENTION_HAPPY);
    assert(attention_update(&att,&empty,15000)==ATTENTION_HOLD);
    assert(attention_update(&att,&empty,16001)==ATTENTION_WANDER);
    attention_enable(&att,true,0,17000);assert(attention_update(&att,&empty,17000)==ATTENTION_SLEEP);
    assert(attention_update(&att,&f,17000)==ATTENTION_SLEEP); /* stale cannot wake */
    attention_enable(&att,false,0,18000);assert(attention_update(&att,&f,18000)==ATTENTION_OFF);
    serial_rate rate;serial_rate_init(&rate);uint32_t applied=115200;
    serial_rate_request rq={1,123,921600};assert(serial_rate_command(&rate,&rq,100)==0);
    serial_rate_poll(&rate,139,true,apply_rate,&applied);assert(applied==115200);
    serial_rate_poll(&rate,140,false,apply_rate,&applied);assert(applied==115200);
    serial_rate_poll(&rate,141,true,apply_rate,&applied);assert(applied==921600&&rate.state==SERIAL_CONFIRM);
    rq.operation=2;rq.token=999;assert(serial_rate_command(&rate,&rq,150)==1);
    rq.token=123;assert(serial_rate_command(&rate,&rq,151)==0&&rate.state==SERIAL_FAST);
    rq.operation=4;rq.baud=460800;assert(serial_rate_command(&rate,&rq,200)==1);
    serial_rate_poll(&rate,5152,true,apply_rate,&applied);assert(applied==115200&&rate.state==SERIAL_BASE);
    rq=(serial_rate_request){1,321,460800};assert(serial_rate_command(&rate,&rq,6000)==0);
    serial_rate_poll(&rate,6040,true,apply_rate,&applied);assert(applied==460800);
    serial_rate_poll(&rate,7840,true,apply_rate,&applied);assert(applied==115200); /* no confirm */
    rq=(serial_rate_request){1,333,1000000};assert(serial_rate_command(&rate,&rq,8000)==1);
    uint8_t rate_wire[16]={'P','4','B','R',1,1,0,0,1,0,0,0,0,16,14,0};
    assert(serial_rate_decode(rate_wire,16,&rq));rate_wire[6]=1;assert(!serial_rate_decode(rate_wire,16,&rq));
    rq=(serial_rate_request){1,456,921600};assert(serial_rate_command(&rate,&rq,9000)==0);
    serial_rate_poll(&rate,9040,true,apply_rate,&applied);rq.operation=2;assert(serial_rate_command(&rate,&rq,9050)==0);
    rq.operation=4;assert(serial_rate_command(&rate,&rq,13000)==0);
    serial_rate_poll(&rate,17000,true,apply_rate,&applied);assert(applied==921600); /* heartbeat renewed */
    rq.operation=3;rq.baud=115200;rq.token=999;assert(serial_rate_command(&rate,&rq,17001)==1);
    rq.token=456;assert(serial_rate_command(&rate,&rq,17002)==0);
    serial_rate_poll(&rate,17041,true,apply_rate,&applied);assert(applied==921600);
    serial_rate_poll(&rate,17042,true,apply_rate,&applied);assert(applied==115200);
    printf("{\"render_cases\":%u,\"oled_failure_injection\":true,\"close_during_tracking\":true,\"pose_wire\":true,\"face_wire\":true,\"attention_transitions\":true,\"hardware_tested\":false}\n",render_cases);
}
