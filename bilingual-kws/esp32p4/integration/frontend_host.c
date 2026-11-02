/* SPDX-License-Identifier: MIT */
/* Host wrapper around the firmware adapter. Serialized by each Python process. */
#include "kws_features.h"
#include <stdlib.h>
#include <string.h>
static struct kw_frontend streaming_frontend;
int kws_stream_begin(void) {
    return kw_features_begin(&streaming_frontend,(struct kw_allocator){malloc,free});
}
void kws_stream_end(void) {kw_features_end(&streaming_frontend);}
int kws_stream_push(const int16_t *pcm,unsigned samples,int8_t *out,unsigned capacity) {
    unsigned pos=0,frames=0;
    if(!pcm||!out||!capacity||samples>16000)return -1;
    while(pos<samples) {
        size_t used=0,count=samples-pos;if(count>257)count=257;
        int8_t row[40];int result=kw_features_push(&streaming_frontend,pcm+pos,count,&used,row);
        if(result<0||!used)return -2;
        pos+=used;
        if(result){if(frames>=capacity)return -3;memcpy(out+40*frames,row,40);frames++;}
    }
    return (int)frames;
}
int kws_extract(const int16_t *pcm, unsigned samples, int8_t *out, unsigned capacity) {
    struct kw_frontend f;
    if (!pcm || !out || !samples || samples > 128000 || !capacity) return -1;
    if (!kw_features_begin(&f, (struct kw_allocator){malloc, free})) return -2;
    unsigned pos=0, frames=0;
    while (pos<samples) {
        size_t used=0, count=samples-pos;
        if (count>257) count=257;
        int8_t row[40];
        int result=kw_features_push(&f,pcm+pos,count,&used,row);
        if (result<0 || !used) {kw_features_end(&f); return -3;}
        pos+=used;
        if (result) {
            if(frames>=capacity) {kw_features_end(&f);return -4;}
            memcpy(out+frames*40,row,40); frames++;
        }
    }
    kw_features_end(&f);
    return f.requested ? -5 : (int)frames;
}
