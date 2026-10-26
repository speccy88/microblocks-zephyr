/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdbool.h>
#define P4_RPC_POOL_BYTES 65536u
#define P4_RPC_PROTO_BYTES 1576u
void *p4_rpc_realloc(void *ptr,size_t bytes);
void p4_rpc_free(void *ptr);
struct p4_rpc_memory_stats {size_t capacity,used,peak,failures;};
void p4_rpc_memory_stats(struct p4_rpc_memory_stats *out);
#ifdef P4_RPC_ALLOC_TEST
void p4_rpc_fail_allocation(size_t nth);
bool p4_rpc_heap_valid(void);
#endif
/* Forced include only on the pinned nanopb module, never global malloc. */
#define pb_realloc p4_rpc_realloc
#define pb_free p4_rpc_free
