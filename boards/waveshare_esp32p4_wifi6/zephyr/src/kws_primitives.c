/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "kws_primitives.h"
#include "kws_backend.h"
#include <string.h>
OBJ kws_available(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_kws_available()?trueObj:falseObj;}
OBJ kws_fixture(int n,OBJ *a){if(n!=1||!isInt(a[0]))return fail(needsIntegerError);return p4_kws_fixture(obj2int(a[0]))?trueObj:falseObj;}
OBJ kws_clip(int n,OBJ *a){if(n!=1||!isInt(a[0]))return fail(needsIntegerError);return p4_kws_clip(obj2int(a[0]))?trueObj:falseObj;}
OBJ kws_busy(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_kws_busy()?trueObj:falseObj;}
OBJ kws_confidence(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_kws_confidence());}
OBJ kws_listen(int n,OBJ *a){if(n!=3||!isInt(a[0])||!isInt(a[1])||!isInt(a[2]))return fail(needsIntegerError);return p4_kws_listen(obj2int(a[0]),obj2int(a[1]),obj2int(a[2]))?trueObj:falseObj;}
OBJ kws_listening(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_kws_listening()?trueObj:falseObj;}
OBJ kws_state(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);const char *s=p4_kws_state();return newStringFromBytes(s,strlen(s));}
void p4_kws_poll(void){if(p4_kws_take_event()){char name[]="_p4.wake.OkayNabu";startReceiversOfBroadcast(name,sizeof(name)-1);}}
OBJ kws_cancel(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);p4_kws_cancel();return falseObj;}
OBJ kws_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[960];p4_kws_status(s,sizeof(s));return newStringFromBytes(s,strlen(s));}
OBJ kws_scores(int n,OBJ *a){
 if(n!=2||!isInt(a[0])||!isInt(a[1]))return fail(needsIntegerError);
 int offset=obj2int(a[0]),count=obj2int(a[1]);uint8_t data[64];
 if(offset<0||count<0||count>64||!p4_kws_scores(offset,count,data))return fail(indexOutOfRangeError);
 OBJ out=newObj(ByteArrayType,(count+3)/4,zeroObj);if(out==falseObj)return out;setByteCountAdjust(out,count);memcpy(&FIELD(out,0),data,count);return out;
}
