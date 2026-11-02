/* SPDX-License-Identifier: MIT */
#include "face.h"
#include <string.h>
static unsigned u16(const uint8_t *p){return (unsigned)p[0]|(unsigned)p[1]<<8;}
static uint32_t u32(const uint8_t *p){return (uint32_t)u16(p)|(uint32_t)u16(p+2)<<16;}
bool face_fresh(const face_state *s,int64_t now){return s&&s->received&&s->visible&&now>=s->received_ms&&now-s->received_ms<=2000;}
bool face_receive(face_state *s,const uint8_t *p,size_t n,int64_t now){
    if(!s||!p||n!=20||memcmp(p,"P4FC",4)||p[4]!=1||p[5]>1||p[6]>2||p[7]>2||p[16]>3||p[17]>3||u16(p+18))return false;
    unsigned x=u16(p+12),y=u16(p+14);uint32_t sequence=u32(p+8);
    if(x>1000||y>1000||(!p[5]&&(x!=500||y!=500||p[6]||p[7]||p[16]||p[17])))return false;
    if(s->received&&now>=s->received_ms&&now-s->received_ms<=2000){
        uint32_t advance=sequence-s->sequence;
        if(!advance||advance>=0x80000000u)return false;
    }
    *s=(face_state){.received=true,.visible=p[5],.left_eye=p[6],.right_eye=p[7],.head=p[16],.look=p[17],.x=x,.y=y,.sequence=sequence,.received_ms=now};
    return true;
}
void attention_enable(eyes_attention *s,bool enabled,unsigned mode,int64_t now){
    *s=(eyes_attention){.enabled=enabled,.idle_mode=mode,.state=ATTENTION_OFF,.x=500,.y=500,.idle_since=now};
}
unsigned attention_update(eyes_attention *s,const face_state *face,int64_t now){
    if(!s->enabled)return s->state=ATTENTION_OFF;
    if(face_fresh(face,now)){
        s->seen=true;s->last_seen=face->received_ms;s->x=face->x;s->y=face->y;
        return s->state=ATTENTION_HAPPY;
    }
    if(s->seen&&now>=s->last_seen&&now-s->last_seen<=3000)return s->state=ATTENTION_HOLD;
    if(s->seen){s->seen=false;s->idle_since=now;}
    unsigned phase=now>=s->idle_since?(unsigned)((now-s->idle_since)%20000):0;
    if(s->idle_mode==0)return s->state=ATTENTION_SLEEP;
    if(s->idle_mode==1)return s->state=ATTENTION_WANDER;
    return s->state=phase<8000?ATTENTION_WANDER:(phase<12000?ATTENTION_DROWSY:ATTENTION_SLEEP);
}
const char *attention_name(unsigned s){
    static const char *const names[]={"off","looking around","sleepy","sleeping","happy, following face","waiting for face"};
    return s<sizeof(names)/sizeof(*names)?names[s]:"off";
}
