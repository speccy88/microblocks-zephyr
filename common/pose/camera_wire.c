/* SPDX-License-Identifier: MIT */
#include "camera_wire.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t value){for(unsigned i=0;i<4;i++)p[i]=value>>(8*i);}
bool pose_camera_decode(const uint8_t *p,size_t n,pose_camera_request *out){
    if(!p||!out||n!=24||memcmp(p,"P4CP",4)||p[4]!=1||p[5]>4||p[6]||p[7]||p[22]||p[23])return false;
    pose_camera_request r={p[5],get32(p+8),get32(p+12),get32(p+16),(uint16_t)(p[20]|(uint16_t)p[21]<<8)};
    if(r.count>512||r.session>0x1fffffffu||(r.operation&& !r.session))return false;
    if(r.operation!=3&&(r.offset||r.count))return false;
    if(r.operation==3&&(!r.count||r.offset>10368||r.count>10368-r.offset))return false;
    *out=r;return true;
}
void pose_camera_reply(uint8_t *p,const pose_camera_request *r,uint8_t status,uint8_t state){
    memcpy(p,"P4CP",4);p[4]=1;p[5]=r->operation;p[6]=status;p[7]=state;put32(p+8,r->request);put32(p+12,r->session);
}
