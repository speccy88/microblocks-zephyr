/* SPDX-License-Identifier: MIT */
#include "result_store.h"
#include "image_store.h"
#include "audio_store.h"
#include <string.h>
#include <stdlib.h>
#ifndef MEDIA_ALLOC_EXTERNAL
void *media_alloc(size_t n){return malloc(n);}
void media_free(void *p){free(p);}
#endif
static media_result slots[MEDIA_SLOTS];
static uint64_t ages[MEDIA_SLOTS],clock_count;
static uint32_t active_session,next_token=1;
static size_t used;
static media_event events[8];static unsigned event_count;
static void clear_slot(unsigned i)
{
 if(slots[i].data){memset(slots[i].data,0,slots[i].bytes);media_free(slots[i].data);used-=slots[i].bytes;}
 memset(&slots[i],0,sizeof(slots[i]));ages[i]=0;
}
void media_clear(void){for(unsigned i=0;i<MEDIA_SLOTS;i++)clear_slot(i);event_count=0;}
void media_session(uint32_t s){media_clear();active_session=s<=0x1fffffffu?s:0;}
uint32_t media_session_id(void){return active_session;}
static void announce(uint32_t uid,uint32_t token)
{
 /* A burst keeps the newest event for each site. No payload/VM object is
  * retained in this small notification queue. Expired tokens never alias. */
 for(unsigned i=0;i<event_count;i++)if(events[i].uid==uid){
  memmove(events+i,events+i+1,(event_count-i-1)*sizeof(*events));event_count--;break;
 }
 if(event_count==8){memmove(events,events+1,7*sizeof(*events));event_count--;}
 events[event_count++]=(media_event){active_session,uid,token};
}
static media_result *reserve(uint32_t uid,size_t bytes)
{
 for(unsigned i=0;i<MEDIA_SLOTS;i++)if(slots[i].uid==uid)clear_slot(i);
 if(!bytes || bytes>MEDIA_BUDGET || !next_token)return NULL;
 for(;;){
  unsigned empty=MEDIA_SLOTS,oldest=MEDIA_SLOTS;
  for(unsigned i=0;i<MEDIA_SLOTS;i++){
   if(!slots[i].data && empty==MEDIA_SLOTS)empty=i;
   if(slots[i].data && (oldest==MEDIA_SLOTS || ages[i]<ages[oldest]))oldest=i;
  }
  if(empty<MEDIA_SLOTS && bytes<=MEDIA_BUDGET-used){
   uint8_t *p=media_alloc(bytes);if(!p)return NULL;
   slots[empty]=(media_result){.token=next_token++,.uid=uid,.bytes=bytes,.data=p};
   ages[empty]=++clock_count;used+=bytes;return slots+empty;
  }
  if(oldest==MEDIA_SLOTS)return NULL;
  clear_slot(oldest);
 }
}
uint32_t media_publish(uint32_t uid,int handle)
{
 if(!active_session || !uid || uid>0x1fffffffu)return 0;
 const image_view *image=image_get(handle);const audio_view *audio=audio_get(handle);
 media_result *r=NULL;
 if(image){
  unsigned w=image->width,h=image->height;
  if(w>MEDIA_THUMB_W || h>MEDIA_THUMB_H){
   if(w*MEDIA_THUMB_H>h*MEDIA_THUMB_W){h=h*MEDIA_THUMB_W/w;w=MEDIA_THUMB_W;}
   else {w=w*MEDIA_THUMB_H/h;h=MEDIA_THUMB_H;}
   if(!w)w=1;
   if(!h)h=1;
  }
  size_t bytes=(size_t)w*h*image->format;r=reserve(uid,bytes);
  if(r){
   r->kind=1;r->width=w;r->height=h;r->source_width=image->width;r->source_height=image->height;r->format=image->format;
   for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++){
    size_t from=((size_t)(y*image->height/h)*image->width+x*image->width/w)*image->format;
    memcpy(r->data+((size_t)y*w+x)*image->format,image->pixels+from,image->format);
   }
  }
 }else if(audio && audio->channels==1 && audio->rate==AUDIO_RATE && audio->frames<=AUDIO_MAX_FRAMES){
  r=reserve(uid,(size_t)audio->frames*2);
  if(r){
   r->kind=2;r->frames=audio->frames;r->rate=audio->rate;r->channels=1;
   for(unsigned i=0;i<audio->frames;i++){uint16_t v=(uint16_t)audio->samples[i];r->data[2*i]=v;r->data[2*i+1]=v>>8;}
  }
 }else{
  for(unsigned i=0;i<MEDIA_SLOTS;i++)if(slots[i].uid==uid)clear_slot(i);
 }
 uint32_t token=r?r->token:0;announce(uid,token);return token;
}
const media_result *media_get(uint32_t uid,uint32_t token)
{
 if(!token)return NULL;
 for(unsigned i=0;i<MEDIA_SLOTS;i++)if(slots[i].data && slots[i].uid==uid && slots[i].token==token)return slots+i;
 return NULL;
}
int media_read(uint32_t uid,uint32_t token,size_t offset,uint8_t *out,size_t n)
{
 const media_result *r=media_get(uid,token);
 if(!r || !out || n>512 || offset>r->bytes || n>r->bytes-offset)return 0;
 memcpy(out,r->data+offset,n);return 1;
}
int media_release(uint32_t uid,uint32_t token)
{
 for(unsigned i=0;i<MEDIA_SLOTS;i++)if(slots[i].data && slots[i].uid==uid && slots[i].token==token){clear_slot(i);return 1;}
 return 0;
}
int media_event_peek(media_event *out){if(!event_count || !out)return 0;*out=events[0];return 1;}
void media_event_pop(void){if(event_count){event_count--;memmove(events,events+1,event_count*sizeof(*events));}}
size_t media_bytes_used(void){return used;}
unsigned media_count(void){unsigned n=0;for(unsigned i=0;i<MEDIA_SLOTS;i++)n+=slots[i].data!=NULL;return n;}
