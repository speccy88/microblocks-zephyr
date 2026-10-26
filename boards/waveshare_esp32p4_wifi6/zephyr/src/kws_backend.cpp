/* SPDX-License-Identifier: MIT */
/* Trusted builtin only. This does not broaden the custom NN import contract. */
#include "kws_backend.h"
#include "kws_features.h"
#include "kws_assets.h"
extern "C" {
#include "audio_store.h"
#include "audio_backend.h"
}
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <psa/crypto.h>
#include <tensorflow/lite/micro/micro_interpreter.h>
#include <tensorflow/lite/micro/micro_mutable_op_resolver.h>
#include <tensorflow/lite/micro/micro_resource_variable.h>
#include <tensorflow/lite/schema/schema_generated.h>
#include <cstdio>
#include <cstring>

namespace {
constexpr unsigned STACK=16384,ARENA=32768,MAX_SCORES=270;
K_MUTEX_DEFINE(lock);K_SEM_DEFINE(requested,0,1);
static struct {K_KERNEL_STACK_MEMBER(stack,STACK);} memory __attribute__((section(".ext_ram.bss.kws_stack")));
static struct k_thread thread;
static atomic_t cancelled;
static bool initialized,busy,ready,owned;
static bool job_stream;
static atomic_t stream_quarantined;
static atomic_t streaming,ring_overflows;
static unsigned stream_ms,cutoff_milli=970,cooldown_ms=1000;
struct AudioChunk {unsigned count;int16_t samples[256];};
static char ring_memory[16*sizeof(AudioChunk)] __attribute__((section(".ext_ram.bss.kws_ring"),aligned(4)));
static struct k_msgq ring;
static const int16_t *pcm;
static unsigned frames;
static const char *phase="idle",*message="microphone off; clip inference only";
struct Metrics {
 unsigned frames,features,invocations,events,event_ms,confidence_milli,arena_used,frontend_peak,stack_unused;
 unsigned max_invoke_us,max_step_us;
 uint64_t total_invoke_us,total_us;
 uint32_t feature_hash;
 uint8_t scores[MAX_SCORES];
};
static Metrics metrics;
static unsigned events[4],event_head,event_count,event_overflow,last_confidence;
static tflite::MicroMutableOpResolver<13> resolver;
static void *allocate(size_t n){return shared_multi_heap_aligned_alloc(SMH_REG_ATTR_EXTERNAL,16,n);}
static void release(void *p){if(p)shared_multi_heap_free(p);}
static uint64_t us(){return k_cyc_to_us_floor64(k_cycle_get_64());}
static int accept_audio(const int16_t *samples,unsigned count,void *)
{
 if(!samples||!count||count>256||atomic_get(&cancelled))return 0;
 AudioChunk chunk{};chunk.count=count;memcpy(chunk.samples,samples,count*2);
 int ok=k_msgq_put(&ring,&chunk,K_NO_WAIT)==0;
 memset(&chunk,0,sizeof(chunk));if(!ok)atomic_inc(&ring_overflows);return ok;
}
static const char *infer(Metrics &m)
{
 unsigned bytes=p4_kws_model_end-p4_kws_model_start;uint8_t hash[32];size_t n=0;
 if(bytes!=60264||psa_hash_compute(PSA_ALG_SHA_256,p4_kws_model_start,bytes,hash,32,&n)!=PSA_SUCCESS||n!=32||memcmp(hash,p4_kws_digest,32))return "trusted model hash mismatch";
 flatbuffers::Verifier verifier(p4_kws_model_start,bytes,24,4096);
 if(!tflite::VerifyModelBuffer(verifier))return "invalid model FlatBuffer";
 auto model=tflite::GetModel(p4_kws_model_start);
 if(model->version()!=TFLITE_SCHEMA_VERSION||model->subgraphs()->size()!=2)return "trusted model schema mismatch";
 auto arena=(uint8_t *)allocate(ARENA);if(!arena)return "tensor arena allocation failed";
 memset(arena,0,ARENA);const char *error=nullptr;
 kw_frontend frontend{};bool frontend_ready=false;
 auto allocator=tflite::MicroAllocator::Create(arena,ARENA);
 auto variables=allocator?tflite::MicroResourceVariables::Create(allocator,6):nullptr;
 if(!variables)error="resource variables allocation failed";
 else {
  tflite::MicroInterpreter interpreter(model,resolver,allocator,variables);
  if(interpreter.AllocateTensors()!=kTfLiteOk)error="tensor allocation failed";
  else {
   auto input=interpreter.input(0),output=interpreter.output(0);
   if(!input||!output||input->type!=kTfLiteInt8||input->bytes!=120||input->dims->size!=3||input->dims->data[0]!=1||input->dims->data[1]!=3||input->dims->data[2]!=40||output->type!=kTfLiteUInt8||output->bytes!=1||output->params.scale!=1.f/256||output->params.zero_point!=0)error="trusted tensor contract mismatch";
   else if(!(frontend_ready=kw_features_begin(&frontend,{allocate,release})))error="frontend allocation failed";
   else {
    unsigned history[5]={},batch=0,work_us=0;int64_t last_event=-100000;size_t pos=0,span=frames;
    uint64_t start=us();int64_t deadline=k_uptime_get()+(job_stream?stream_ms+3000:60000);
    AudioChunk chunk{};const int16_t *samples=pcm;
    if(job_stream){
     k_msgq_purge(&ring);memset(ring_memory,0,sizeof(ring_memory));span=0;
     if(!p4_audio_stream_start(stream_ms,accept_audio,nullptr))error="microphone busy or unavailable";
     else atomic_set(&streaming,1);
    }
    m.feature_hash=2166136261u;
    while(!error){
     if(atomic_get(&cancelled)){error="cancelled";break;}
     if((!job_stream||stream_ms)&&k_uptime_get()>deadline){error="inference deadline exceeded";break;}
     if(pos>=span){
      if(!job_stream)break;
      if(k_msgq_get(&ring,&chunk,K_MSEC(25))){int state=p4_audio_stream_state();if(state==1)continue;if(state<0)error="microphone stream failed; inspect audio status";break;}
      if(!chunk.count||chunk.count>256){error="invalid audio stream block";break;}
      samples=chunk.samples;span=chunk.count;pos=0;
     }
     size_t count=MIN((size_t)257,span-pos),used=0;int8_t feature[40];
     uint64_t feature_started=us();int result=kw_features_push(&frontend,samples+pos,count,&used,feature);work_us+=us()-feature_started;
     if(result<0||!used||used>count){error="frontend processing failed";break;}
     if(used>UINT32_MAX-m.frames){error="session counter limit reached; restart listener";break;}
     pos+=used;m.frames+=used;if(!result)continue;
     for(unsigned i=0;i<40;i++)m.feature_hash=(m.feature_hash^(uint8_t)feature[i])*16777619u;
     m.features++;memcpy(input->data.int8+batch*40,feature,40);
     if(++batch!=3)continue;
     batch=0;
     uint64_t before=us();auto result_status=interpreter.Invoke();unsigned elapsed=us()-before;
     m.max_invoke_us=MAX(m.max_invoke_us,elapsed);m.total_invoke_us+=elapsed;
     if(result_status!=kTfLiteOk){error="native kernel invocation failed";break;}
     if(!job_stream&&m.invocations>=MAX_SCORES){error="score budget exceeded";break;}
     unsigned score=output->data.uint8[0];if(m.invocations<MAX_SCORES)m.scores[m.invocations]=score;
     history[m.invocations%5]=score;unsigned sum=0;for(unsigned v:history)sum+=v;
     int64_t at_ms=50+30LL*m.invocations;m.invocations++;
     if(sum>=(cutoff_milli*1280+999)/1000&&at_ms-last_event>=cooldown_ms){
      m.events++;m.event_ms=at_ms;m.confidence_milli=(sum*1000+640)/1280;last_event=at_ms;memset(history,0,sizeof(history));
      k_mutex_lock(&lock,K_FOREVER);
      if(!atomic_get(&cancelled)){if(event_count<4){events[(event_head+event_count)%4]=m.confidence_milli;event_count++;}else event_overflow++;}
      k_mutex_unlock(&lock);
     }
     work_us+=elapsed;m.max_step_us=MAX(m.max_step_us,work_us);work_us=0;
     k_sleep(K_MSEC(1));
    }
    if(job_stream&&atomic_get(&streaming)){
     p4_audio_stream_stop();int64_t stop_deadline=k_uptime_get()+3000;
     while(p4_audio_stream_state()==1&&k_uptime_get()<stop_deadline)k_sleep(K_MSEC(5));
     if(p4_audio_stream_state()==1){atomic_set(&stream_quarantined,1);error="audio stop pending; restart board before reuse";}
     else {atomic_clear(&streaming);k_msgq_purge(&ring);memset(ring_memory,0,sizeof(ring_memory));}
     if(atomic_get(&ring_overflows))error="audio queue overflow; listener stopped";
    }
    memset(&chunk,0,sizeof(chunk));
    m.total_us=us()-start;m.arena_used=interpreter.arena_used_bytes();
   }
  }
 }
 m.frontend_peak=frontend.peak_requested;
 if(frontend_ready||frontend.live)kw_features_end(&frontend);
 memset(arena,0,ARENA);release(arena);return error;
}
static void worker(void *,void *,void *)
{
 for(;;){
  k_sem_take(&requested,K_FOREVER);Metrics result{};const char *error=infer(result);
  size_t unused=0;k_thread_stack_space_get(&thread,&unused);result.stack_unused=unused;
  k_mutex_lock(&lock,K_FOREVER);
  if(owned){memset((void *)pcm,0,frames*2);release((void *)pcm);}pcm=nullptr;owned=false;
  bool stopped=atomic_get(&cancelled);metrics=result;ready=!error&&!stopped;busy=false;
  phase=atomic_get(&stream_quarantined)?"error":stopped?"idle":error?"error":"ready";message=atomic_get(&stream_quarantined)?"audio stop pending; restart board":stopped?"cancelled; buffers released":error?error:job_stream?"listening complete; microphone stopped":"clip complete; microphone was not started";
  k_mutex_unlock(&lock);
 }
}
static bool queue(const int16_t *samples,unsigned count,bool take)
{
 if(!initialized||busy||atomic_get(&stream_quarantined)||!samples||count<480||count>AUDIO_MAX_FRAMES)return false;
 event_head=event_count=event_overflow=last_confidence=0;
 job_stream=false;cutoff_milli=970;cooldown_ms=1000;atomic_clear(&ring_overflows);
 pcm=samples;frames=count;owned=take;busy=true;ready=false;phase="running";atomic_clear(&cancelled);k_sem_give(&requested);return true;
}
}
extern "C" void p4_kws_init(void)
{
 if(initialized)return;
 if(resolver.AddCallOnce()!=kTfLiteOk||resolver.AddVarHandle()!=kTfLiteOk||resolver.AddReshape()!=kTfLiteOk||resolver.AddReadVariable()!=kTfLiteOk||resolver.AddConcatenation()!=kTfLiteOk||resolver.AddStridedSlice()!=kTfLiteOk||resolver.AddAssignVariable()!=kTfLiteOk||resolver.AddConv2D()!=kTfLiteOk||resolver.AddDepthwiseConv2D()!=kTfLiteOk||resolver.AddSplitV()!=kTfLiteOk||resolver.AddFullyConnected()!=kTfLiteOk||resolver.AddLogistic()!=kTfLiteOk||resolver.AddQuantize()!=kTfLiteOk||psa_crypto_init()!=PSA_SUCCESS){message="kernel or hash initialization failed";return;}
 k_msgq_init(&ring,ring_memory,sizeof(AudioChunk),16);
 initialized=true;k_thread_create(&thread,memory.stack,K_KERNEL_STACK_SIZEOF(memory.stack),worker,nullptr,nullptr,nullptr,8,0,K_NO_WAIT);k_thread_name_set(&thread,"p4_kws");
}
extern "C" int p4_kws_available(void){return initialized;}
extern "C" int p4_kws_fixture(unsigned id)
{
 k_mutex_lock(&lock,K_FOREVER);bool ok=false;
#if defined(P4_KWS_FIXTURES)
 const uint8_t *start=id==1?p4_kws_positive_start:id==2?p4_kws_negative_start:nullptr;
 const uint8_t *end=id==1?p4_kws_positive_end:id==2?p4_kws_negative_end:nullptr;
 if(start)ok=queue((const int16_t *)start,(end-start)/2,false);
#else
 (void)id;
#endif
 k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_kws_clip(int handle)
{
 const audio_view *v=audio_get(handle);if(!v||v->frames<480||v->frames>AUDIO_MAX_FRAMES||v->rate!=16000||v->channels!=1)return 0;
 k_mutex_lock(&lock,K_FOREVER);bool ok=false;
 if(initialized&&!busy){auto copy=(int16_t *)allocate(v->frames*2);if(copy){memcpy(copy,v->samples,v->frames*2);ok=queue(copy,v->frames,true);if(!ok){memset(copy,0,v->frames*2);release(copy);}}}
 k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_kws_busy(void){k_mutex_lock(&lock,K_FOREVER);int value=busy;k_mutex_unlock(&lock);return value;}
extern "C" int p4_kws_listen(unsigned ms,unsigned confidence,unsigned cooldown)
{
 if(ms>300000||(ms&&ms<100)||confidence<500||confidence>999||cooldown<250||cooldown>10000)return 0;
 k_mutex_lock(&lock,K_FOREVER);bool ok=initialized&&!busy&&!atomic_get(&stream_quarantined)&&!p4_audio_busy();
 if(ok){job_stream=true;stream_ms=ms;cutoff_milli=confidence;cooldown_ms=cooldown;pcm=nullptr;frames=0;owned=false;busy=true;ready=false;event_head=event_count=event_overflow=last_confidence=0;atomic_clear(&ring_overflows);atomic_clear(&cancelled);phase="starting";k_sem_give(&requested);}
 k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_kws_listening(void){return atomic_get(&streaming)&&p4_audio_stream_state()==1;}
extern "C" void p4_kws_cancel(void){atomic_set(&cancelled,1);p4_audio_stream_stop();k_mutex_lock(&lock,K_FOREVER);ready=false;event_count=event_head=last_confidence=0;if(!busy){bool fault=atomic_get(&stream_quarantined)||p4_audio_stream_state()<0;phase=fault?"error":"idle";message=fault?"audio fault; inspect audio status before reuse":"microphone off; results cleared";memset(&metrics,0,sizeof(metrics));}k_mutex_unlock(&lock);}
extern "C" int p4_kws_take_event(void){k_mutex_lock(&lock,K_FOREVER);int ok=event_count&&!atomic_get(&cancelled);if(ok){last_confidence=events[event_head];event_head=(event_head+1)%4;event_count--;}k_mutex_unlock(&lock);return ok;}
extern "C" unsigned p4_kws_confidence(void){k_mutex_lock(&lock,K_FOREVER);unsigned n=last_confidence;k_mutex_unlock(&lock);return n;}
extern "C" const char *p4_kws_state(void){k_mutex_lock(&lock,K_FOREVER);const char *s=busy?(job_stream?(atomic_get(&streaming)?"Listening for Okay Nabu":"Starting wake-word listener"):"Checking audio clip"):message;k_mutex_unlock(&lock);return s;}
extern "C" int p4_kws_scores(unsigned offset,unsigned count,uint8_t *out){k_mutex_lock(&lock,K_FOREVER);unsigned available=MIN(metrics.invocations,MAX_SCORES);bool ok=ready&&!busy&&offset<=available&&count<=available-offset&&count<=64;if(ok)memcpy(out,metrics.scores+offset,count);k_mutex_unlock(&lock);return ok;}
extern "C" void p4_kws_status(char *out,size_t n)
{
 k_mutex_lock(&lock,K_FOREVER);Metrics m=busy?Metrics{}:metrics;
 snprintf(out,n,"{\"available\":%s,\"busy\":%s,\"listening\":%s,\"phase\":\"%s\",\"message\":\"%s\",\"frames\":%u,\"features\":%u,\"feature_fnv1a\":\"%08x\",\"invocations\":%u,\"events\":%u,\"event_ms\":%u,\"confidence_milli\":%u,\"arena_reserved_bytes\":%u,\"arena_used_bytes\":%u,\"frontend_peak_requested_bytes\":%u,\"stack_reserved_bytes\":%u,\"stack_unused_bytes\":%u,\"max_invoke_us\":%u,\"total_invoke_us\":%llu,\"max_step_us\":%u,\"total_us\":%llu,\"ring_bytes\":%u,\"ring_overflows\":%u,\"event_overflows\":%u,\"quarantined\":%s}",initialized?"true":"false",busy?"true":"false",p4_kws_listening()?"true":"false",phase,busy?(job_stream?"explicit microphone stream":"bounded CPU clip inference"):message,m.frames,m.features,m.feature_hash,m.invocations,m.events,m.event_ms,m.confidence_milli,ARENA,m.arena_used,m.frontend_peak,STACK,m.stack_unused,m.max_invoke_us,(unsigned long long)m.total_invoke_us,m.max_step_us,(unsigned long long)m.total_us,(unsigned)sizeof(ring_memory),(unsigned)atomic_get(&ring_overflows),event_overflow,atomic_get(&stream_quarantined)?"true":"false");
 k_mutex_unlock(&lock);
}
