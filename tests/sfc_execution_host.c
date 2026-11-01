/* SPDX-License-Identifier: MIT - fixture only, no serial/network endpoints. */
#include "sfc_actions.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
static void state(const mb_steps *s,const mb_sfc_actions *a,const unsigned *ids,unsigned error){
 uint32_t fired=0;for(unsigned i=0;i<24;i++)if(s->fired&(UINT32_C(1)<<i))fired|=UINT32_C(1)<<(ids[i]-1);
 printf("{\"error\":%u,\"running\":%s,\"now\":%" PRIu64 ",\"active\":%u,\"entered\":%u,\"exited\":%u,\"fired\":%" PRIu32 ",\"entryMs\":[",error,s->running?"true":"false",s->now,(unsigned)s->active,(unsigned)s->entered,(unsigned)s->exited,fired);
 for(unsigned i=0;i<16;i++)printf("%s%" PRIu64,i?",":"",s->entry_ms[i]);
 printf("],\"actions\":{\"normal\":%u,\"entryPulse\":%u,\"exitPulse\":%u,\"stored\":%u,\"reset\":%u,\"requested\":%u}}\n",(unsigned)a->normal,(unsigned)a->entry_pulse,(unsigned)a->exit_pulse,(unsigned)a->stored,(unsigned)a->reset,(unsigned)a->requested);
}
int main(void){
 mb_steps flow;mb_sfc_actions actions;mb_steps_init(&flow,0);mb_sfc_actions_init(&actions,0,0);
 unsigned ids[24];for(unsigned i=0;i<24;i++)ids[i]=i+1;
 char line[160],command[16],tail;uint64_t a,b,c,d;
 while(fgets(line,sizeof(line),stdin)){
  if(!strchr(line,'\n'))return 2;a=b=c=d=0;command[0]=0;
  int n=sscanf(line,"%15s %" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64 " %c",command,&a,&b,&c,&d,&tail);
  unsigned e=0;bool report=false;
  if(!strcmp(command,"INIT")&&n==4&&b<=65535&&c<=65535){mb_steps_init(&flow,a);mb_sfc_actions_init(&actions,(uint16_t)b,(uint16_t)c);for(unsigned i=0;i<24;i++)ids[i]=i+1;}
  else if(!strcmp(command,"ADD")&&n==3&&a<=16&&b<=1)e=mb_steps_add(&flow,(unsigned)a,b!=0);
  else if(!strcmp(command,"EDGE")&&n==5&&a<=24&&b<=65535&&c<=65535&&d<=86400000)e=mb_steps_transition(&flow,(unsigned)a,(uint16_t)b,(uint16_t)c,(uint32_t)d);
  else if(!strcmp(command,"MAP")&&n==3&&a>=1&&a<=24&&b>=1&&b<=24)ids[a-1]=(unsigned)b;
  else if(!strcmp(command,"BIND")&&n==4&&a<=16&&b<=16&&c<=MB_SFC_R)e=mb_sfc_actions_add(&actions,(unsigned)a,(unsigned)b,(mb_sfc_qualifier)c);
  else if(!strcmp(command,"SEAL")&&n==1)e=mb_sfc_actions_seal(&actions);
  else if(!strcmp(command,"COND")&&n==3&&a<=24&&b<=1)e=mb_steps_condition(&flow,(unsigned)a,b!=0);
  else if(!strcmp(command,"START")&&n==2){
   mb_steps next=flow;mb_sfc_actions ac=actions;report=true;
   if(!ac.sealed||ac.steps!=flow.defined)e=MB_SFC_UNSEALED;
   else if((e=mb_steps_start(&next,a))==0){mb_sfc_actions_clear(&ac);e=mb_sfc_actions_apply(&ac,next.active,next.entered,next.exited);}
   if(!e){flow=next;actions=ac;}
  }
  else if(!strcmp(command,"SCAN")&&n==2){
   mb_steps next=flow;mb_sfc_actions ac=actions;report=true;e=mb_steps_scan(&next,a);
   if(!e){if(next.running)e=mb_sfc_actions_apply(&ac,next.active,next.entered,next.exited);else mb_sfc_actions_clear(&ac);}
   if(!e){flow=next;actions=ac;}
  }
  else if(!strcmp(command,"RESTART")&&n==3&&a<=16){e=mb_sfc_restart(&flow,&actions,(unsigned)a,b);report=true;}
  else if(!strcmp(command,"RESET")&&n==2){unsigned initial=1;while(initial<=16&&!(flow.initial&(1u<<(initial-1))))initial++;e=mb_sfc_restart(&flow,&actions,initial,a);report=true;}
  else if(!strcmp(command,"STOP")&&n==1){mb_steps_stop(&flow);mb_sfc_actions_clear(&actions);report=true;}
  else return 2;
  if(report)state(&flow,&actions,ids,e);else if(e){fprintf(stderr,"configuration error %u\n",e);return 3;}
 }
 return ferror(stdin)?4:0;
}
