/* SPDX-License-Identifier: MIT */
#include "sfc_actions.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void){
 mb_sfc_actions a,b;mb_steps f,g;
 mb_sfc_actions_init(&a,65535,65535);
 assert(mb_sfc_actions_apply(&a,1,1,0)==MB_SFC_UNSEALED);
 assert(mb_sfc_actions_add(&a,0,1,MB_SFC_N)==MB_SFC_RANGE);
 assert(mb_sfc_actions_add(&a,1,17,MB_SFC_N)==MB_SFC_RANGE);
 assert(mb_sfc_actions_add(&a,1,1,(mb_sfc_qualifier)-1)==MB_SFC_RANGE);
 assert(mb_sfc_actions_add(&a,16,16,MB_SFC_S)==MB_SFC_OK);
 b=a;assert(mb_sfc_actions_add(&a,16,16,MB_SFC_S)==MB_SFC_DUPLICATE);assert(!memcmp(&a,&b,sizeof(a)));
 assert(mb_sfc_actions_seal(&a)==MB_SFC_OK);assert(mb_sfc_actions_add(&a,1,1,MB_SFC_N)==MB_SFC_SEALED);
 assert(mb_sfc_actions_apply(&a,32768,32768,0)==MB_SFC_OK);assert(a.stored==32768);
 b=a;assert(mb_sfc_actions_apply(&a,1,2,0)==MB_SFC_MISSING);assert(!memcmp(&a,&b,sizeof(a)));
 mb_sfc_actions_clear(&a);assert(!a.requested&&!a.stored&&a.sealed&&a.count==1);
 mb_sfc_actions_init(&a,65535,65535);
 for(unsigned i=0;i<64;i++)assert(mb_sfc_actions_add(&a,i/5+1,1,(mb_sfc_qualifier)(i%5))==MB_SFC_OK);
 b=a;assert(mb_sfc_actions_add(&a,16,16,MB_SFC_N)==MB_SFC_RANGE);assert(!memcmp(&a,&b,sizeof(a)));
 mb_steps_init(&f,10);assert(mb_steps_add(&f,1,true)==MB_STEP_OK);assert(mb_steps_add(&f,2,false)==MB_STEP_OK);
 mb_sfc_actions_init(&a,3,3);assert(mb_sfc_actions_add(&a,1,1,MB_SFC_S)==MB_SFC_OK);assert(mb_sfc_actions_add(&a,2,2,MB_SFC_P0)==MB_SFC_OK);assert(mb_sfc_actions_seal(&a)==MB_SFC_OK);
 assert(mb_sfc_restart(&f,&a,1,10)==MB_SFC_OK);assert(a.stored==1&&f.initial==1);
 g=f;b=a;assert(mb_sfc_restart(&f,&a,2,9)==MB_SFC_REWIND);assert(!memcmp(&f,&g,sizeof(f))&&!memcmp(&a,&b,sizeof(a)));
 assert(mb_sfc_restart(&f,&a,3,10)==MB_SFC_MISSING);assert(!memcmp(&f,&g,sizeof(f))&&!memcmp(&a,&b,sizeof(a)));
 assert(mb_sfc_restart(&f,&a,0,10)==MB_SFC_RANGE);assert(!memcmp(&f,&g,sizeof(f))&&!memcmp(&a,&b,sizeof(a)));
 assert(mb_sfc_restart(&f,&a,2,20)==MB_SFC_OK);assert(f.active==2&&f.entered==2&&!f.exited&&f.entry_ms[1]==20&&f.initial==1&&!a.requested);
 assert(mb_sfc_restart(&f,&a,1,20)==MB_SFC_OK);assert(a.stored==1&&f.initial==1);
 puts("{\"result\":\"PASS\",\"scenarios\":7,\"hardware_access\":false}");return 0;
}
