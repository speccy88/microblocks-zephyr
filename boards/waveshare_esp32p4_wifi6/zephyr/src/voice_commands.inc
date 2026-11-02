/* SPDX-License-Identifier: MIT */
/* Included inside kws_backend.cpp's private namespace. Same worker, frontend,
 * ring, cancellation and audio owner as Okay Nabu; never a second listener. */
#if defined(P4_VOICE_COMMANDS)
#include "voice_assets.h"
static bool job_voice;
static uint16_t voice_scores[10];
static unsigned voice_events[4],voice_head,voice_count,voice_overflow;
static int voice_last=-1;
static unsigned voice_confidence;
static tflite::MicroMutableOpResolver<8> voice_resolver;
static bool voice_initialized;
static const unsigned VOICE_ARENA=131072;
static const char *voice_names[10]={"up","down","left","right","angry","happy","tired","normal","unknown","silence"};
static const char *infer_voice(Metrics &m) {
    const unsigned bytes=p4_voice_model_end-p4_voice_model_start;
    uint8_t hash[32];size_t digest_size=0;
    if(bytes!=P4_VOICE_MODEL_BYTES || psa_hash_compute(PSA_ALG_SHA_256,p4_voice_model_start,bytes,hash,32,&digest_size)!=PSA_SUCCESS || digest_size!=32 || memcmp(hash,p4_voice_digest,32))return "voice model hash mismatch";
    flatbuffers::Verifier verifier(p4_voice_model_start,bytes,24,4096);
    if(!tflite::VerifyModelBuffer(verifier))return "invalid voice model FlatBuffer";
    const auto model=tflite::GetModel(p4_voice_model_start);
    if(model->version()!=TFLITE_SCHEMA_VERSION || model->subgraphs()->size()!=1)return "voice model schema mismatch";
    auto arena=(uint8_t *)allocate(VOICE_ARENA);
    auto history=(int8_t *)allocate(118*40);
    if(!arena || !history){release(arena);release(history);return "voice memory pressure; release other media";}
    memset(arena,0,VOICE_ARENA);memset(history,-128,118*40);
    const char *error=nullptr;kw_frontend frontend{};bool frontend_ready=false;
    {
        tflite::MicroInterpreter interpreter(model,voice_resolver,arena,VOICE_ARENA);
        if(interpreter.AllocateTensors()!=kTfLiteOk)error="voice tensor allocation failed";
        else {
            auto in=interpreter.input(0),out=interpreter.output(0);
            if(in->type!=kTfLiteInt8 || in->bytes!=4720 || in->dims->size!=4 || in->dims->data[0]!=1 || in->dims->data[1]!=118 || in->dims->data[2]!=40 || in->dims->data[3]!=1 || out->type!=kTfLiteInt8 || out->bytes!=10 || out->dims->size!=2 || out->dims->data[0]!=1 || out->dims->data[1]!=10 || in->params.scale<=0 || out->params.scale!=P4_VOICE_OUTPUT_SCALE || out->params.zero_point!=P4_VOICE_OUTPUT_ZERO)error="voice tensor contract mismatch";
            else if(!(frontend_ready=kw_features_begin(&frontend,{allocate,release})))error="voice frontend allocation failed";
            else {
                m.arena_used=interpreter.arena_used_bytes();m.frontend_peak=frontend.peak_requested;
                k_mutex_lock(&lock,K_FOREVER);metrics=m;k_mutex_unlock(&lock);
                voice_decision decision;voice_decision_begin(&decision,cutoff_milli,cooldown_ms);
                unsigned fill=0,since=0;size_t pos=0,span=frames;
                const int16_t *samples=pcm;AudioChunk chunk{};
                const uint64_t started=us();int64_t deadline=k_uptime_get()+(job_stream?stream_ms+3000:60000);
                if(job_stream) {
                    k_msgq_purge(&ring);memset(ring_memory,0,sizeof(ring_memory));span=0;
                    if(!p4_audio_stream_start(stream_ms,accept_audio,nullptr))error="microphone busy or unavailable";
                    else {atomic_set(&streaming,1);k_mutex_lock(&lock,K_FOREVER);phase="warming";k_mutex_unlock(&lock);}
                }
                m.feature_hash=2166136261u;
                while(!error) {
                    if(atomic_get(&cancelled)){error="cancelled";break;}
                    if((!job_stream||stream_ms)&&k_uptime_get()>deadline){error="voice deadline exceeded";break;}
                    if(atomic_get(&ring_overflows)){error="voice audio queue overflow";break;}
                    if(pos>=span) {
                        if(!job_stream)break;
                        if(k_msgq_get(&ring,&chunk,K_MSEC(25))) {
                            int state=p4_audio_stream_state();if(state==1)continue;
                            if(state<0)error="microphone stream failed";
                            break;
                        }
                        if(!chunk.count || chunk.count>256){error="invalid voice audio block";break;}
                        samples=chunk.samples;span=chunk.count;pos=0;
                    }
                    int8_t feature[40];size_t used=0,count=MIN((size_t)257,span-pos);
                    uint64_t step=us();int got=kw_features_push(&frontend,samples+pos,count,&used,feature);
                    if(got<0||!used||used>count){error="voice frontend failed";break;}
                    if(used>UINT32_MAX-m.frames){error="voice session counter limit";break;}
                    pos+=used;m.frames+=used;if(!got)continue;
                    m.features++;
                    for(unsigned i=0;i<40;i++)m.feature_hash=(m.feature_hash^(uint8_t)feature[i])*16777619u;
                    if(fill<118){memcpy(history+40*fill,feature,40);fill++;}
                    else {memmove(history,history+40,117*40);memcpy(history+117*40,feature,40);}
                    if(fill<118)continue;
                    if(m.invocations && ++since<10)continue;
                    since=0;
                    for(unsigned i=0;i<4720;i++) {
                        int q=(int)lrintf(history[i]/in->params.scale)+in->params.zero_point;
                        in->data.int8[i]=(int8_t)CLAMP(q,-128,127);
                    }
                    uint64_t before=us();auto result=interpreter.Invoke();unsigned elapsed=us()-before;
                    m.max_invoke_us=MAX(m.max_invoke_us,elapsed);m.total_invoke_us+=elapsed;m.invocations++;
                    if(result!=kTfLiteOk){error="voice TFLM invocation failed";break;}
                    uint16_t scores[10];for(unsigned i=0;i<10;i++){int score=(int)lrintf(((int)out->data.int8[i]-out->params.zero_point)*out->params.scale*1000);scores[i]=(uint16_t)CLAMP(score,0,1000);}
                    const uint32_t at_ms=m.frames/16;int action=voice_decision_push(&decision,scores,at_ms);
                    k_mutex_lock(&lock,K_FOREVER);
                    metrics=m;if(!atomic_get(&cancelled))phase=job_stream?"listening":"running";
                    if(!atomic_get(&cancelled))memcpy(voice_scores,scores,sizeof(scores));
                    if(action>=0&&!atomic_get(&cancelled)) {
                        m.events++;m.event_ms=at_ms;m.confidence_milli=decision.smooth[action];
                        if(voice_count<4){voice_events[(voice_head+voice_count)%4]=(unsigned)action | ((unsigned)m.confidence_milli<<8);voice_count++;}
                        else voice_overflow++;
                    }
                    k_mutex_unlock(&lock);
                    m.max_step_us=MAX(m.max_step_us,(unsigned)(us()-step));k_sleep(K_MSEC(1));
                }
                if(job_stream&&atomic_get(&streaming)) {
                    p4_audio_stream_stop();int64_t stop_deadline=k_uptime_get()+3000;
                    while(p4_audio_stream_state()==1&&k_uptime_get()<stop_deadline)k_sleep(K_MSEC(5));
                    if(p4_audio_stream_state()==1){atomic_set(&stream_quarantined,1);error="audio stop pending; restart board before reuse";}
                    else {atomic_clear(&streaming);k_msgq_purge(&ring);memset(ring_memory,0,sizeof(ring_memory));}
                }
                memset(&chunk,0,sizeof(chunk));m.total_us=us()-started;
            }
            m.arena_used=interpreter.arena_used_bytes();
        }
    }
    m.frontend_peak=frontend.peak_requested;if(frontend_ready||frontend.live)kw_features_end(&frontend);
    memset(history,0,118*40);release(history);memset(arena,0,VOICE_ARENA);release(arena);
    return error;
}
#else
static bool job_voice;
#endif
