/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "result_store.h"
#include "media_protocol.h"
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <string.h>
#include <stdio.h>
void *media_alloc(size_t n){return shared_multi_heap_aligned_alloc(SMH_REG_ATTR_EXTERNAL,64,n);}
void media_free(void *p){if(p)shared_multi_heap_free(p);}
static uint32_t get32(const unsigned char *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(unsigned char *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=n>>(8*i);}
void p4_media_poll(void)
{
 media_event event;
 if(!ideConnected()){if(media_session_id())media_session(0);return;}
 if(!hasOutputSpace(17) || !media_event_peek(&event))return;
 unsigned char body[12];put32(body,event.session);put32(body+4,event.uid);put32(body+8,event.token);
 waitAndSendMessage(209,0,sizeof(body),(char *)body);media_event_pop();
}
void p4_media_message(int type,int bytes,char *body)
{
 if(type!=208 || bytes!=28 || memcmp(body,"P4MR",4))return;
 const unsigned char *p=(unsigned char *)body;
 unsigned op=p[4],count=p[22]|(unsigned)p[23]<<8;
 uint32_t request=get32(p+6),session=get32(p+10),token=get32(p+14),offset=get32(p+18),uid=get32(p+24);
 unsigned char out[526]={0};put32(out,request);out[4]=1;out[5]=op;put32(out+6,session);put32(out+10,token);
 unsigned length=14;
 if(op==0 || op==1){
  if(op==0 || (session && session<=0x1fffffffu)){
   if(op==1)media_session(session);
   int n=snprintf((char *)out+14,sizeof(out)-14,"{\"protocol\":1,\"slots\":%u,\"budget\":%u,\"image_width\":160,\"image_height\":90,\"audio_frames\":128000,\"chunk_bytes\":512}",MEDIA_SLOTS,MEDIA_BUDGET);
   if(n>0 && n<(int)sizeof(out)-14){out[4]=0;length+=n;}
  }
 }else if(session && session==media_session_id()){
  const media_result *r=media_get(uid,token);
  if(op==2 && r){
   int n=snprintf((char *)out+14,sizeof(out)-14,
    "{\"kind\":%u,\"width\":%u,\"height\":%u,\"source_width\":%u,\"source_height\":%u,\"format\":%u,\"frames\":%u,\"rate\":%u,\"channels\":%u,\"bytes\":%u}",
    r->kind,r->width,r->height,r->source_width,r->source_height,r->format,r->frames,r->rate,r->channels,(unsigned)r->bytes);
   if(n>0 && n<(int)sizeof(out)-14){out[4]=0;length+=n;}
  }else if(op==3 && count<=512 && media_read(uid,token,offset,out+14,count)){
   out[4]=0;length+=count;
  }else if(op==4){out[4]=media_release(uid,token)?0:1;}
  else if(op==5){media_session(0);out[4]=0;}
 }
 if(hasOutputSpace(length+5))waitAndSendMessage(208,0,length,(char *)out);
}
