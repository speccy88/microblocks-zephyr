/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "neural_primitives.h"
#include "neural_backend.h"
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
static uint32_t model(OBJ value)
{
 if(!IS_TYPE(value,StringType))return 0;
 const char *p=obj2str(value);if(strlen(p)!=11||memcmp(p,"NN:",3))return 0;
 uint32_t result=0;
 for(unsigned i=3;i<11;i++){unsigned c=(unsigned char)p[i],v=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:16;if(v>15)return 0;result=result*16+v;}
 return result<=0x1fffffffu?result:0;
}
static OBJ text(const char *s){return newStringFromBytes((char *)s,strlen(s));}
OBJ nn_available(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_nn_available()?trueObj:falseObj;}
OBJ nn_load(int n,OBJ *a){if(n!=1||!IS_TYPE(a[0],StringType))return fail(needsStringError);uint32_t t=p4_nn_builtin(obj2str(a[0]));char s[12]="";if(t)snprintf(s,sizeof(s),"NN:%08x",(unsigned)t);return text(s);}
OBJ nn_current(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);uint32_t t=p4_nn_current();char s[12]="";if(t)snprintf(s,sizeof(s),"NN:%08x",(unsigned)t);return text(s);}
OBJ nn_busy(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_nn_busy()?trueObj:falseObj;}
OBJ nn_ready(int n,OBJ *a){if(n!=1)return fail(notEnoughArguments);return p4_nn_ready(model(a[0]))?trueObj:falseObj;}
OBJ nn_info(int n,OBJ *a){if(n!=1)return fail(notEnoughArguments);char s[1000];p4_nn_info(model(a[0]),s,sizeof(s));return text(s);}
OBJ nn_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[600];p4_nn_status(s,sizeof(s));return text(s);}
OBJ nn_caps(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[600];p4_nn_capabilities(s,sizeof(s));return text(s);}
OBJ nn_set(int n,OBJ *a){if(n!=3||!isInt(a[1])||!isInt(a[2]))return fail(needsIntegerError);int i=obj2int(a[1]);return i>0&&p4_nn_set_value(model(a[0]),i-1,obj2int(a[2]))?trueObj:falseObj;}
OBJ nn_run(int n,OBJ *a){if(n!=2||!isInt(a[1]))return fail(needsIntegerError);int r=obj2int(a[1]);return r>0&&p4_nn_run(model(a[0]),r)?trueObj:falseObj;}
OBJ nn_output(int n,OBJ *a){if(n!=2||!isInt(a[1]))return fail(needsIntegerError);int i=obj2int(a[1]),value;return i>0&&p4_nn_output_value(model(a[0]),i-1,&value)?int2obj(value):falseObj;}
OBJ nn_cancel(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);p4_nn_cancel();return falseObj;}
OBJ nn_unload(int n,OBJ *a){if(n!=1)return fail(notEnoughArguments);return p4_nn_unload(model(a[0]))?trueObj:falseObj;}
OBJ nn_input_bytes(int n,OBJ *a)
{
 if(n!=3||!isInt(a[1])||!IS_TYPE(a[2],ByteArrayType))return fail(needsByteArray);
 int offset=obj2int(a[1]),count=BYTES(a[2]);uint32_t t=model(a[0]);uint8_t out[1];unsigned bytes=0;
 return offset>=0&&count<=512&&p4_nn_transfer(7,&t,offset,0,(uint8_t *)&FIELD(a[2],0),count,out,&bytes)==0?trueObj:falseObj;
}
OBJ nn_output_bytes(int n,OBJ *a)
{
 if(n!=3||!isInt(a[1])||!isInt(a[2]))return fail(needsIntegerError);
 int offset=obj2int(a[1]),count=obj2int(a[2]);uint8_t bytes[512];unsigned len=sizeof(bytes);uint32_t t=model(a[0]);
 if(offset<0||count<0||count>512||p4_nn_transfer(6,&t,offset,0,NULL,count,bytes,&len))return fail(indexOutOfRangeError);
 OBJ out=newObj(ByteArrayType,(len+3)/4,zeroObj);if(out==falseObj)return out;setByteCountAdjust(out,len);memcpy(&FIELD(out,0),bytes,len);return out;
}
static uint32_t get32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static void put32(uint8_t *p,uint32_t value){for(unsigned i=0;i<4;i++)p[i]=value>>(8*i);}
void p4_nn_message(int type,int n,char *body)
{
 if(type!=216||n<24||memcmp(body,"P4NN",4))return;
 const uint8_t *p=(const uint8_t *)body;unsigned op=p[4],count=p[18]|(unsigned)p[19]<<8;uint32_t t=get32(p+10);
 uint8_t out[1010]={0};put32(out,get32(p+6));out[4]=1;out[5]=op;put32(out+6,t);unsigned bytes=1000;
 bool payload=op==1||op==2||op==7||op==8;
 if(p[5]==1&&count<=512&&n==(int)(24+(payload?count:0))){out[4]=p4_nn_transfer(op,&t,get32(p+14),get32(p+20),p+24,count,out+10,&bytes);put32(out+6,t);}else bytes=0;
 if(hasOutputSpace(bytes+15))waitAndSendMessage(216,0,bytes+10,(char *)out);
}
