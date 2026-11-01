/* SPDX-License-Identifier: MIT — stdin fixture for the actual unchanged engine. */
#include "steps.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
static void state(const mb_steps *s,mb_step_error error){
 printf("{\"error\":%u,\"running\":%s,\"now\":%" PRIu64 ",\"active\":%u,\"entered\":%u,\"exited\":%u,\"fired\":%" PRIu32 ",\"entryMs\":[",(unsigned)error,s->running?"true":"false",s->now,(unsigned)s->active,(unsigned)s->entered,(unsigned)s->exited,s->fired);
 for(unsigned i=0;i<16;i++)printf("%s%" PRIu64,i?",":"",s->entry_ms[i]);puts("]}");
}
int main(void){
 mb_steps s;mb_steps_init(&s,0);char line[160],command[16];uint64_t a,b,c,d;
 while(fgets(line,sizeof(line),stdin)){
  if(!strchr(line,'\n'))return 2;
  a=b=c=d=0;command[0]=0;int n=sscanf(line,"%15s %" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64,command,&a,&b,&c,&d);
  mb_step_error e=MB_STEP_OK;int report=0;
  if(!strcmp(command,"INIT")&&n==2)mb_steps_init(&s,a);
  else if(!strcmp(command,"ADD")&&n==3&&a<=16&&b<=1)e=mb_steps_add(&s,(unsigned)a,b!=0);
  else if(!strcmp(command,"EDGE")&&n==5&&a<=24&&b<=65535&&c<=65535&&d<=86400000)e=mb_steps_transition(&s,(unsigned)a,(uint16_t)b,(uint16_t)c,(uint32_t)d);
  else if(!strcmp(command,"COND")&&n==3&&a<=24&&b<=1)e=mb_steps_condition(&s,(unsigned)a,b!=0);
  else if(!strcmp(command,"START")&&n==2){e=mb_steps_start(&s,a);report=1;}
  else if(!strcmp(command,"SCAN")&&n==2){e=mb_steps_scan(&s,a);report=1;}
  else if(!strcmp(command,"STOP")&&n==1){mb_steps_stop(&s);report=1;}
  else return 2;
  if(report)state(&s,e);
  else if(e){fprintf(stderr,"configuration error %u\n",(unsigned)e);return 3;}
 }
 return ferror(stdin)?4:0;
}
