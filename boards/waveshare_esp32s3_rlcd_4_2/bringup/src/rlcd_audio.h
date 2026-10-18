/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
int rlcd_audio_play(int frequency, int duration_ms, int volume);
void rlcd_audio_stop(void);
bool rlcd_audio_busy(void);
int rlcd_audio_status(char *dst, unsigned size);
