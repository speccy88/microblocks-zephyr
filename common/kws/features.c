/* SPDX-License-Identifier: MIT */
/* Independent adapter around the pinned Apache-2.0 TFLM microfrontend.
 * Training parameters/feature quantization are data-format requirements.
 * No ESPHome implementation or RTOS glue is copied. */
#include "kws_features.h"
#include "tensorflow/lite/experimental/microfrontend/lib/frontend_util.h"
#include <stdio.h>
#include <string.h>
#include <limits.h>

static struct kw_frontend *owner;
void *kw_frontend_alloc(size_t n)
{
 struct kw_frontend *f=owner;
 if(!f||f->error||!n||n>16384||n>KW_FRONTEND_BUDGET-f->requested){if(f)f->error=1;return NULL;}
 for(unsigned i=0;i<KW_ALLOC_SLOTS;i++)if(!f->allocations[i]){
  void *p=f->allocator.alloc(n);if(!p){f->error=1;return NULL;}
  f->allocations[i]=p;f->sizes[i]=n;f->requested+=n;f->allocations_made++;
  if(f->requested>f->peak_requested)f->peak_requested=f->requested;
  return p;
 }
 f->error=1;return NULL;
}
void *kw_frontend_calloc(size_t n,size_t size)
{
 if(!size||n>SIZE_MAX/size){if(owner)owner->error=1;return NULL;}
 void *p=kw_frontend_alloc(n*size);if(p)memset(p,0,n*size);return p;
}
void kw_frontend_free(void *p)
{
 if(!p)return;
 struct kw_frontend *f=owner;if(!f)return;
 for(unsigned i=0;i<KW_ALLOC_SLOTS;i++)if(f->allocations[i]==p){
  f->requested-=f->sizes[i];memset(p,0,f->sizes[i]);f->allocator.release(p);f->allocations[i]=NULL;f->sizes[i]=0;return;
 }
 f->error=1; /* Never forward an unknown/double free to the heap. */
}
int kw_frontend_fprintf(FILE *stream,const char *format,...)
{(void)stream;(void)format;if(owner)owner->diagnostics++;return 0;}

int kw_features_begin(struct kw_frontend *f,struct kw_allocator allocator)
{
 if(!f||owner||!allocator.alloc||!allocator.release)return 0;
 memset(f,0,sizeof(*f));f->allocator=allocator;owner=f;
 struct FrontendConfig c;
 FrontendFillConfigWithDefaults(&c);
 c.window.size_ms=30;c.window.step_size_ms=10;
 c.filterbank.num_channels=40;c.filterbank.lower_band_limit=125.0f;c.filterbank.upper_band_limit=7500.0f;
 c.noise_reduction.smoothing_bits=10;c.noise_reduction.even_smoothing=0.025f;
 c.noise_reduction.odd_smoothing=0.06f;c.noise_reduction.min_signal_remaining=0.05f;
 c.pcan_gain_control.enable_pcan=1;c.pcan_gain_control.strength=0.95f;
 c.pcan_gain_control.offset=80.0f;c.pcan_gain_control.gain_bits=21;
 c.log_scale.enable_log=1;c.log_scale.scale_shift=6;
 if(!FrontendPopulateState(&c,&f->state,16000)||f->error){kw_features_end(f);return 0;}
 f->live=1;return 1;
}
int kw_features_push(struct kw_frontend *f,const int16_t *pcm,size_t n,size_t *used,int8_t out[40])
{
 if(used)*used=0;
 if(!f||owner!=f||!f->live||f->error||!used||!out||!pcm||!n||n>16000)return -1;
 struct FrontendOutput v=FrontendProcessSamples(&f->state,pcm,n,used);
 if(*used>n||!*used||v.size>40||(v.size&&v.size!=40)){f->error=1;return -1;}
 if(!v.size)return 0;
 /* Preserve the published streaming frontend's historical integer scaling
  * convention; tensor quantization metadata is checked independently. */
 for(unsigned i=0;i<40;i++){
  int32_t q=((int32_t)v.values[i]*256+333)/666-128;
  out[i]=(int8_t)(q<-128?-128:q>127?127:q);
 }
 f->features++;return 1;
}
void kw_features_reset(struct kw_frontend *f)
{if(f&&owner==f&&f->live){FrontendReset(&f->state);f->features=0;}}
void kw_features_end(struct kw_frontend *f)
{
 if(!f||owner!=f)return;
 f->live=0;FrontendFreeStateContents(&f->state);
 /* Also reclaim known allocations after a partial setup failure. */
 for(unsigned i=0;i<KW_ALLOC_SLOTS;i++)if(f->allocations[i])kw_frontend_free(f->allocations[i]);
 memset(&f->state,0,sizeof(f->state));owner=NULL;
}
