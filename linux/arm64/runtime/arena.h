/* SPDX-License-Identifier: MPL-2.0
 * LP64 arena adapter for MicroBlocks SmallVM v417. */
#ifndef SMALLVM_LINUX_ARENA_H
#define SMALLVM_LINUX_ARENA_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#define SMALLVM_ARENA_RESERVED_BYTES 16u
#define SMALLVM_HEAP_BYTES 262144u
#define SMALLVM_CODE_BYTES 524288u

/* Idempotent initialization. No address hints, fixed mappings or ASLR changes.
 * Zero on success, -1 with errno on allocation failure. */
int smallvmArenaInit(void);
void smallvmArenaDestroy(void);
uint32_t *smallvmHeapStart(void);
size_t smallvmHeapBytes(void);
uint32_t *smallvmCodeStart(void);
size_t smallvmCodeBytes(void);

/* Checked aligned references into the arena. Tags/booleans and out-of-arena
 * addresses are rejected with NULL/0 and errno=EINVAL. Native pointers never
 * pass through a 32-bit integer. The zero reference remains falseObj. */
uint32_t *smallvmO2A(uint32_t reference);
uint32_t smallvmA2O(const void *address);
#define O2A(reference) smallvmO2A((uint32_t)(reference))
#define A2O(address) smallvmA2O((const void *)(address))

#ifdef __cplusplus
}
#endif
#endif
