/* SPDX-License-Identifier: MIT */
#include "serial_rate.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=v>>(8*i);}
void serial_rate_init(serial_rate *s){*s=(serial_rate){.baud=115200,.target=115200};}
bool serial_rate_decode(const uint8_t *p,size_t n,serial_rate_request *r){
    if(!p||!r||n!=16||memcmp(p,"P4BR",4)||p[4]!=1||p[5]>4||p[6]||p[7])return false;
    *r=(serial_rate_request){p[5],get32(p+8),get32(p+12)};
    return r->operation==0?(r->baud==0):(r->token!=0);
}
unsigned serial_rate_command(serial_rate *s,const serial_rate_request *r,uint64_t now){
    if(r->operation==0)return 0;
    if(r->operation==1){
        if(r->baud!=460800&&r->baud!=921600)return 1;
        if(s->state!=SERIAL_BASE)return 2;
        s->state=SERIAL_SWITCHING;s->target=r->baud;s->token=r->token;s->switch_at=now+40;s->expires=now+1800;return 0;
    }
    if(r->operation==3&&s->state==SERIAL_BASE&&r->baud==115200)return 0;
    if(r->token!=s->token||now>=s->expires)return 1;
    if(r->operation==2){
        if((s->state!=SERIAL_CONFIRM&&s->state!=SERIAL_FAST)||r->baud!=s->baud)return 1;
        s->state=SERIAL_FAST;s->expires=now+5000;return 0;
    }
    if(r->operation==3){
        if(s->state!=SERIAL_FAST||r->baud!=115200)return 1;
        s->state=SERIAL_SWITCHING;s->target=115200;s->switch_at=now+40;return 0;
    }
    if(r->operation==4&&s->state==SERIAL_FAST&&r->baud==s->baud){s->expires=now+5000;return 0;}
    return 1;
}
void serial_rate_poll(serial_rate *s,uint64_t now,bool tx_complete,serial_rate_apply apply,void *context){
    if(s->state!=SERIAL_BASE&&now>=s->expires){s->state=SERIAL_SWITCHING;s->target=115200;s->switch_at=now;}
    if(s->state!=SERIAL_SWITCHING||now<s->switch_at||!tx_complete)return;
    if(apply(s->target,context)){(void)apply(115200,context);serial_rate_init(s);return;}
    s->baud=s->target;
    if(s->baud==115200){serial_rate_init(s);return;}
    s->state=SERIAL_CONFIRM;s->expires=now+1800;
}
void serial_rate_reply(const serial_rate *s,const serial_rate_request *r,unsigned status,uint8_t out[16]){
    memcpy(out,"P4BR",4);out[4]=1;out[5]=r->operation;out[6]=status;out[7]=s->state;
    put32(out+8,r->token);put32(out+12,s->baud);
}
