/* SPDX-License-Identifier: MIT */
#include "audio_store.h"
#include "image_store.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    assert(!audio_create(0) && !audio_create(AUDIO_MAX_FRAMES+1));
    int h=audio_create(4);assert(h>0 && !image_get(h));
    int im=image_create(1,1,1);assert(im && !audio_get(im));image_release(im);
    int16_t known[]={-32768,32767,0,-1};memcpy(audio_get(h)->samples,known,sizeof(known));
    uint8_t bytes[8];assert(audio_read(h,0,bytes,8));
    assert(!memcmp(bytes,(uint8_t[]){0,128,255,127,0,0,255,255},8));
    assert(!audio_read(h,7,bytes,2) && !audio_read(h,(size_t)-1,bytes,1));
    unsigned peak,rms;assert(audio_stats(h,&peak,&rms) && peak==32768 && rms==23170);
    float f[4];assert(audio_copy_float(h,f,4) && f[0]==-1.0f && f[1]>0.9999f && f[2]==0);
    assert(!audio_copy_float(h,f,3));assert(audio_release(h) && !audio_get(h) && !audio_release(h));
    for(unsigned i=0;i<10000;i++){h=audio_create(32);assert(h && audio_release(h) && !audio_get(h));}
    int a=audio_create(AUDIO_MAX_FRAMES),b=audio_create(AUDIO_MAX_FRAMES);
    assert(a && b && !audio_create(1) && audio_bytes_used()==AUDIO_BUDGET);
    audio_release_all();assert(!audio_count() && !audio_bytes_used());
    puts("{\"result\":\"PASS\",\"reuse_cycles\":10000,\"pcm_extremes_rms_le_float\":true,\"typed_handle_separation\":true,\"capacity_bounds_lifecycle\":true}");
}
