/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#define IMAGE_SLOTS 4
#define IMAGE_BUDGET (8u * 1024u * 1024u)
#define IMAGE_MAX_WIDTH 1280u
#define IMAGE_MAX_HEIGHT 720u
enum image_format { IMAGE_RGB565=2, IMAGE_GRAY8=1, IMAGE_RGB888=3 };
typedef struct { unsigned width,height,stride,format; size_t bytes; uint8_t *pixels; } image_view;
/* All store functions run only on the VM thread. Buffers contain no VM objects. */
int image_create(unsigned width,unsigned height,unsigned format);
int image_adopt(unsigned width,unsigned height,unsigned format,uint8_t *pixels,size_t bytes);
const image_view *image_get(int handle);
int image_resize(int handle,unsigned width,unsigned height,unsigned format);
int image_grayscale(int handle);
int image_release(int handle);
void image_release_all(void);
size_t image_bytes_used(void);
unsigned image_count(void);
int image_read(int handle,size_t offset,uint8_t *dst,size_t count);
void *image_alloc(size_t bytes);
void image_free(void *ptr);
