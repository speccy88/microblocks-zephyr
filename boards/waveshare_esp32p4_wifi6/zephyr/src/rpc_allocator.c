/* SPDX-License-Identifier: MIT */
#include "rpc_allocator.h"
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_heap.h>
#include <string.h>
#if defined(CONFIG_ESP_SPIRAM)
#define RPC_RAM __attribute__((section(".ext_ram.bss.rpc_pool"),aligned(16)))
#else
#define RPC_RAM __attribute__((aligned(16)))
#endif
static uint8_t rpc_pool[P4_RPC_POOL_BYTES] RPC_RAM;
static struct {struct sys_heap heap;bool initialized;size_t used,peak,failures;} rpc_state RPC_RAM;
K_MUTEX_DEFINE(rpc_allocator_lock);
#ifdef P4_RPC_ALLOC_TEST
static size_t fail_nth,calls;
void p4_rpc_fail_allocation(size_t nth){k_mutex_lock(&rpc_allocator_lock,K_FOREVER);fail_nth=nth;calls=0;k_mutex_unlock(&rpc_allocator_lock);}
bool p4_rpc_heap_valid(void){k_mutex_lock(&rpc_allocator_lock,K_FOREVER);bool ok=!rpc_state.initialized || sys_heap_validate(&rpc_state.heap);k_mutex_unlock(&rpc_allocator_lock);return ok;}
#endif
void *p4_rpc_realloc(void *ptr,size_t bytes)
{
 if(k_is_in_isr() || k_is_pre_kernel())return NULL;
 if(!bytes){p4_rpc_free(ptr);return NULL;}
 k_mutex_lock(&rpc_allocator_lock,K_FOREVER);
 if(!rpc_state.initialized){sys_heap_init(&rpc_state.heap,rpc_pool,sizeof(rpc_pool));rpc_state.initialized=true;}
 size_t before=ptr?sys_heap_usable_size(&rpc_state.heap,ptr):0;
 bool fail=bytes>P4_RPC_POOL_BYTES;
#ifdef P4_RPC_ALLOC_TEST
 if(fail_nth && ++calls==fail_nth)fail=true;
#endif
 void *result=fail?NULL:sys_heap_realloc(&rpc_state.heap,ptr,bytes);
 if(result){rpc_state.used=rpc_state.used-before+sys_heap_usable_size(&rpc_state.heap,result);rpc_state.peak=MAX(rpc_state.peak,rpc_state.used);}
 else rpc_state.failures++;
 k_mutex_unlock(&rpc_allocator_lock);return result;
}
void p4_rpc_free(void *ptr)
{
 if(!ptr)return;
 __ASSERT(!k_is_in_isr() && !k_is_pre_kernel(),"RPC free requires thread context");
 k_mutex_lock(&rpc_allocator_lock,K_FOREVER);
 size_t bytes=sys_heap_usable_size(&rpc_state.heap,ptr);
 memset(ptr,0,bytes); /* Discard decoded data before pool reuse. */
 rpc_state.used-=bytes;sys_heap_free(&rpc_state.heap,ptr);
 k_mutex_unlock(&rpc_allocator_lock);
}
void p4_rpc_memory_stats(struct p4_rpc_memory_stats *out)
{
 k_mutex_lock(&rpc_allocator_lock,K_FOREVER);
 *out=(struct p4_rpc_memory_stats){sizeof(rpc_pool),rpc_state.used,rpc_state.peak,rpc_state.failures};
 k_mutex_unlock(&rpc_allocator_lock);
}
