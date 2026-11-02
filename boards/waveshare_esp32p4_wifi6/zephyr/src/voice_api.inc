/* SPDX-License-Identifier: MIT */
/* Included after kws_backend.cpp namespace, to share its serialized worker. */
#if defined(P4_VOICE_COMMANDS)
extern "C" int p4_voice_available(void){return initialized&&voice_initialized;}
extern "C" void p4_voice_clear(void) {
    k_mutex_lock(&lock,K_FOREVER);voice_head=voice_count=voice_overflow=voice_confidence=0;voice_last=-1;
    memset(voice_scores,0,sizeof(voice_scores));k_mutex_unlock(&lock);
}
extern "C" int p4_voice_listen(unsigned ms,unsigned confidence,unsigned cooldown) {
    if(ms>300000 || (ms&&ms<1200) || confidence<500 || confidence>999 || cooldown<250 || cooldown>10000)return 0;
    k_mutex_lock(&lock,K_FOREVER);
    bool ok=p4_voice_available()&&!busy&&!atomic_get(&stream_quarantined)&&!p4_audio_busy();
    if(ok) {
        p4_voice_clear();event_head=event_count=event_overflow=last_confidence=0;
        job_voice=job_stream=true;stream_ms=ms;cutoff_milli=confidence;cooldown_ms=cooldown;
        pcm=nullptr;frames=0;owned=false;busy=true;ready=false;phase="starting";metrics=Metrics{};
        atomic_clear(&cancelled);atomic_clear(&ring_overflows);k_sem_give(&requested);
    }
    k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_voice_clip(int handle) {
    const audio_view *v=audio_get(handle);
    if(!v||v->frames<19200||v->frames>AUDIO_MAX_FRAMES||v->rate!=16000||v->channels!=1)return 0;
    k_mutex_lock(&lock,K_FOREVER);bool ok=false;
    if(p4_voice_available()&&!busy&&!atomic_get(&stream_quarantined)) {
        auto copy=(int16_t *)allocate(v->frames*2);
        if(copy){memcpy(copy,v->samples,v->frames*2);p4_voice_clear();ok=queue(copy,v->frames,true,true);if(!ok){memset(copy,0,v->frames*2);release(copy);}}
    }
    k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_voice_take_event(void) {
    k_mutex_lock(&lock,K_FOREVER);int result=-1;
    if(voice_count&&!atomic_get(&cancelled)) {
        unsigned v=voice_events[voice_head];voice_head=(voice_head+1)%4;voice_count--;
        voice_last=result=v&255;voice_confidence=v>>8;
    }
    k_mutex_unlock(&lock);return result;
}
extern "C" const char *p4_voice_command(void){k_mutex_lock(&lock,K_FOREVER);const char *s=voice_last<0?"":voice_names[voice_last];k_mutex_unlock(&lock);return s;}
extern "C" unsigned p4_voice_confidence(void){k_mutex_lock(&lock,K_FOREVER);unsigned c=voice_confidence;k_mutex_unlock(&lock);return c;}
extern "C" unsigned p4_voice_score(unsigned i){k_mutex_lock(&lock,K_FOREVER);unsigned c=i<10?voice_scores[i]:0;k_mutex_unlock(&lock);return c;}
extern "C" void p4_voice_status(char *out,size_t bytes) {
    k_mutex_lock(&lock,K_FOREVER);Metrics m=job_voice?metrics:Metrics{};
    const char *state=job_voice?phase:busy?"shared worker busy":"idle";
    const char *detail=job_voice?(busy?"voice worker active":message):busy?"wake-word worker active":"voice listener off";
    bool listening=job_voice&&atomic_get(&streaming)&&p4_audio_stream_state()==1;
    snprintf(out,bytes,"{\"available\":%s,\"busy\":%s,\"worker_busy\":%s,\"listening\":%s,\"phase\":\"%s\",\"command\":\"%s\",\"confidence_milli\":%u,\"arena_reserved_bytes\":%u,\"arena_used_bytes\":%u,\"frontend_peak_bytes\":%u,\"feature_ring_bytes\":4720,\"audio_ring_bytes\":%u,\"stack_reserved_bytes\":%u,\"max_invoke_us\":%u,\"max_step_us\":%u,\"frames\":%u,\"invocations\":%u,\"events\":%u,\"ring_overflows\":%u,\"event_overflows\":%u,\"message\":\"%s\"}",p4_voice_available()?"true":"false",busy&&job_voice?"true":"false",busy?"true":"false",listening?"true":"false",state,voice_last<0?"":voice_names[voice_last],voice_confidence,VOICE_ARENA,m.arena_used,m.frontend_peak,(unsigned)sizeof(ring_memory),STACK,m.max_invoke_us,m.max_step_us,m.frames,m.invocations,m.events,(unsigned)atomic_get(&ring_overflows),voice_overflow,detail);
    k_mutex_unlock(&lock);
}
#else
extern "C" int p4_voice_available(void){return 0;}
extern "C" int p4_voice_listen(unsigned a,unsigned b,unsigned c){(void)a;(void)b;(void)c;return 0;}
extern "C" int p4_voice_clip(int h){(void)h;return 0;}
extern "C" int p4_voice_take_event(void){return -1;}
extern "C" const char *p4_voice_command(void){return "";}
extern "C" unsigned p4_voice_confidence(void){return 0;}
extern "C" unsigned p4_voice_score(unsigned i){(void)i;return 0;}
extern "C" void p4_voice_clear(void){}
extern "C" void p4_voice_status(char *out,size_t n){snprintf(out,n,"{\"available\":false,\"message\":\"voice command model not installed\"}");}
#endif
