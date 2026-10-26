/* SPDX-License-Identifier: MIT */
#include "clock.h"
#include <string.h>
#include <stdio.h>
#include <limits.h>
#define MAX_WALL_MS INT64_C(13569465599999) /* 2399-12-31 23:59:59.999 UTC */
static bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}
static int month_days(int y,int m){static const int days[]={31,28,31,30,31,30,31,31,30,31,30,31};return days[m-1]+(m==2&&leap(y));}
static int64_t floor_day(int64_t ms){return ms>=0?ms/MB_DAY_MS:-((-ms+MB_DAY_MS-1)/MB_DAY_MS);}
static void missed(mb_timer *t,uint64_t count){t->missed=count>UINT32_MAX-t->missed?UINT32_MAX:t->missed+(uint32_t)count;}
static void notify(mb_timer *t,uint64_t count,bool jump){
 if(jump&&!t->catch_up){missed(t,count);return;}
 if(t->pending)missed(t,count);else {t->pending=true;missed(t,count-1);}
}
static void wall_tick(mb_clock *c,bool jump){
 if(!c->wall_valid)return;
 int64_t local=c->wall_ms+(int64_t)c->offset_minutes*60000;
 for(unsigned i=0;i<MB_TIMER_COUNT;i++){
  mb_timer *t=&c->timers[i];if(!t->allocated||!t->active)continue;
  if(t->mode==MB_TIMER_AT&&c->wall_ms>=t->deadline){notify(t,1,jump);t->active=false;}
  if(t->mode==MB_TIMER_DAILY){
   int64_t day=floor_day(local-(int64_t)t->minute*60000);
   if(day>=t->next_day){notify(t,(uint64_t)(day-t->next_day+1),jump);t->next_day=day+1;}
  }
 }
}
void mb_clock_init(mb_clock *c,uint64_t now){memset(c,0,sizeof(*c));c->mono=now;}
void mb_clock_invalidate(mb_clock *c){c->wall_valid=false;for(unsigned i=0;i<MB_TIMER_COUNT;i++)if(c->timers[i].mode!=MB_TIMER_INTERVAL)c->timers[i].pending=false;}
mb_time_error mb_clock_tick(mb_clock *c,uint64_t now){
 if(now<c->mono)return MB_TIME_REWIND;
 uint64_t delta=now-c->mono;c->mono=now;
 if(c->wall_valid){if(delta>(uint64_t)(MAX_WALL_MS-c->wall_ms))mb_clock_invalidate(c);else c->wall_ms+=(int64_t)delta;}
 for(unsigned i=0;i<MB_TIMER_COUNT;i++){
  mb_timer *t=&c->timers[i];
  if(!t->allocated||!t->active||t->mode!=MB_TIMER_INTERVAL||now<t->next_mono)continue;
  uint64_t count=(now-t->next_mono)/t->period+1;notify(t,count,false);
  uint64_t remainder=t->period-(now-t->next_mono)%t->period;
  if(now>UINT64_MAX-remainder)t->active=false;else t->next_mono=now+remainder;
 }
 wall_tick(c,false);return MB_TIME_OK;
}
mb_time_error mb_clock_set(mb_clock *c,int64_t ms){if(ms<0||ms>MAX_WALL_MS)return MB_TIME_RANGE;c->wall_ms=ms;c->wall_valid=true;wall_tick(c,true);return MB_TIME_OK;}
mb_time_error mb_clock_offset(mb_clock *c,int minutes){if(minutes < -840||minutes>840)return MB_TIME_RANGE;c->offset_minutes=(int16_t)minutes;wall_tick(c,true);return MB_TIME_OK;}
static int digits(const char *s,int n){int v=0;for(int i=0;i<n;i++){if(s[i]<'0'||s[i]>'9')return -1;v=v*10+s[i]-'0';}return v;}
mb_time_error mb_clock_parse(const char *s,size_t n,int64_t *ms){
 if(!s||!ms||n!=20||s[4]!='-'||s[7]!='-'||s[10]!='T'||s[13]!=':'||s[16]!=':'||s[19]!='Z')return MB_TIME_RANGE;
 int y=digits(s,4),m=digits(s+5,2),d=digits(s+8,2),h=digits(s+11,2),min=digits(s+14,2),sec=digits(s+17,2);
 if(y<1970||y>2399||m<1||m>12||d<1||d>month_days(y,m)||h<0||h>23||min<0||min>59||sec<0||sec>59)return MB_TIME_RANGE;
 int64_t days=0;for(int i=1970;i<y;i++)days+=365+leap(i);for(int i=1;i<m;i++)days+=month_days(y,i);
 *ms=(days+d-1)*MB_DAY_MS+h*INT64_C(3600000)+min*60000+sec*1000;return MB_TIME_OK;
}
bool mb_clock_format(int64_t ms,char out[21]){
 if(ms<0||ms>MAX_WALL_MS)return false;
 int64_t days=ms/MB_DAY_MS;int y=1970,m=1;
 while(days>=365+leap(y)){days-=365+leap(y);y++;}
 while(days>=month_days(y,m)){days-=month_days(y,m);m++;}
 int64_t seconds=ms/1000%86400;
 return snprintf(out,21,"%04d-%02d-%02dT%02d:%02d:%02dZ",y,m,(int)days+1,(int)(seconds/3600),(int)(seconds/60%60),(int)(seconds%60))==20;
}
static mb_timer *find(mb_clock *c,uint32_t ref){unsigned i=ref&7;uint32_t generation=ref>>3;mb_timer *t=&c->timers[i];return t->allocated&&generation&&t->generation==generation?t:NULL;}
static mb_time_error arm(mb_clock *c,mb_timer *t){
 if(t->mode!=MB_TIMER_INTERVAL&&!c->wall_valid)return MB_TIME_INVALID;
 if(t->mode==MB_TIMER_INTERVAL){if(c->mono>UINT64_MAX-t->period)return MB_TIME_RANGE;t->next_mono=c->mono+t->period;}
 if(t->mode==MB_TIMER_DAILY){int64_t local=c->wall_ms+(int64_t)c->offset_minutes*60000;t->next_day=floor_day(local);if(local-t->next_day*MB_DAY_MS>(int64_t)t->minute*60000)t->next_day++;}
 t->pending=false;t->missed=0;t->active=true;return MB_TIME_OK;
}
mb_time_error mb_timer_create(mb_clock *c,mb_timer_mode mode,uint32_t period,int64_t at,int h,int min,bool catch_up,uint32_t *ref){
 if(!ref||mode<MB_TIMER_INTERVAL||mode>MB_TIMER_DAILY)return MB_TIME_RANGE;
 if(mode==MB_TIMER_INTERVAL&&(period<10||period>86400000))return MB_TIME_RANGE;
 if(mode!=MB_TIMER_INTERVAL&&!c->wall_valid)return MB_TIME_INVALID;
 if(mode==MB_TIMER_AT&&(at<=c->wall_ms||at>MAX_WALL_MS))return MB_TIME_RANGE;
 if(mode==MB_TIMER_DAILY&&(h<0||h>23||min<0||min>59))return MB_TIME_RANGE;
 for(unsigned i=0;i<MB_TIMER_COUNT;i++){
  mb_timer *t=&c->timers[i];if(t->allocated||t->generation>=UINT32_C(0x07ffffff))continue;
  mb_timer next={.generation=t->generation+1,.allocated=true,.mode=(uint8_t)mode,.period=period,.deadline=at,.minute=(uint16_t)(mode==MB_TIMER_DAILY?h*60+min:0),.catch_up=catch_up};
  mb_time_error e=arm(c,&next);if(e)return e;*t=next;*ref=(next.generation<<3)|i;return MB_TIME_OK;
 }
 return MB_TIME_FULL;
}
mb_time_error mb_timer_query(mb_clock *c,uint32_t ref,bool take,bool *ready,uint32_t *lost){mb_timer *t=find(c,ref);if(!t)return MB_TIME_STALE;if(ready)*ready=t->pending;if(lost)*lost=t->missed;if(take)t->pending=false;return MB_TIME_OK;}
mb_time_error mb_timer_stop(mb_clock *c,uint32_t ref){mb_timer *t=find(c,ref);if(!t)return MB_TIME_STALE;t->active=t->pending=false;return MB_TIME_OK;}
mb_time_error mb_timer_restart(mb_clock *c,uint32_t ref){mb_timer *t=find(c,ref);return t?arm(c,t):MB_TIME_STALE;}
mb_time_error mb_timer_delete(mb_clock *c,uint32_t ref){mb_timer *t=find(c,ref);if(!t)return MB_TIME_STALE;t->allocated=t->active=t->pending=false;return MB_TIME_OK;}
void mb_timers_stop_all(mb_clock *c){for(unsigned i=0;i<MB_TIMER_COUNT;i++)c->timers[i].allocated=c->timers[i].active=c->timers[i].pending=false;}
const char *mb_time_error_text(mb_time_error e){static const char *s[]={"OK","Time or timer value out of range","Wall clock is not set","All eight timer slots are in use","Expired timer reference","Monotonic time moved backward"};return (unsigned)e<sizeof(s)/sizeof(s[0])?s[e]:"Unknown clock error";}
