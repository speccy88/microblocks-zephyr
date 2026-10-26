/* SPDX-License-Identifier: MIT */
#ifndef MB_STEPS_H
#define MB_STEPS_H
#include <stdbool.h>
#include <stdint.h>
#define MB_STEP_COUNT 16
#define MB_TRANSITION_COUNT 24
typedef enum {MB_STEP_OK,MB_STEP_RANGE,MB_STEP_RUNNING,MB_STEP_MISSING,MB_STEP_DUPLICATE,MB_STEP_NO_INITIAL,MB_STEP_REWIND} mb_step_error;
typedef struct {uint16_t from,to;uint32_t after_ms;bool defined,condition;} mb_transition;
typedef struct {
 uint16_t defined,initial,active,entered,exited;uint32_t fired;
 bool running;uint64_t now,entry_ms[MB_STEP_COUNT];
 mb_transition transitions[MB_TRANSITION_COUNT];
} mb_steps;
void mb_steps_init(mb_steps *s,uint64_t now);
mb_step_error mb_steps_clear(mb_steps *s);
mb_step_error mb_steps_add(mb_steps *s,unsigned step,bool initial);
mb_step_error mb_steps_transition(mb_steps *s,unsigned id,uint16_t from,uint16_t to,uint32_t after_ms);
mb_step_error mb_steps_condition(mb_steps *s,unsigned id,bool condition);
mb_step_error mb_steps_start(mb_steps *s,uint64_t now);
void mb_steps_stop(mb_steps *s);
mb_step_error mb_steps_scan(mb_steps *s,uint64_t now);
mb_step_error mb_steps_elapsed(mb_steps *s,unsigned step,uint64_t now,uint64_t *elapsed);
const char *mb_step_error_text(mb_step_error e);
#endif
