/* SPDX-License-Identifier: MIT */
#include "decision.h"
#include <string.h>
void voice_decision_begin(voice_decision *s,unsigned threshold,unsigned cooldown) {
    memset(s,0,sizeof(*s)); s->threshold=threshold; s->cooldown=cooldown;
    s->candidate=255; s->armed=true;
}
int voice_decision_push(voice_decision *s,const uint16_t scores[10],uint32_t ms) {
    unsigned best=0;
    for(unsigned i=0;i<10;i++) {
        unsigned v=scores[i]>1000?1000:scores[i];
        s->smooth[i]=s->initialized?(uint16_t)((s->smooth[i]+v+1)/2):(uint16_t)v;
        if(s->smooth[i]>s->smooth[best])best=i;
    }
    s->initialized=true;
    if(best>=8 || s->smooth[best]<s->threshold) {
        s->stable=0;s->candidate=255;
        if(s->release<3)s->release++;
        if(s->release>=3)s->armed=true;
        return -1;
    }
    s->release=0;
    if(s->candidate!=best) {s->candidate=best;s->stable=1;}
    else if(s->stable<2)s->stable++;
    if(!s->armed || s->stable<2 || (s->has_event && (uint32_t)(ms-s->last_event)<s->cooldown))return -1;
    s->last_event=ms;s->has_event=true;s->armed=false;s->stable=0;
    return (int)best;
}
