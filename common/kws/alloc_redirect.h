/* SPDX-License-Identifier: MIT */
/* Force-include ONLY for the pinned external microfrontend translation units.
 * Load C/C++ standard wrappers first, then redirect their allocation/error
 * calls without changing the rest of the application or vendor source. */
#pragma once
#ifdef __cplusplus
#include <cstdlib>
#include <cstdio>
#include <stdlib.h>
#include <stdio.h>
extern "C" {
#else
#include <stdlib.h>
#include <stdio.h>
#endif
void *kw_frontend_alloc(size_t);
void *kw_frontend_calloc(size_t,size_t);
void kw_frontend_free(void *);
int kw_frontend_fprintf(FILE *,const char *,...);
#ifdef __cplusplus
}
#endif
#define malloc kw_frontend_alloc
#define calloc kw_frontend_calloc
#define free kw_frontend_free
#define fprintf kw_frontend_fprintf
