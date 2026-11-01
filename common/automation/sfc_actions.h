/* SPDX-License-Identifier: MIT - host-tested boundary requests, not GPIO. */
#ifndef MB_SFC_ACTIONS_H
#define MB_SFC_ACTIONS_H
#include "steps.h"
#define MB_SFC_SIGNAL_COUNT 16
#define MB_SFC_BINDING_COUNT 64
typedef enum {MB_SFC_N,MB_SFC_P1,MB_SFC_P0,MB_SFC_S,MB_SFC_R} mb_sfc_qualifier;
typedef enum {MB_SFC_OK,MB_SFC_RANGE,MB_SFC_MISSING,MB_SFC_DUPLICATE,MB_SFC_SEALED,MB_SFC_UNSEALED,MB_SFC_REWIND,MB_SFC_FLOW} mb_sfc_error;
typedef struct {uint8_t step,signal,qualifier;} mb_sfc_binding;
typedef struct {
 uint16_t steps,signals,normal,entry_pulse,exit_pulse,stored,reset,requested;
 unsigned count;bool sealed;mb_sfc_binding bindings[MB_SFC_BINDING_COUNT];
} mb_sfc_actions;
void mb_sfc_actions_init(mb_sfc_actions *a,uint16_t steps,uint16_t signals);
mb_sfc_error mb_sfc_actions_add(mb_sfc_actions *a,unsigned step,unsigned signal,mb_sfc_qualifier q);
mb_sfc_error mb_sfc_actions_seal(mb_sfc_actions *a);
void mb_sfc_actions_clear(mb_sfc_actions *a);
mb_sfc_error mb_sfc_actions_apply(mb_sfc_actions *a,uint16_t active,uint16_t entered,uint16_t exited);
/* Administrative cancel/restart. Leaves configured initial mask untouched. */
mb_sfc_error mb_sfc_restart(mb_steps *flow,mb_sfc_actions *a,unsigned step,uint64_t now);
#endif
