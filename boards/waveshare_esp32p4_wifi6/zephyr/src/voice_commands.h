/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
int p4_voice_available(void);
int p4_voice_listen(unsigned ms,unsigned confidence,unsigned cooldown);
int p4_voice_clip(int handle);
int p4_voice_take_event(void);
const char *p4_voice_command(void);
unsigned p4_voice_confidence(void);
unsigned p4_voice_score(unsigned index);
void p4_voice_status(char *out,size_t bytes);
void p4_voice_clear(void);
#ifdef __cplusplus
}
#endif
