/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "voice_primitives.h"
#include "voice_commands.h"
#include "kws_backend.h"
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
static OBJ voice_text(const char *s){return newStringFromBytes(s,strlen(s));}
OBJ voice_available(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_voice_available()?trueObj:falseObj;}
OBJ voice_listen(int n,OBJ *a){if(n!=3||!isInt(a[0])||!isInt(a[1])||!isInt(a[2]))return fail(needsIntegerError);return p4_voice_listen(obj2int(a[0]),obj2int(a[1]),obj2int(a[2]))?trueObj:falseObj;}
OBJ voice_stop(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);p4_kws_cancel();return falseObj;}
OBJ voice_clip(int n,OBJ *a){if(n!=1||!isInt(a[0]))return fail(needsIntegerError);return p4_voice_clip(obj2int(a[0]))?trueObj:falseObj;}
OBJ voice_command(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return voice_text(p4_voice_command());}
OBJ voice_confidence(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_voice_confidence());}
OBJ voice_score(int n,OBJ *a){
    if(n!=1||!IS_TYPE(a[0],StringType))return fail(needsStringError);
    static const char *names[]={"up","down","left","right","angry","happy","tired","normal","unknown","silence"};
    const char *s=obj2str(a[0]);unsigned len=strlen(s);
    for(unsigned i=0;i<10;i++) {
        if(strlen(names[i])!=len)continue;
        bool same=true;for(unsigned j=0;j<len;j++)if(tolower((unsigned char)s[j])!=names[i][j])same=false;
        if(same)return int2obj(p4_voice_score(i));
    }
    return fail(indexOutOfRangeError);
}
OBJ voice_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char out[900];p4_voice_status(out,sizeof(out));return voice_text(out);}
void p4_voice_poll(void){if(p4_voice_take_event()>=0){char name[]="_p4.voice.command";startReceiversOfBroadcast(name,sizeof(name)-1);}}
