/* SPDX-License-Identifier: MIT */
#include "steps.h"
#include <string.h>
void mb_steps_init(mb_steps *s,uint64_t now){memset(s,0,sizeof(*s));s->now=now;}
void mb_steps_stop(mb_steps *s){s->running=false;s->active=s->entered=s->exited=0;s->fired=0;memset(s->entry_ms,0,sizeof(s->entry_ms));for(unsigned i=0;i<MB_TRANSITION_COUNT;i++)s->transitions[i].condition=false;}
mb_step_error mb_steps_clear(mb_steps *s){if(s->running)return MB_STEP_RUNNING;uint64_t now=s->now;mb_steps_init(s,now);return MB_STEP_OK;}
mb_step_error mb_steps_add(mb_steps *s,unsigned step,bool initial){
 if(s->running)return MB_STEP_RUNNING;
 if(step<1||step>MB_STEP_COUNT)return MB_STEP_RANGE;
 uint16_t bit=(uint16_t)(1u<<(step-1));if(s->defined&bit)return MB_STEP_DUPLICATE;
 s->defined|=bit;if(initial)s->initial|=bit;return MB_STEP_OK;
}
mb_step_error mb_steps_transition(mb_steps *s,unsigned id,uint16_t from,uint16_t to,uint32_t delay){
 if(s->running)return MB_STEP_RUNNING;
 if(id<1||id>MB_TRANSITION_COUNT||!from||!to||delay>86400000)return MB_STEP_RANGE;
 if((from&s->defined)!=from||(to&s->defined)!=to)return MB_STEP_MISSING;
 mb_transition *t=&s->transitions[id-1];if(t->defined)return MB_STEP_DUPLICATE;
 *t=(mb_transition){.from=from,.to=to,.after_ms=delay,.defined=true};return MB_STEP_OK;
}
mb_step_error mb_steps_condition(mb_steps *s,unsigned id,bool condition){
 if(id<1||id>MB_TRANSITION_COUNT)return MB_STEP_RANGE;
 mb_transition *t=&s->transitions[id-1];if(!t->defined)return MB_STEP_MISSING;t->condition=condition;return MB_STEP_OK;
}
mb_step_error mb_steps_start(mb_steps *s,uint64_t now){
 if(s->running)return MB_STEP_RUNNING;
 if(now<s->now)return MB_STEP_REWIND;
 if(!s->initial)return MB_STEP_NO_INITIAL;
 mb_steps_stop(s);s->now=now;s->active=s->entered=s->initial;s->running=true;
 for(unsigned i=0;i<MB_STEP_COUNT;i++)if(s->initial&(1u<<i))s->entry_ms[i]=now;
 return MB_STEP_OK;
}
mb_step_error mb_steps_scan(mb_steps *s,uint64_t now){
 if(now<s->now)return MB_STEP_REWIND;
 s->now=now;s->entered=s->exited=0;s->fired=0;
 uint16_t consumed=0,targets=0,snapshot=s->active;
 for(unsigned i=0;i<MB_TRANSITION_COUNT;i++){
  mb_transition *t=&s->transitions[i];bool condition=t->condition;t->condition=false;
  if(!s->running||!t->defined||!condition||(snapshot&t->from)!=t->from||(consumed&t->from))continue;
  bool elapsed=true;for(unsigned k=0;k<MB_STEP_COUNT;k++)if((t->from&(1u<<k))&&now-s->entry_ms[k]<t->after_ms)elapsed=false;
  if(!elapsed)continue;
  consumed|=t->from;targets|=t->to;s->fired|=UINT32_C(1)<<i;
 }
 if(s->running){s->active=(uint16_t)((snapshot&~consumed)|targets);s->entered=targets;s->exited=consumed;for(unsigned i=0;i<MB_STEP_COUNT;i++)if(targets&(1u<<i))s->entry_ms[i]=now;}
 return MB_STEP_OK;
}
mb_step_error mb_steps_elapsed(mb_steps *s,unsigned step,uint64_t now,uint64_t *out){
 if(!out||step<1||step>MB_STEP_COUNT)return MB_STEP_RANGE;
 if(!(s->defined&(1u<<(step-1))))return MB_STEP_MISSING;
 if(now<s->now)return MB_STEP_REWIND;
 *out=(s->active&(1u<<(step-1)))?now-s->entry_ms[step-1]:0;return MB_STEP_OK;
}
const char *mb_step_error_text(mb_step_error e){static const char *const text[]={"OK","Step, transition or delay out of range","Stop steps before changing their configuration","Step or transition is not defined","Step or transition already exists","Choose at least one initial step","Monotonic time moved backward"};return (unsigned)e<sizeof(text)/sizeof(text[0])?text[e]:"Unknown step error";}
