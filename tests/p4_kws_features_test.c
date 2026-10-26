/* SPDX-License-Identifier: MIT */
#include "kws_features.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned calls,fail_after=~0u,active;
static void *allocate(size_t n){if(calls++==fail_after)return NULL;void *p=malloc(n);if(p)active++;return p;}
static void release(void *p){assert(active);active--;free(p);}
static struct kw_allocator allocator={allocate,release};
static int16_t pcm[16000];
static int8_t golden[100*40],actual[100*40];
static size_t collect(struct kw_frontend *f,size_t chunk,int8_t *out)
{
 size_t pos=0,features=0,steps=0;
 while(pos<16000){
  size_t n=16000-pos;if(n>chunk)n=chunk;size_t used=0;
  int result=kw_features_push(f,pcm+pos,n,&used,out+features*40);
  assert(result>=0&&used>0&&used<=n);pos+=used;features+=result;
  assert(features<100&&++steps<=16000);
 }
 return features;
}
int main(void)
{
 uint32_t random=1234567;
 for(unsigned i=0;i<16000;i++){random=random*1664525u+1013904223u;pcm[i]=(int16_t)((int)(random>>16)/4-8192);}
 struct kw_frontend f,other;
 assert(!kw_features_begin(NULL,allocator));assert(kw_features_begin(&f,allocator));
 assert(!kw_features_begin(&other,allocator));
 unsigned allocations=f.allocations_made;size_t peak=f.peak_requested;
 int8_t feature[40];size_t used=123;
 assert(kw_features_push(&f,NULL,1,&used,feature)==-1&&used==0);
 assert(kw_features_push(&f,pcm,0,&used,feature)==-1&&used==0);
 assert(kw_features_push(&f,pcm,16001,&used,feature)==-1&&used==0);
 size_t n=collect(&f,16000,golden);assert(n==98&&f.features==98);
 for(size_t chunk=1;chunk<=16000;chunk=chunk==1?7:chunk==7?160:chunk==160?479:16000){
  kw_features_reset(&f);size_t count=collect(&f,chunk,actual);
  assert(count==n&&!memcmp(golden,actual,n*40));assert(f.allocations_made==allocations);
  if(chunk==16000)break;
 }
 kw_features_end(&f);assert(!f.live&&f.requested==0&&active==0);
 assert(kw_features_push(&f,pcm,160,&used,feature)==-1);
 for(unsigned failure=0;failure<allocations;failure++){
  calls=0;fail_after=failure;assert(!kw_features_begin(&f,allocator));
  assert(!f.live&&f.requested==0&&active==0);
 }
 calls=0;fail_after=~0u;assert(kw_features_begin(&f,allocator));kw_features_end(&f);
 assert(!active&&peak>0&&peak<KW_FRONTEND_BUDGET);
 uint32_t hash=2166136261u;for(size_t i=0;i<n*40;i++)hash=(hash^(uint8_t)golden[i])*16777619u;
 printf("{\"result\":\"PASS\",\"scope\":\"offline trained audio frontend; no model or microphone execution\",\"features\":%zu,\"feature_fnv1a\":\"%08x\",\"peak_requested_bytes\":%zu,\"allocations\":%u,\"injected_allocation_failures\":%u,\"split_buffer_sizes\":[1,7,160,479,16000],\"sanitizers\":\"ASan+UBSan\"}\n",n,hash,peak,allocations,allocations);
}
