/* SPDX-License-Identifier: MIT */
#include "decision.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    voice_decision d; uint16_t scores[10]={0}; scores[2]=990;
    voice_decision_begin(&d,850,800);
    assert(voice_decision_push(&d,scores,0)==-1);
    assert(voice_decision_push(&d,scores,100)==2);
    for(unsigned t=200;t<3000;t+=100)assert(voice_decision_push(&d,scores,t)==-1);
    scores[2]=0;scores[8]=990;
    for(unsigned t=3000;t<4000;t+=100)assert(voice_decision_push(&d,scores,t)==-1);
    scores[8]=0;scores[0]=990;int events=0;
    for(unsigned t=4000;t<5000;t+=100)if(voice_decision_push(&d,scores,t)==0)events++;
    assert(events==1);
    /* Stop/restart clears old confidence/rearm/timestamps. */
    voice_decision_begin(&d,850,800);scores[0]=600;
    for(unsigned t=0;t<1000;t+=100)assert(voice_decision_push(&d,scores,t)==-1);
    voice_decision_begin(&d,850,800);scores[0]=990;
    assert(voice_decision_push(&d,scores,UINT32_MAX-10)==-1);
    assert(voice_decision_push(&d,scores,UINT32_MAX)==0);
    assert(voice_decision_push(&d,scores,10)==-1);
    puts("decision policy: stability, rejection, release, cooldown, restart, wrap PASS");
}
