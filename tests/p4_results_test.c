/* SPDX-License-Identifier: MIT */
#include "result_store.h"
#include "image_store.h"
#include "audio_store.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static int fail_alloc;static unsigned allocations,frees;
void *media_alloc(size_t n){if(fail_alloc)return NULL;void *p=malloc(n);if(p)allocations++;return p;}
void media_free(void *p){if(p)frees++;free(p);}
int main(void)
{
 int h=image_create(320,180,IMAGE_GRAY8);assert(h);
 const image_view *v=image_get(h);
 for(unsigned y=0;y<180;y++)for(unsigned x=0;x<320;x++)v->pixels[y*320+x]=(x+3*y)%251;
 assert(media_publish(1,h)==0 && media_count()==0);
 media_session(17);uint32_t first=media_publish(1,h);assert(first);
 assert(image_release(h));const media_result *r=media_get(1,first);
 assert(r && r->kind==1 && r->width==160 && r->height==90 && r->source_width==320);
 for(unsigned y=0;y<90;y++)for(unsigned x=0;x<160;x++)assert(r->data[y*160+x]==(2*x+6*y)%251);
 uint8_t bytes[514];assert(media_read(1,first,0,bytes,512));
 assert(!media_read(2,first,0,bytes,1) && !media_read(1,first,0,bytes,513));
 assert(!media_read(1,first,r->bytes-1,bytes,2));
 h=image_create(80,80,IMAGE_RGB565);assert(h);v=image_get(h);
 for(size_t i=0;i<v->bytes;i+=2){v->pixels[i]=0xe0;v->pixels[i+1]=7;}
 uint32_t green=media_publish(2,h);assert(green && image_release(h));
 assert(media_get(1,first)->width==160 && media_get(2,green)->width==80);
 assert(media_get(2,green)->data[0]==0xe0);
 int a=audio_create(1600);assert(a);const audio_view *av=audio_get(a);
 for(unsigned i=0;i<1600;i++)av->samples[i]=i&1?32767:-32768;
 uint32_t pcm=media_publish(3,a);assert(pcm && audio_release(a));
 assert(media_read(3,pcm,0,bytes,4));
 assert(bytes[0]==0 && bytes[1]==128 && bytes[2]==255 && bytes[3]==127);
 assert(media_get(3,pcm)->rate==16000 && media_get(3,pcm)->frames==1600);
 /* Two full clips force eviction under the independent snapshot budget. */
 a=audio_create(AUDIO_MAX_FRAMES);assert(a);memset(audio_get(a)->samples,0,2*AUDIO_MAX_FRAMES);
 uint32_t p1=media_publish(4,a),p2=media_publish(5,a);assert(p1 && p2);
 assert(media_bytes_used()==4*AUDIO_MAX_FRAMES+3200 && media_bytes_used()<=MEDIA_BUDGET);
 assert(!media_get(1,first) && !media_get(2,green) && media_get(3,pcm));
 assert(audio_release(a));assert(media_get(4,p1) && media_get(5,p2));
 media_event event;unsigned count=0;
 while(media_event_peek(&event)){assert(event.session==17);count++;media_event_pop();}
 assert(count<=8 && count>=2);
 media_session(18);assert(!media_get(4,p1) && media_bytes_used()==0);
 h=image_create(1,1,IMAGE_RGB888);assert(h);memcpy(image_get(h)->pixels,"abc",3);
 fail_alloc=1;assert(!media_publish(6,h));assert(image_get(h));fail_alloc=0;
 assert(media_event_peek(&event) && event.uid==6 && event.token==0);media_event_pop();
 uint32_t previous=0;
 for(unsigned i=0;i<10000;i++){
  uint32_t token=media_publish(6,h);assert(token>previous && !media_get(6,previous));
  assert(media_read(6,token,0,bytes,3) && !memcmp(bytes,"abc",3));
  assert(media_release(6,token) && !media_release(6,token));previous=token;
 }
 assert(image_release(h));media_clear();media_session(0);
 assert(!media_count() && !media_bytes_used() && !media_event_peek(&event));
 assert(allocations==frees && !image_count() && !audio_count());
 puts("PASS: copied image/audio results, source release, UID/token isolation, eviction, bounds, allocation failure, 10000 reuse cycles");
 return 0;
}
