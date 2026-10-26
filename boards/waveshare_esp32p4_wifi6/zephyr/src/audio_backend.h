/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
void p4_audio_init(void);
int p4_audio_codec_id(void);
int p4_audio_available(void);
int p4_audio_request(unsigned milliseconds);
int p4_audio_busy(void);
int p4_audio_result(void);
void p4_audio_discard(void);
const char *p4_audio_status(void);
/* Called on the audio worker with a temporary mono block. Copy immediately;
 * never retain its pointer or block this callback on inference/VM work. */
typedef int (*p4_audio_sink)(const int16_t *,unsigned,void *);
int p4_audio_stream_start(unsigned milliseconds,p4_audio_sink sink,void *context);
void p4_audio_stream_stop(void);
int p4_audio_stream_state(void); /* 1 running, 0 stopped, -1 error/quarantined */
