/* SPDX-License-Identifier: MIT */
#include "audio_store.h"
#include <stdlib.h>
#include <string.h>
#ifndef AUDIO_ALLOC_EXTERNAL
void *audio_alloc(size_t n){return malloc(n);}
void audio_free(void *p){free(p);}
#endif
typedef struct { audio_view view;unsigned generation; } slot;
static slot slots[AUDIO_SLOTS];
static size_t used;
const audio_view *audio_get(int handle)
{
    if(handle<=(int)AUDIO_HANDLE_TAG || (unsigned)handle>0x3fffffffu)return NULL;
    unsigned value=(unsigned)handle-AUDIO_HANDLE_TAG-1,index=value%AUDIO_SLOTS;
    return slots[index].view.samples && slots[index].generation==value/AUDIO_SLOTS?&slots[index].view:NULL;
}
int audio_adopt(int16_t *pcm,unsigned frames)
{
    size_t bytes=(size_t)frames*sizeof(int16_t);
    if(!pcm || !frames || frames>AUDIO_MAX_FRAMES || bytes>AUDIO_BUDGET-used)return 0;
    for(unsigned i=0;i<AUDIO_SLOTS;i++)if(!slots[i].view.samples && slots[i].generation<0x0fffffffu){
        slots[i].view=(audio_view){frames,AUDIO_RATE,1,pcm};used+=bytes;
        return (int)(AUDIO_HANDLE_TAG+slots[i].generation*AUDIO_SLOTS+i+1);
    }
    return 0;
}
int audio_create(unsigned frames)
{
    if(!frames || frames>AUDIO_MAX_FRAMES || audio_count()==AUDIO_SLOTS)return 0;
    int16_t *p=audio_alloc((size_t)frames*sizeof(int16_t));if(!p)return 0;
    int h=audio_adopt(p,frames);if(!h)audio_free(p);return h;
}
int audio_release(int handle)
{
    const audio_view *v=audio_get(handle);if(!v)return 0;
    unsigned i=((unsigned)handle-AUDIO_HANDLE_TAG-1)%AUDIO_SLOTS;
    size_t bytes=(size_t)v->frames*sizeof(int16_t);used-=bytes;
    memset(v->samples,0,bytes);audio_free(v->samples);
    memset(&slots[i].view,0,sizeof(audio_view));slots[i].generation++;return 1;
}
void audio_release_all(void)
{ for(unsigned i=0;i<AUDIO_SLOTS;i++)if(slots[i].view.samples)audio_release(AUDIO_HANDLE_TAG+slots[i].generation*AUDIO_SLOTS+i+1); }
unsigned audio_count(void){unsigned n=0;for(unsigned i=0;i<AUDIO_SLOTS;i++)n+=slots[i].view.samples!=NULL;return n;}
size_t audio_bytes_used(void){return used;}
int audio_read(int handle,size_t offset,uint8_t *out,size_t bytes)
{
    const audio_view *v=audio_get(handle);
    size_t size=v?(size_t)v->frames*2:0;
    if(!v || !out || offset>size || bytes>size-offset)return 0;
    for(size_t i=0;i<bytes;i++){size_t pos=offset+i;uint16_t sample=(uint16_t)v->samples[pos/2];out[i]=sample>>(8*(pos%2));}
    return 1;
}
int audio_copy_float(int handle,float *out,unsigned frames)
{
    const audio_view *v=audio_get(handle);if(!v || !out || frames!=v->frames)return 0;
    for(unsigned i=0;i<frames;i++)out[i]=v->samples[i]/32768.0f;
    return 1;
}
static unsigned root64(uint64_t n)
{
    uint64_t root=0,bit=UINT64_C(1)<<62;
    while(bit>n)bit>>=2;
    while(bit){if(n>=root+bit){n-=root+bit;root=(root>>1)+bit;}else root>>=1;bit>>=2;}
    return (unsigned)root;
}
int audio_stats(int handle,unsigned *peak,unsigned *rms)
{
    const audio_view *v=audio_get(handle);if(!v || !peak || !rms)return 0;
    uint64_t squares=0;unsigned max=0;
    for(unsigned i=0;i<v->frames;i++){int32_t s=v->samples[i];unsigned a=s<0?-s:s;if(a>max)max=a;squares+=(int64_t)s*s;}
    *peak=max;*rms=root64(squares/v->frames);return 1;
}
