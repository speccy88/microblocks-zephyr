/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <stddef.h>
#define MEDIA_SLOTS 4u
#define MEDIA_BUDGET (512u*1024u)
#define MEDIA_THUMB_W 160u
#define MEDIA_THUMB_H 90u
typedef struct {
 uint32_t token,uid;
 unsigned kind,width,height,source_width,source_height,format,rate,channels,frames;
 size_t bytes;uint8_t *data;
} media_result;
typedef struct { uint32_t session,uid,token; } media_event;
/* All access is serialized on the VM thread; workers retain no VM pointers. */
void media_session(uint32_t session);
uint32_t media_session_id(void);
uint32_t media_publish(uint32_t uid,int handle);
const media_result *media_get(uint32_t uid,uint32_t token);
int media_read(uint32_t uid,uint32_t token,size_t offset,uint8_t *out,size_t count);
int media_release(uint32_t uid,uint32_t token);
void media_clear(void);
int media_event_peek(media_event *event);
void media_event_pop(void);
size_t media_bytes_used(void);
unsigned media_count(void);
void *media_alloc(size_t bytes);
void media_free(void *ptr);
