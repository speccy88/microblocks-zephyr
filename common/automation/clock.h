/* SPDX-License-Identifier: MIT */
#ifndef MB_CLOCK_H
#define MB_CLOCK_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define MB_TIMER_COUNT 8
#define MB_DAY_MS INT64_C(86400000)
typedef enum {MB_TIME_OK,MB_TIME_RANGE,MB_TIME_INVALID,MB_TIME_FULL,MB_TIME_STALE,MB_TIME_REWIND} mb_time_error;
typedef enum {MB_TIMER_INTERVAL,MB_TIMER_AT,MB_TIMER_DAILY} mb_timer_mode;
typedef struct {
 uint32_t generation,missed;uint64_t next_mono;
 int64_t deadline,next_day;uint32_t period;uint16_t minute;
 uint8_t mode;bool allocated,active,pending,catch_up;
} mb_timer;
typedef struct {
 uint64_t mono;int64_t wall_ms;int16_t offset_minutes;bool wall_valid;
 mb_timer timers[MB_TIMER_COUNT];
} mb_clock;
void mb_clock_init(mb_clock *c,uint64_t now);
mb_time_error mb_clock_tick(mb_clock *c,uint64_t now);
mb_time_error mb_clock_set(mb_clock *c,int64_t utc_ms);
void mb_clock_invalidate(mb_clock *c);
mb_time_error mb_clock_offset(mb_clock *c,int minutes);
mb_time_error mb_clock_parse(const char *iso,size_t length,int64_t *utc_ms);
bool mb_clock_format(int64_t utc_ms,char iso[21]);
mb_time_error mb_timer_create(mb_clock *c,mb_timer_mode mode,uint32_t interval,int64_t at,int hour,int minute,bool catch_up,uint32_t *handle);
mb_time_error mb_timer_query(mb_clock *c,uint32_t handle,bool take,bool *ready,uint32_t *missed);
mb_time_error mb_timer_stop(mb_clock *c,uint32_t handle);
mb_time_error mb_timer_restart(mb_clock *c,uint32_t handle);
mb_time_error mb_timer_delete(mb_clock *c,uint32_t handle);
void mb_timers_stop_all(mb_clock *c);
const char *mb_time_error_text(mb_time_error e);
#endif
