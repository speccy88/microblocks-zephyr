/* SPDX-License-Identifier: MIT */
#include "clock.h"
#include "steps.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#define OK(x) assert((x)==0)
static int64_t utc(const char *s){int64_t ms;OK(mb_clock_parse(s,strlen(s),&ms));return ms;}
static bool ready(mb_clock *c,uint32_t r,bool take){bool yes=false;OK(mb_timer_query(c,r,take,&yes,NULL));return yes;}
static uint32_t lost(mb_clock *c,uint32_t r){uint32_t n=0;OK(mb_timer_query(c,r,false,NULL,&n));return n;}
static void clocks(void){
 mb_clock c;mb_clock_init(&c,1000);uint32_t r=0,a=0,b=0;
 assert(!c.wall_valid);assert(mb_timer_create(&c,MB_TIMER_DAILY,0,0,12,0,true,&r)==MB_TIME_INVALID);
 OK(mb_timer_create(&c,MB_TIMER_INTERVAL,100,0,0,0,true,&r));OK(mb_clock_tick(&c,1099));assert(!ready(&c,r,false));
 OK(mb_clock_tick(&c,1100));assert(ready(&c,r,false));assert(ready(&c,r,true));assert(!ready(&c,r,false));
 OK(mb_clock_tick(&c,1500));assert(ready(&c,r,true));assert(lost(&c,r)==3);
 mb_clock original=c;assert(mb_clock_tick(&c,1499)==MB_TIME_REWIND);assert(!memcmp(&c,&original,sizeof(c)));
 OK(mb_clock_set(&c,utc("2026-10-26T09:00:00Z")));OK(mb_clock_offset(&c,60));
 OK(mb_clock_set(&c,utc("2020-01-01T00:00:00Z")));OK(mb_clock_tick(&c,1599));assert(!ready(&c,r,false));OK(mb_clock_tick(&c,1600));assert(ready(&c,r,true));
 OK(mb_timer_stop(&c,r));OK(mb_clock_tick(&c,2600));assert(!ready(&c,r,false));OK(mb_timer_restart(&c,r));OK(mb_clock_tick(&c,2700));assert(ready(&c,r,true));
 OK(mb_timer_delete(&c,r));assert(mb_timer_query(&c,r,false,NULL,NULL)==MB_TIME_STALE);
 OK(mb_timer_create(&c,MB_TIMER_INTERVAL,100,0,0,0,true,&a));assert(a!=r);assert(mb_timer_restart(&c,r)==MB_TIME_STALE);
 mb_timers_stop_all(&c);assert(mb_timer_query(&c,a,false,NULL,NULL)==MB_TIME_STALE);
 OK(mb_clock_set(&c,utc("2026-10-26T09:00:00Z")));
 OK(mb_timer_create(&c,MB_TIMER_AT,0,c.wall_ms+1000,0,0,false,&a));OK(mb_timer_create(&c,MB_TIMER_AT,0,c.wall_ms+1000,0,0,true,&b));
 OK(mb_clock_set(&c,c.wall_ms+2000));assert(!ready(&c,a,false)&&lost(&c,a)==1);assert(ready(&c,b,true));
 OK(mb_clock_set(&c,c.wall_ms-3000));OK(mb_clock_tick(&c,5700));assert(!ready(&c,b,false));
 mb_timers_stop_all(&c);OK(mb_clock_set(&c,utc("2026-10-26T09:00:00Z")));
 OK(mb_timer_create(&c,MB_TIMER_AT,0,c.wall_ms+1000,0,0,true,&a));mb_clock_invalidate(&c);OK(mb_clock_tick(&c,10000));assert(!ready(&c,a,false));
 OK(mb_clock_set(&c,utc("2026-10-26T09:00:02Z")));assert(ready(&c,a,true));
 mb_timers_stop_all(&c);OK(mb_clock_offset(&c,-300));OK(mb_clock_set(&c,utc("2026-03-08T06:59:50Z")));
 OK(mb_timer_create(&c,MB_TIMER_DAILY,0,0,2,30,false,&a));OK(mb_timer_create(&c,MB_TIMER_DAILY,0,0,2,30,true,&b));
 OK(mb_clock_offset(&c,-240));assert(!ready(&c,a,false)&&lost(&c,a)==1);assert(ready(&c,b,true));
 mb_timers_stop_all(&c);OK(mb_clock_set(&c,utc("2026-11-01T05:29:50Z")));
 OK(mb_timer_create(&c,MB_TIMER_DAILY,0,0,1,30,true,&a));OK(mb_clock_tick(&c,30000));assert(ready(&c,a,true));
 OK(mb_clock_offset(&c,-300));OK(mb_clock_tick(&c,3630000));assert(!ready(&c,a,false));
 OK(mb_clock_tick(&c,90030000));assert(ready(&c,a,true));assert(!ready(&c,a,false));
 mb_timers_stop_all(&c);for(unsigned i=0;i<MB_TIMER_COUNT;i++)OK(mb_timer_create(&c,MB_TIMER_INTERVAL,10,0,INT_MAX,INT_MAX,false,&r));
 assert(mb_timer_create(&c,MB_TIMER_INTERVAL,10,0,0,0,false,&r)==MB_TIME_FULL);
 mb_timers_stop_all(&c);assert(mb_timer_create(&c,MB_TIMER_INTERVAL,9,0,0,0,false,&r)==MB_TIME_RANGE);
 assert(mb_clock_offset(&c,841)==MB_TIME_RANGE);mb_clock_init(&c,UINT64_MAX-5);assert(mb_timer_create(&c,MB_TIMER_INTERVAL,10,0,0,0,false,&r)==MB_TIME_RANGE);
 mb_clock_init(&c,0);OK(mb_timer_create(&c,MB_TIMER_INTERVAL,10,0,0,0,false,&r));OK(mb_clock_tick(&c,UINT64_C(100000000000)));assert(lost(&c,r)==UINT32_MAX);
 int64_t ms;assert(mb_clock_parse("2100-02-29T00:00:00Z",20,&ms)==MB_TIME_RANGE);assert(mb_clock_parse("2024-01-01T00:00:60Z",20,&ms)==MB_TIME_RANGE);
 assert(utc("1970-01-01T00:00:00Z")==0);assert(utc("2000-01-01T00:00:00Z")==INT64_C(946684800000));
 const char *dates[]={"2000-02-29T23:59:59Z","2024-02-29T12:34:56Z","2100-03-01T00:00:00Z","2399-12-31T23:59:59Z"};
 for(unsigned i=0;i<sizeof(dates)/sizeof(dates[0]);i++){char formatted[21];assert(mb_clock_format(utc(dates[i]),formatted));assert(!strcmp(formatted,dates[i]));}
}
static void steps(void){
 mb_steps s;mb_steps_init(&s,0);assert(mb_steps_start(&s,0)==MB_STEP_NO_INITIAL);
 assert(mb_steps_add(&s,0,true)==MB_STEP_RANGE);OK(mb_steps_add(&s,1,true));OK(mb_steps_add(&s,2,false));OK(mb_steps_add(&s,3,false));OK(mb_steps_add(&s,4,false));
 assert(mb_steps_add(&s,1,false)==MB_STEP_DUPLICATE);assert(mb_steps_transition(&s,1,16,2,0)==MB_STEP_MISSING);
 OK(mb_steps_transition(&s,1,1,2,0));OK(mb_steps_transition(&s,2,2,4,0));OK(mb_steps_transition(&s,3,1,8,0));
 OK(mb_steps_start(&s,0));assert(s.active==1&&s.entered==1);assert(mb_steps_add(&s,5,false)==MB_STEP_RUNNING);
 OK(mb_steps_condition(&s,1,true));OK(mb_steps_condition(&s,2,true));OK(mb_steps_condition(&s,3,true));OK(mb_steps_scan(&s,10));
 assert(s.active==2&&s.fired==1&&s.entered==2&&s.exited==1); /* no cascade; lowest ID wins conflict */
 OK(mb_steps_scan(&s,20));assert(s.active==2&&s.fired==0); /* guards do not persist */
 OK(mb_steps_condition(&s,2,true));OK(mb_steps_scan(&s,30));assert(s.active==4&&s.fired==2);
 uint64_t elapsed;OK(mb_steps_elapsed(&s,3,55,&elapsed));assert(elapsed==25);mb_steps saved=s;assert(mb_steps_scan(&s,29)==MB_STEP_REWIND);assert(!memcmp(&s,&saved,sizeof(s)));
 mb_steps_stop(&s);assert(!s.active&&!s.fired&&!s.running);OK(mb_steps_clear(&s));
 for(unsigned i=1;i<=4;i++)OK(mb_steps_add(&s,i,i==1));
 OK(mb_steps_transition(&s,1,1,6,0));OK(mb_steps_transition(&s,2,6,8,100));OK(mb_steps_transition(&s,3,8,8,10));
 OK(mb_steps_start(&s,100));OK(mb_steps_condition(&s,1,true));OK(mb_steps_scan(&s,110));assert(s.active==6); /* fork */
 OK(mb_steps_condition(&s,2,true));OK(mb_steps_scan(&s,209));assert(s.active==6);OK(mb_steps_condition(&s,2,true));OK(mb_steps_scan(&s,210));assert(s.active==8); /* timed join */
 OK(mb_steps_condition(&s,3,true));OK(mb_steps_scan(&s,220));assert(s.active==8&&s.entered==8&&s.exited==8);OK(mb_steps_elapsed(&s,4,225,&elapsed));assert(elapsed==5);
 mb_steps_stop(&s);OK(mb_steps_clear(&s));OK(mb_steps_add(&s,1,true));OK(mb_steps_add(&s,2,true));OK(mb_steps_add(&s,3,false));OK(mb_steps_add(&s,4,false));
 OK(mb_steps_transition(&s,1,1,4,0));OK(mb_steps_transition(&s,2,2,8,0));OK(mb_steps_start(&s,300));OK(mb_steps_condition(&s,1,true));OK(mb_steps_condition(&s,2,true));OK(mb_steps_scan(&s,310));assert(s.active==12&&s.fired==3); /* independent simultaneous edges */
 mb_steps_stop(&s);assert(!s.active&&!s.entered&&!s.exited);assert(mb_steps_condition(&s,25,true)==MB_STEP_RANGE);
}
int main(void){clocks();steps();puts("{\"result\":\"PASS\",\"clock\":\"fake monotonic/UTC/offset\",\"steps\":\"deterministic logical state only\",\"hardware_access\":false}");}
