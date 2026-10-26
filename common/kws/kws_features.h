/* SPDX-License-Identifier: MIT */
/* Deliberately distinct from the C library's <features.h>. */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include "tensorflow/lite/experimental/microfrontend/lib/frontend.h"

#define KW_FEATURES 40
#define KW_ALLOC_SLOTS 32
#define KW_FRONTEND_BUDGET 65536u
struct kw_allocator { void *(*alloc)(size_t); void (*release)(void *); };
/* One owner at a time; the backend serializes complete frontend sessions. */
struct kw_frontend {
 struct FrontendState state;
 struct kw_allocator allocator;
 void *allocations[KW_ALLOC_SLOTS];
 size_t sizes[KW_ALLOC_SLOTS],requested,peak_requested;
 unsigned allocations_made,diagnostics,features;
 int live,error;
};
#ifdef __cplusplus
extern "C" {
#endif
int kw_features_begin(struct kw_frontend *,struct kw_allocator);
int kw_features_push(struct kw_frontend *,const int16_t *,size_t,size_t *,int8_t out[KW_FEATURES]);
void kw_features_reset(struct kw_frontend *);
void kw_features_end(struct kw_frontend *);
#ifdef __cplusplus
}
#endif
