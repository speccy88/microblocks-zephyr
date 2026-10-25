/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#define AUDIO_SLOTS 2u
#define AUDIO_RATE 16000u
#define AUDIO_MAX_FRAMES (8u*AUDIO_RATE)
#define AUDIO_BUDGET (AUDIO_SLOTS*AUDIO_MAX_FRAMES*sizeof(int16_t))
#define AUDIO_HANDLE_TAG 0x20000000u
typedef struct { unsigned frames,rate,channels; int16_t *samples; } audio_view;
/* Store access/adoption is VM-thread-only. Workers own independent native PCM. */
int audio_adopt(int16_t *samples,unsigned frames);
int audio_create(unsigned frames);
const audio_view *audio_get(int handle);
int audio_release(int handle);
void audio_release_all(void);
unsigned audio_count(void);
size_t audio_bytes_used(void);
int audio_read(int handle,size_t byte_offset,uint8_t *out,size_t bytes);
int audio_copy_float(int handle,float *out,unsigned frames);
int audio_stats(int handle,unsigned *peak,unsigned *rms);
void *audio_alloc(size_t bytes);
void audio_free(void *ptr);
