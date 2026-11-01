/* SPDX-License-Identifier: MIT - HOST TEST ONLY, never linked into firmware. */
#include "vm/interp.h"
#include "steps.h"
#include <stdio.h>
#include <string.h>
_Static_assert(SFCTestPrims==24,"Compiler/native test step primitive index must match");
static mb_steps flow;static uint64_t test_now;static unsigned scans;
static OBJ result(mb_step_error e){return e==MB_STEP_OK?trueObj:falseObj;}
static int ints(int n,OBJ *a,int count){if(n!=count)return 0;for(int i=0;i<n;i++)if(!isInt(a[i]))return 0;return 1;}
static OBJ clear(int n,OBJ *a){(void)a;return n?falseObj:result(mb_steps_clear(&flow));}
static OBJ stop(int n,OBJ *a){(void)a;if(n)return falseObj;mb_steps_stop(&flow);return trueObj;}
static OBJ add(int n,OBJ *a){if(n!=2||!isInt(a[0])||(a[1]!=trueObj&&a[1]!=falseObj))return falseObj;return result(mb_steps_add(&flow,obj2int(a[0]),a[1]==trueObj));}
static OBJ groups(int n,OBJ *a){if(!ints(n,a,4))return falseObj;return result(mb_steps_transition(&flow,obj2int(a[0]),(uint16_t)obj2int(a[1]),(uint16_t)obj2int(a[2]),obj2int(a[3])));}
static OBJ condition(int n,OBJ *a){if(n!=2||!isInt(a[0])||(a[1]!=trueObj&&a[1]!=falseObj))return falseObj;return result(mb_steps_condition(&flow,obj2int(a[0]),a[1]==trueObj));}
static OBJ start(int n,OBJ *a){(void)a;return n?falseObj:result(mb_steps_start(&flow,test_now));}
static OBJ scan(int n,OBJ *a){(void)a;if(n)return falseObj;scans++;return result(mb_steps_scan(&flow,test_now));}
static OBJ flag(int n,OBJ *a,uint16_t mask){if(!ints(n,a,1)||obj2int(a[0])<1||obj2int(a[0])>16)return falseObj;return mask&(1u<<(obj2int(a[0])-1))?trueObj:falseObj;}
static OBJ active(int n,OBJ *a){return flag(n,a,flow.active);}
static OBJ entered(int n,OBJ *a){return flag(n,a,flow.entered);}
static OBJ exited(int n,OBJ *a){return flag(n,a,flow.exited);}
static OBJ status(int n,OBJ *a){(void)a;return n?falseObj:newStringFromBytes("HOST TEST",9);}
static OBJ now(int n,OBJ *a){if(!ints(n,a,1)||obj2int(a[0])<0||(uint64_t)obj2int(a[0])<test_now)return falseObj;test_now=obj2int(a[0]);return trueObj;}
static OBJ snapshot(int n,OBJ *a){(void)a;if(n)return falseObj;char out[240];int len=snprintf(out,sizeof(out),"{\"active\":%u,\"entered\":%u,\"exited\":%u,\"fired\":%u,\"now\":%u,\"scans\":%u,\"running\":%s}",(unsigned)flow.active,(unsigned)flow.entered,(unsigned)flow.exited,(unsigned)flow.fired,(unsigned)test_now,scans,flow.running?"true":"false");return newStringFromBytes(out,len);}
static PrimEntry entries[]={{"clear",clear},{"stop",stop},{"add",add},{"groups",groups},{"condition",condition},{"start",start},{"scan",scan},{"active",active},{"entered",entered},{"exited",exited},{"status",status},{"testNow",now},{"testSnapshot",snapshot}};
void addSFCTestPrims(void){mb_steps_init(&flow,0);test_now=0;scans=0;addPrimitiveSet(SFCTestPrims,"steps",sizeof(entries)/sizeof(entries[0]),entries);}
