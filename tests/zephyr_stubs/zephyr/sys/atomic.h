/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
typedef int atomic_t;
static inline int atomic_get(const atomic_t *p) { return *p; }
static inline int atomic_set(atomic_t *p,int n) { int old=*p;*p=n;return old; }
static inline int atomic_clear(atomic_t *p) { return atomic_set(p,0); }
static inline bool atomic_cas(atomic_t *p,int old,int n) { if(*p!=old)return false;*p=n;return true; }
