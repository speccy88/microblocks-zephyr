/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
/* Included in generated wrappers after Zephyr's forced compatibility header.
 * This independent engine uses its portable C branch on RV32/Zephyr. */
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>
#undef ESP_PLATFORM
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
void *p4_whistle_alloc(size_t bytes);
void *p4_whistle_calloc(size_t n,size_t bytes);
void p4_whistle_free(void *ptr);
#define ND_ALLOC(n) p4_whistle_alloc(n)
#define ND_FREE(p) p4_whistle_free(p)
#define ND_ALLOC_FAST(n) p4_whistle_alloc(n)
#define ND_FREE_FAST(p) p4_whistle_free(p)
#define malloc(n) p4_whistle_alloc(n)
#define calloc(n,s) p4_whistle_calloc(n,s)
#define free(p) p4_whistle_free(p)
