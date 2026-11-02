/* SPDX-License-Identifier: MIT */
#include "eyes_backend.h"
#include "camera_backend.h"
#include "audio_backend.h"
#include "discovery_backend.h"
#include <zephyr/kernel.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/gpio.h>
#include <stdio.h>
#include <string.h>
static const struct device *const bus=DEVICE_DT_GET(DT_NODELABEL(i2c0));
K_MUTEX_DEFINE(eyes_lock);
static struct {K_KERNEL_STACK_MEMBER(stack,4096);} memory __attribute__((section(".ext_ram.bss.eyes_stack")));
static struct k_thread thread;
static eyes_config desired;
static bool running,ready,initialized;
static bool probe_pending;
static int probed_address;
static int64_t probe_deadline;
static int probe_errors[2]={-EAGAIN,-EAGAIN};
static const struct device *const gpio=DEVICE_DT_GET(DT_NODELABEL(gpio0));
static uint32_t generation,revision;
static unsigned actions[8],head,tail;
static unsigned pose_action;
static int64_t pose_action_time;
static char message[96]="OLED not initialized; no I2C writes";
/* Pose state belongs only to the VM thread. The renderer sees copied config. */
static pose_state pose;
static face_state face;
static eyes_attention attention;
static bool following,reacting,had_person;
static unsigned last_gesture;
static bool bus_busy(void){return camera_busy()||p4_audio_busy()||p4_discovery_busy();}
static int write_oled(void *context,uint8_t address,const uint8_t *data,size_t n){
    ARG_UNUSED(context);return i2c_write(bus,data,n,address);
}
static int probe_oled(void *context,uint8_t address){
    ARG_UNUSED(context);uint8_t dummy=0;
    struct i2c_msg msg={.buf=&dummy,.len=0,.flags=I2C_MSG_WRITE|I2C_MSG_STOP};
    int result=i2c_transfer(bus,&msg,1,address);
    k_mutex_lock(&eyes_lock,K_FOREVER);probe_errors[address==0x3c?0:1]=result;k_mutex_unlock(&eyes_lock);
    return result;
}
static bool current(uint32_t g){
    k_mutex_lock(&eyes_lock,K_FOREVER);bool ok=running&&generation==g;k_mutex_unlock(&eyes_lock);return ok;
}
static void failure(uint32_t g,int error){
    k_mutex_lock(&eyes_lock,K_FOREVER);
    if(generation==g){running=ready=false;snprintf(message,sizeof(message),"OLED I2C error %d; check controller/address/wiring; initialize again",error);}
    k_mutex_unlock(&eyes_lock);
}
static void worker(void *a,void *b,void *c){
    ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);uint32_t active=0,applied=0;
    for(;;){
        k_mutex_lock(&eyes_lock,K_FOREVER);
        bool run=running,probe=probe_pending;eyes_config config=desired;uint32_t g=generation,r=revision;
        k_mutex_unlock(&eyes_lock);
        if(probe&&(k_uptime_get()>=probe_deadline||!bus_busy())){
            bool expired=k_uptime_get()>=probe_deadline;
            int found=!expired&&device_is_ready(bus)?eyes_find_address(probe_oled,NULL):0;
            k_mutex_lock(&eyes_lock,K_FOREVER);
            if(probe_pending&&generation==g){
                probed_address=found;probe_pending=false;
                if(found>0)snprintf(message,sizeof(message),"0x%02X ACK on SDA7/SCL8; controller unknown; select SSD1306 or SH1106 profile",found);
                else snprintf(message,sizeof(message),expired?"OLED probe timed out waiting for shared bus; try again when camera/audio is idle":(found<0?"Both 0x3C and 0x3D ACK; choose an address explicitly; controller unknown":"No OLED address ACK (0x3C/0x3D); check power/wiring/bus; controller unknown"));
            }
            k_mutex_unlock(&eyes_lock);continue;
        }
        if(!run||bus_busy()){k_sleep(K_MSEC(20));continue;}
        int64_t began=k_uptime_get();
        if(active!=g){
            if(!device_is_ready(bus)){failure(g,-ENODEV);continue;}
            int error=eyes_oled_init(&config,write_oled,NULL);
            if(error){failure(g,error);continue;}
            eyes_engine_begin(&config,(uint32_t)began);active=g;applied=r;
        }else if(applied!=r){eyes_engine_configure(&config);applied=r;}
        k_mutex_lock(&eyes_lock,K_FOREVER);
        /* Preserve command order; one action per frame gives each a visible tick. */
        unsigned action=0;if(running&&generation==g&&head!=tail){action=actions[tail++%8];}
        else if(running&&generation==g&&pose_action){
            if(k_uptime_get()-pose_action_time<=1000)action=pose_action;
            pose_action=0;
        }
        k_mutex_unlock(&eyes_lock);
        if(action)eyes_engine_action(action);
        const uint8_t *frame=config.alignment?eyes_engine_alignment():eyes_engine_frame((uint32_t)began);bool complete=true;
        for(unsigned page=0;page<(unsigned)config.height/8;page++){
            if(!current(g)||bus_busy()){complete=false;break;}
            int error=eyes_oled_page(&config,page,frame,write_oled,NULL);
            if(error){failure(g,error);complete=false;break;}
            k_yield();
        }
        if(complete){
            k_mutex_lock(&eyes_lock,K_FOREVER);
            if(running&&generation==g){ready=true;snprintf(message,sizeof(message),"%s profile 128x%d at 0x%02X; SDA7/SCL8; max 8 fps",config.controller?"SH1106":"SSD1306",config.height,config.address);}
            k_mutex_unlock(&eyes_lock);
        }
        int64_t remaining=125-(k_uptime_get()-began);if(remaining>0)k_sleep(K_MSEC(remaining));
    }
}
void p4_eyes_init(void){
    if(initialized)return;
    initialized=true;
    desired=eyes_defaults(64,0,0x3c);
    k_thread_create(&thread,memory.stack,K_KERNEL_STACK_SIZEOF(memory.stack),worker,NULL,NULL,NULL,9,0,K_NO_WAIT);
    k_thread_name_set(&thread,"oled_eyes");
}
bool p4_eyes_begin(int height,int controller,int address){
    eyes_config c=eyes_defaults(height,controller,address);if(!eyes_config_valid(&c))return false;
    k_mutex_lock(&eyes_lock,K_FOREVER);
    if(probe_pending){k_mutex_unlock(&eyes_lock);return false;}
    desired=c;generation++;revision++;head=tail=0;
    running=true;ready=false;pose_action=0;snprintf(message,sizeof(message),"OLED initialization queued; wait for eyes ready or check status");
    k_mutex_unlock(&eyes_lock);return true;
}
bool p4_eyes_get(eyes_config *out){k_mutex_lock(&eyes_lock,K_FOREVER);*out=desired;bool ok=running;k_mutex_unlock(&eyes_lock);return ok;}
bool p4_eyes_set(const eyes_config *c){
    if(!eyes_config_valid(c))return false;
    k_mutex_lock(&eyes_lock,K_FOREVER);bool ok=running&&c->height==desired.height&&c->controller==desired.controller&&c->address==desired.address;
    if(ok){desired=*c;revision++;}k_mutex_unlock(&eyes_lock);return ok;
}
bool p4_eyes_action(unsigned action){
    if(action<EYES_BLINK||action>EYES_CONFUSED)return false;
    k_mutex_lock(&eyes_lock,K_FOREVER);bool ok=running&&head-tail<8;
    if(ok)actions[head++%8]=action;
    k_mutex_unlock(&eyes_lock);return ok;
}
bool p4_eyes_ready(void){k_mutex_lock(&eyes_lock,K_FOREVER);bool ok=ready;k_mutex_unlock(&eyes_lock);return ok;}
bool p4_eyes_probe(void){
    k_mutex_lock(&eyes_lock,K_FOREVER);
    bool ok=!running&&!probe_pending;
    if(ok){probe_pending=true;probed_address=0;probe_deadline=k_uptime_get()+2000;generation++;snprintf(message,sizeof(message),"Address-only OLED probe queued; no controller initialization");}
    k_mutex_unlock(&eyes_lock);return ok;
}
bool p4_eyes_probing(void){k_mutex_lock(&eyes_lock,K_FOREVER);bool b=probe_pending;k_mutex_unlock(&eyes_lock);return b;}
int p4_eyes_address(void){k_mutex_lock(&eyes_lock,K_FOREVER);int address=probe_pending?0:probed_address;k_mutex_unlock(&eyes_lock);return address;}
void p4_eyes_bus_status(char *out,size_t n){
    int sda=device_is_ready(gpio)?gpio_pin_get_raw(gpio,7):-1;
    int scl=device_is_ready(gpio)?gpio_pin_get_raw(gpio,8):-1;
    k_mutex_lock(&eyes_lock,K_FOREVER);
    snprintf(out,n,"I2C0 ready=%d; SDA7=%d SCL8=%d; probe 0x3C=%d 0x3D=%d (0=ACK)",device_is_ready(bus),sda,scl,probe_errors[0],probe_errors[1]);
    k_mutex_unlock(&eyes_lock);
}
void p4_eyes_status(char *out,size_t n){k_mutex_lock(&eyes_lock,K_FOREVER);snprintf(out,n,"%s",message);k_mutex_unlock(&eyes_lock);}
void p4_eyes_stop(void){
    following=reacting=had_person=false;
    attention_enable(&attention,false,0,k_uptime_get());
    k_mutex_lock(&eyes_lock,K_FOREVER);running=ready=probe_pending=false;generation++;head=tail=0;pose_action=0;
    snprintf(message,sizeof(message),"Eyes stopped; last OLED frame retained; initialize to resume");k_mutex_unlock(&eyes_lock);
}
void p4_pose_message(int type,int bytes,const char *body){
    if(type==210&&bytes==20)pose_receive(&pose,(const uint8_t *)body,bytes,k_uptime_get());
    if(type==212&&bytes==20)face_receive(&face,(const uint8_t *)body,bytes,k_uptime_get());
}
void p4_pose_reset(void){memset(&pose,0,sizeof(pose));memset(&face,0,sizeof(face));}
face_state p4_face_snapshot(void){face_state s=face;if(!face_fresh(&s,k_uptime_get())){s.visible=false;s.x=s.y=500;s.left_eye=s.right_eye=s.head=s.look=0;}return s;}
void p4_attention_enable(bool enabled,unsigned mode){attention_enable(&attention,enabled,mode,k_uptime_get());}
const char *p4_attention_status(void){return attention_name(attention.state);}
pose_state p4_pose_snapshot(void){pose_state s=pose;if(!pose_fresh(&s,k_uptime_get())){s.visible=false;s.x=s.y=500;s.gesture=POSE_NEUTRAL;s.confidence=0;}return s;}
void p4_pose_follow(bool follow,bool react){
    following=follow;reacting=follow&&react;had_person=false;last_gesture=99;
    k_mutex_lock(&eyes_lock,K_FOREVER);pose_action=0;k_mutex_unlock(&eyes_lock);
    if(follow){eyes_config c;if(p4_eyes_get(&c)){c.idle=false;p4_eyes_set(&c);}}
}
void p4_eyes_poll(void){
    if(attention.enabled){
        eyes_config c;if(!p4_eyes_get(&c))return;
        unsigned previous=attention.state,state=attention_update(&attention,&face,k_uptime_get());
        bool awake=state==ATTENTION_HAPPY||state==ATTENTION_HOLD;
        c.idle=state==ATTENTION_WANDER;c.autoblink=state!=ATTENTION_SLEEP;
        c.mood=awake?3:((state==ATTENTION_SLEEP||state==ATTENTION_DROWSY)?1:0);
        c.x=awake?attention.x:500;c.y=awake?attention.y:500;c.curious=false;
        if(previous!=state){
            /* Latest policy transition wins over an obsolete unrendered pose action. */
            k_mutex_lock(&eyes_lock,K_FOREVER);
            pose_action=state==ATTENTION_SLEEP?EYES_CLOSE:EYES_OPEN;pose_action_time=k_uptime_get();
            k_mutex_unlock(&eyes_lock);
        }
        pose_state p=p4_pose_snapshot();
        c.curious=awake&&reacting&&p.visible&&p.gesture==POSE_ARMS_OUT;
        if(awake&&reacting&&p.visible&&p.gesture!=last_gesture){
            unsigned a=p.gesture==POSE_WAVE||p.gesture==POSE_BOTH_UP?EYES_LAUGH:
                (p.gesture==POSE_LEFT_UP?EYES_WINK_LEFT:(p.gesture==POSE_RIGHT_UP?EYES_WINK_RIGHT:0));
            if(a&&previous==state){k_mutex_lock(&eyes_lock,K_FOREVER);pose_action=a;pose_action_time=k_uptime_get();k_mutex_unlock(&eyes_lock);}
        }
        last_gesture=p.visible?p.gesture:99;
        eyes_config before;if(p4_eyes_get(&before)&&memcmp(&before,&c,sizeof(c)))p4_eyes_set(&c);
        return;
    }
    if(!following)return;
    pose_state p=p4_pose_snapshot();eyes_config c;if(!p4_eyes_get(&c))return;
    int x=p.visible?p.x:500,y=p.visible?p.y:500;
    bool changed=c.x!=x||c.y!=y||c.idle;c.x=x;c.y=y;c.idle=false;
    if(reacting&&(p.gesture!=last_gesture||p.visible!=had_person)){
        c.mood=p.gesture==POSE_BOTH_UP||p.gesture==POSE_WAVE?3:(p.gesture==POSE_ARMS_OUT?2:0);
        c.curious=p.gesture==POSE_LEFT_UP||p.gesture==POSE_RIGHT_UP;changed=true;
        k_mutex_lock(&eyes_lock,K_FOREVER);
        pose_action=0;pose_action_time=k_uptime_get();
        if(p.visible&&p.gesture==POSE_WAVE)pose_action=EYES_LAUGH;
        if(p.visible&&p.gesture==POSE_LEFT_UP)pose_action=EYES_WINK_LEFT;
        if(p.visible&&p.gesture==POSE_RIGHT_UP)pose_action=EYES_WINK_RIGHT;
        k_mutex_unlock(&eyes_lock);
    }
    if(changed)p4_eyes_set(&c);
    last_gesture=p.gesture;had_person=p.visible;
}
