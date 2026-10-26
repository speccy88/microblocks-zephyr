/* SPDX-License-Identifier: MIT */
/* Bounded host-only feature export for synthetic fixtures, never a mic API. */
#include "kws_features.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
int main(int argc,char **argv)
{
 if(argc!=3)return 2;
 FILE *in=fopen(argv[1],"rb");if(!in)return 2;
 if(fseek(in,0,SEEK_END))return 2;long bytes=ftell(in);
 if(bytes<=0||bytes>256000||bytes%2||fseek(in,0,SEEK_SET))return 2;
 int16_t *pcm=malloc((size_t)bytes);if(!pcm)return 2;
 if(fread(pcm,1,(size_t)bytes,in)!=(size_t)bytes)return 2;fclose(in);
 FILE *out=fopen(argv[2],"wb");if(!out)return 2;
 struct kw_frontend f;struct kw_allocator allocator={malloc,free};
 if(!kw_features_begin(&f,allocator))return 3;
 size_t frames=(size_t)bytes/2,pos=0;uint32_t hash=2166136261u;
 while(pos<frames){
  size_t n=frames-pos;if(n>257)n=257;size_t used=0;int8_t feature[40];
  int r=kw_features_push(&f,pcm+pos,n,&used,feature);if(r<0||!used||used>n)return 3;
  pos+=used;if(r){
   if(fwrite(feature,1,40,out)!=40)return 3;
   for(unsigned i=0;i<40;i++)hash=(hash^(uint8_t)feature[i])*16777619u;
  }
 }
 unsigned features=f.features;size_t peak=f.peak_requested;
 kw_features_end(&f);memset(pcm,0,(size_t)bytes);free(pcm);fclose(out);
 if(f.requested)return 3;
 printf("{\"result\":\"PASS\",\"scope\":\"offline synthetic PCM to trained features; no inference or microphone\",\"frames\":%zu,\"features\":%u,\"feature_fnv1a\":\"%08x\",\"peak_requested_bytes\":%zu}\n",frames,features,hash,peak);
 return 0;
}
