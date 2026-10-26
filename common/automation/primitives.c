/* SPDX-License-Identifier: MPL-2.0 */
/* Zephyr supplies uptime; the clock/timer and step cores are portable C. */
#include "vm/interp.h"
#include "primitives.h"
#include "clock.h"
#include "steps.h"
#include <zephyr/kernel.h>
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#if defined(CONFIG_ESP_SPIRAM)
#define AUTO_STATE __attribute__((section(".ext_ram.bss.automation"),aligned(16)))
#else
#define AUTO_STATE
#endif
static mb_clock clock_state AUTO_STATE;
static mb_steps step_state AUTO_STATE;
static mb_time_error clock_error;
static mb_step_error step_error;
static bool initialized;
static uint64_t now(void){return (uint64_t)k_uptime_get();}
static OBJ string(const char *s){return newStringFromBytes(s,strlen(s));}
static OBJ clock_result(mb_time_error e){clock_error=e;return e==MB_TIME_OK?trueObj:falseObj;}
static OBJ step_result(mb_step_error e){step_error=e;return e==MB_STEP_OK?trueObj:falseObj;}
static bool integers(int n,OBJ *a,int expected){if(n!=expected){fail(notEnoughArguments);return false;}for(int i=0;i<n;i++)if(!isInt(a[i])){fail(needsIntegerError);return false;}return true;}
static bool boolean(OBJ a){return a==trueObj||a==falseObj;}
static bool iso(OBJ a,int64_t *ms){
 if(!IS_TYPE(a,StringType)){fail(needsStringError);return false;}
 size_t cap=4*(size_t)WORDS(a);const char *s=obj2str(a);
 if(cap<21||cap>24)return false;
 for(size_t i=20;i<cap;i++)if(s[i])return false;
 return mb_clock_parse(s,20,ms)==MB_TIME_OK;
}
void mb_automation_poll(void){if(initialized){mb_time_error e=mb_clock_tick(&clock_state,now());if(e)clock_error=e;}}
void mb_automation_stop(void){if(initialized){mb_timers_stop_all(&clock_state);mb_steps_stop(&step_state);}}
static OBJ valid(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);mb_automation_poll();return clock_state.wall_valid?trueObj:falseObj;}
static OBJ source(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);mb_automation_poll();return string(clock_state.wall_valid?"manual":"unset");}
static OBJ utc_text(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);mb_automation_poll();if(!clock_state.wall_valid){clock_error=MB_TIME_INVALID;return falseObj;}char text[21];if(!mb_clock_format(clock_state.wall_ms,text)){clock_error=MB_TIME_RANGE;return falseObj;}clock_error=MB_TIME_OK;return string(text);}
static OBJ local_text(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);mb_automation_poll();if(!clock_state.wall_valid){clock_error=MB_TIME_INVALID;return falseObj;}char time[21],text[28];int offset=clock_state.offset_minutes,absolute=offset<0?-offset:offset;if(!mb_clock_format(clock_state.wall_ms+(int64_t)offset*60000,time)){clock_error=MB_TIME_RANGE;return falseObj;}snprintf(text,sizeof(text),"%.19s%c%02d:%02d",time,offset<0?'-':'+',absolute/60,absolute%60);clock_error=MB_TIME_OK;return string(text);}
static OBJ set_utc(int n,OBJ *a){if(n!=1)return fail(notEnoughArguments);int64_t ms;mb_automation_poll();return clock_result(iso(a[0],&ms)?mb_clock_set(&clock_state,ms):MB_TIME_RANGE);}
static OBJ invalidate(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);mb_clock_invalidate(&clock_state);return clock_result(MB_TIME_OK);}
static OBJ offset(int n,OBJ *a){if(!integers(n,a,1))return falseObj;mb_automation_poll();return clock_result(mb_clock_offset(&clock_state,obj2int(a[0])));}
static OBJ uptime(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char text[32];snprintf(text,sizeof(text),"%" PRIu64,now());return string(text);}
static OBJ clock_status(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):string(mb_time_error_text(clock_error));}
static OBJ unavailable(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):falseObj;}
static OBJ timer_created(mb_time_error e,uint32_t ref){clock_error=e;return e==MB_TIME_OK?int2obj(ref):falseObj;}
static OBJ interval(int n,OBJ *a){if(!integers(n,a,1))return falseObj;uint32_t ref=0;mb_automation_poll();mb_time_error e=mb_timer_create(&clock_state,MB_TIMER_INTERVAL,(uint32_t)obj2int(a[0]),0,0,0,true,&ref);return timer_created(e,ref);}
static OBJ at(int n,OBJ *a){if(n!=2)return fail(notEnoughArguments);int64_t ms;uint32_t ref=0;mb_automation_poll();if(!iso(a[0],&ms)||!boolean(a[1]))return clock_result(MB_TIME_RANGE);mb_time_error e=mb_timer_create(&clock_state,MB_TIMER_AT,0,ms,0,0,a[1]==trueObj,&ref);return timer_created(e,ref);}
static OBJ daily(int n,OBJ *a){if(n!=3||!isInt(a[0])||!isInt(a[1]))return fail(needsIntegerError);if(!boolean(a[2]))return clock_result(MB_TIME_RANGE);uint32_t ref=0;mb_automation_poll();mb_time_error e=mb_timer_create(&clock_state,MB_TIMER_DAILY,0,0,obj2int(a[0]),obj2int(a[1]),a[2]==trueObj,&ref);return timer_created(e,ref);}
static OBJ query(int n,OBJ *a,bool take,bool missed){if(!integers(n,a,1))return falseObj;mb_automation_poll();bool ready=false;uint32_t count=0;clock_error=mb_timer_query(&clock_state,(uint32_t)obj2int(a[0]),take,&ready,&count);if(clock_error)return falseObj;return missed?int2obj(count>1073741823?1073741823:count):(ready?trueObj:falseObj);}
static OBJ timer_ready(int n,OBJ *a){return query(n,a,false,false);}
static OBJ timer_take(int n,OBJ *a){return query(n,a,true,false);}
static OBJ timer_missed(int n,OBJ *a){return query(n,a,false,true);}
#define TIMER_ACTION(name,fn) static OBJ name(int n,OBJ *a){if(!integers(n,a,1))return falseObj;mb_automation_poll();return clock_result(fn(&clock_state,(uint32_t)obj2int(a[0])));}
TIMER_ACTION(timer_stop,mb_timer_stop) TIMER_ACTION(timer_restart,mb_timer_restart) TIMER_ACTION(timer_delete,mb_timer_delete)
static OBJ flow_clear(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):step_result(mb_steps_clear(&step_state));}
static OBJ flow_add(int n,OBJ *a){if(n!=2||!isInt(a[0]))return fail(needsIntegerError);if(!boolean(a[1]))return step_result(MB_STEP_RANGE);return step_result(mb_steps_add(&step_state,(unsigned)obj2int(a[0]),a[1]==trueObj));}
static OBJ flow_transition(int n,OBJ *a){if(!integers(n,a,3))return falseObj;int from=obj2int(a[1]),to=obj2int(a[2]);if(from<1||from>16||to<1||to>16)return step_result(MB_STEP_RANGE);return step_result(mb_steps_transition(&step_state,(unsigned)obj2int(a[0]),(uint16_t)(1u<<(from-1)),(uint16_t)(1u<<(to-1)),0));}
static OBJ flow_groups(int n,OBJ *a){if(!integers(n,a,4))return falseObj;int from=obj2int(a[1]),to=obj2int(a[2]),delay=obj2int(a[3]);if(from<1||from>65535||to<1||to>65535||delay<0)return step_result(MB_STEP_RANGE);return step_result(mb_steps_transition(&step_state,(unsigned)obj2int(a[0]),(uint16_t)from,(uint16_t)to,(uint32_t)delay));}
static OBJ flow_condition(int n,OBJ *a){if(n!=2||!isInt(a[0]))return fail(needsIntegerError);if(!boolean(a[1]))return step_result(MB_STEP_RANGE);return step_result(mb_steps_condition(&step_state,(unsigned)obj2int(a[0]),a[1]==trueObj));}
static OBJ flow_start(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):step_result(mb_steps_start(&step_state,now()));}
static OBJ flow_stop(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);mb_steps_stop(&step_state);return step_result(MB_STEP_OK);}
static OBJ flow_scan(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):step_result(mb_steps_scan(&step_state,now()));}
static OBJ flow_running(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):(step_state.running?trueObj:falseObj);}
static OBJ flow_flag(int n,OBJ *a,uint16_t flags){if(!integers(n,a,1))return falseObj;int step=obj2int(a[0]);if(step<1||step>16){step_error=MB_STEP_RANGE;return falseObj;}if(!(step_state.defined&(1u<<(step-1)))){step_error=MB_STEP_MISSING;return falseObj;}step_error=MB_STEP_OK;return flags&(1u<<(step-1))?trueObj:falseObj;}
static OBJ flow_active(int n,OBJ *a){return flow_flag(n,a,step_state.active);}
static OBJ flow_entered(int n,OBJ *a){return flow_flag(n,a,step_state.entered);}
static OBJ flow_exited(int n,OBJ *a){return flow_flag(n,a,step_state.exited);}
static OBJ flow_elapsed(int n,OBJ *a){if(!integers(n,a,1))return falseObj;uint64_t elapsed;step_error=mb_steps_elapsed(&step_state,(unsigned)obj2int(a[0]),now(),&elapsed);return step_error?falseObj:int2obj(elapsed>1073741823?1073741823:elapsed);}
static OBJ flow_active_text(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char text[64];size_t used=0;for(unsigned i=0;i<16;i++)if(step_state.active&(1u<<i))used+=(size_t)snprintf(text+used,sizeof(text)-used,"%s%u",used?", ":"",i+1);return string(used?text:"none");}
static OBJ flow_group(int n,OBJ *a){if(!integers(n,a,2))return falseObj;int group=obj2int(a[0]),step=obj2int(a[1]);if(group<0||group>65535||step<1||step>16){step_error=MB_STEP_RANGE;return falseObj;}return int2obj(group|(1u<<(step-1)));}
static OBJ flow_status(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):string(mb_step_error_text(step_error));}
static PrimEntry clock_entries[]={
 {"valid",valid},{"source",source},{"utc",utc_text},{"local",local_text},{"setUTC",set_utc},{"invalidate",invalidate},{"offset",offset},{"uptime",uptime},{"status",clock_status},{"rtcAvailable",unavailable},{"ntpAvailable",unavailable},
 {"interval",interval},{"at",at},{"daily",daily},{"ready",timer_ready},{"take",timer_take},{"missed",timer_missed},{"stop",timer_stop},{"restart",timer_restart},{"delete",timer_delete}};
static PrimEntry step_entries[]={
 {"clear",flow_clear},{"add",flow_add},{"transition",flow_transition},{"groups",flow_groups},{"condition",flow_condition},{"start",flow_start},{"stop",flow_stop},{"scan",flow_scan},{"running",flow_running},
 {"active",flow_active},{"entered",flow_entered},{"exited",flow_exited},{"elapsed",flow_elapsed},{"activeText",flow_active_text},{"group",flow_group},{"status",flow_status}};
void addClockPrims(void){if(!initialized){mb_clock_init(&clock_state,now());mb_steps_init(&step_state,now());initialized=true;}addPrimitiveSet(ClockPrims,"clock",sizeof(clock_entries)/sizeof(clock_entries[0]),clock_entries);}
void addStepPrims(void){addPrimitiveSet(StepPrims,"steps",sizeof(step_entries)/sizeof(step_entries[0]),step_entries);}
