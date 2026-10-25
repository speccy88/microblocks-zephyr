/* SPDX-License-Identifier: MIT */
#pragma once
void p4_audio_init(void);
int p4_audio_codec_id(void);
int p4_audio_available(void);
int p4_audio_request(unsigned milliseconds);
int p4_audio_busy(void);
int p4_audio_result(void);
void p4_audio_discard(void);
const char *p4_audio_status(void);
