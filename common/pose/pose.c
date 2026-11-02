/* SPDX-License-Identifier: MIT */
#include "pose.h"
#include <string.h>
static uint16_t u16(const uint8_t *p){return p[0]|(uint16_t)p[1]<<8;}
static uint32_t u32(const uint8_t *p){return u16(p)|(uint32_t)u16(p+2)<<16;}
bool pose_receive(pose_state *s,const uint8_t *p,size_t n,uint64_t now){
    if(!s||!p||n!=20||memcmp(p,"P4PS",4)||p[4]!=1||p[5]>1||p[6]>POSE_WAVE||p[7]||p[18]||p[19])return false;
    uint32_t seq=u32(p+8);uint16_t x=u16(p+12),y=u16(p+14),confidence=u16(p+16);
    if(x>1000||y>1000||confidence>1000||(p[5]&&confidence<500)||(!p[5]&&(p[6]||confidence||x!=500||y!=500)))return false;
    /* A fresh link may restart its counter after the 1s receiver lease expires. */
    if(s->received&&now>=s->updated&&now-s->updated<=1000&&
       (seq==s->sequence||(uint32_t)(seq-s->sequence)>=0x80000000u))return false;
    *s=(pose_state){true,p[5]!=0,seq,now,x,y,confidence,p[6]};return true;
}
bool pose_fresh(const pose_state *s,uint64_t now){return s&&s->received&&s->visible&&now>=s->updated&&now-s->updated<=1000;}
const char *pose_gesture(unsigned g){static const char *const names[]={"neutral","left hand up","right hand up","both hands up","arms out","wave"};return g<=POSE_WAVE?names[g]:"unknown";}
