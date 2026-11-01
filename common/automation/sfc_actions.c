/* SPDX-License-Identifier: MIT */
#include "sfc_actions.h"
#include <string.h>
void mb_sfc_actions_init(mb_sfc_actions *a,uint16_t steps,uint16_t signals){
 memset(a,0,sizeof(*a));a->steps=steps;a->signals=signals;
}
mb_sfc_error mb_sfc_actions_add(mb_sfc_actions *a,unsigned step,unsigned signal,mb_sfc_qualifier q){
 if(a->sealed)return MB_SFC_SEALED;
 if(step<1||step>16||signal<1||signal>16||(unsigned)q>MB_SFC_R||a->count>=MB_SFC_BINDING_COUNT)return MB_SFC_RANGE;
 if(!(a->steps&(1u<<(step-1)))||!(a->signals&(1u<<(signal-1))))return MB_SFC_MISSING;
 for(unsigned i=0;i<a->count;i++)if(a->bindings[i].step==step&&a->bindings[i].signal==signal&&a->bindings[i].qualifier==(unsigned)q)return MB_SFC_DUPLICATE;
 a->bindings[a->count++]=(mb_sfc_binding){(uint8_t)step,(uint8_t)signal,(uint8_t)q};return MB_SFC_OK;
}
mb_sfc_error mb_sfc_actions_seal(mb_sfc_actions *a){if(a->sealed)return MB_SFC_SEALED;a->sealed=true;return MB_SFC_OK;}
void mb_sfc_actions_clear(mb_sfc_actions *a){a->normal=a->entry_pulse=a->exit_pulse=a->stored=a->reset=a->requested=0;}
mb_sfc_error mb_sfc_actions_apply(mb_sfc_actions *a,uint16_t active,uint16_t entered,uint16_t exited){
 if(!a->sealed)return MB_SFC_UNSEALED;
 if(((active|entered|exited)&a->steps)!=(active|entered|exited)||(entered&active)!=entered)return MB_SFC_MISSING;
 uint16_t normal=0,p1=0,p0=0,sets=0,reset=0;
 for(unsigned i=0;i<a->count;i++){
  const mb_sfc_binding b=a->bindings[i];uint16_t s=(uint16_t)(1u<<(b.step-1)),q=(uint16_t)(1u<<(b.signal-1));
  switch(b.qualifier){
   case MB_SFC_N:if(active&s)normal|=q;break;
   case MB_SFC_P1:if(entered&s)p1|=q;break;
   case MB_SFC_P0:if(exited&s)p0|=q;break;
   case MB_SFC_S:if(entered&s)sets|=q;break;
   case MB_SFC_R:if(active&s)reset|=q;break;
  }
 }
 a->normal=normal;a->entry_pulse=p1;a->exit_pulse=p0;a->reset=reset;
 a->stored=(uint16_t)((a->stored|sets)&~reset);a->requested=(uint16_t)(normal|p1|p0|a->stored);return MB_SFC_OK;
}
mb_sfc_error mb_sfc_restart(mb_steps *flow,mb_sfc_actions *a,unsigned step,uint64_t now){
 if(!a->sealed)return MB_SFC_UNSEALED;
 if(step<1||step>16)return MB_SFC_RANGE;
 if(!(flow->defined&(1u<<(step-1)))||flow->defined!=a->steps)return MB_SFC_MISSING;
 if(now<flow->now)return MB_SFC_REWIND;
 mb_steps next=*flow;mb_sfc_actions actions=*a;uint16_t initial=next.initial;
 mb_steps_stop(&next);next.initial=(uint16_t)(1u<<(step-1));
 if(mb_steps_start(&next,now)!=MB_STEP_OK)return MB_SFC_FLOW;
 next.initial=initial;mb_sfc_actions_clear(&actions);
 mb_sfc_error e=mb_sfc_actions_apply(&actions,next.active,next.entered,next.exited);if(e)return e;
 *flow=next;*a=actions;return MB_SFC_OK;
}
