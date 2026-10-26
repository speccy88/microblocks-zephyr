/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void p4_kws_init(void);
int p4_kws_available(void);
int p4_kws_fixture(unsigned id);
int p4_kws_clip(int handle);
int p4_kws_listen(unsigned milliseconds,unsigned confidence_milli,unsigned cooldown_ms);
int p4_kws_listening(void);
int p4_kws_busy(void);
void p4_kws_cancel(void);
void p4_kws_status(char *out,size_t size);
int p4_kws_scores(unsigned offset,unsigned count,uint8_t *out);
int p4_kws_take_event(void);
unsigned p4_kws_confidence(void);
const char *p4_kws_state(void);
#ifdef __cplusplus
}
#endif
