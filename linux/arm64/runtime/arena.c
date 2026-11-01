/* SPDX-License-Identifier: MPL-2.0
 * LP64 arena adapter for MicroBlocks SmallVM v417. */
#include "arena.h"
#include <errno.h>
#include <stdlib.h>

#define ARENA_BYTES (SMALLVM_ARENA_RESERVED_BYTES + SMALLVM_HEAP_BYTES + SMALLVM_CODE_BYTES)
static unsigned char *arena;

int smallvmArenaInit(void) {
    if (arena) return 0;
    arena = calloc(1, ARENA_BYTES);
    return arena ? 0 : -1;
}

void smallvmArenaDestroy(void) { free(arena); arena = NULL; }

uint32_t *smallvmHeapStart(void) {
    return arena ? (uint32_t *)(void *)(arena + SMALLVM_ARENA_RESERVED_BYTES) : NULL;
}
size_t smallvmHeapBytes(void) { return SMALLVM_HEAP_BYTES; }
uint32_t *smallvmCodeStart(void) {
    return arena ? (uint32_t *)(void *)(arena + SMALLVM_ARENA_RESERVED_BYTES + SMALLVM_HEAP_BYTES) : NULL;
}
size_t smallvmCodeBytes(void) { return SMALLVM_CODE_BYTES; }

uint32_t *smallvmO2A(uint32_t reference) {
    if (!arena || reference < SMALLVM_ARENA_RESERVED_BYTES || (reference & 3u) || reference > ARENA_BYTES - sizeof(uint32_t)) {
        errno = EINVAL;
        return NULL;
    }
    return (uint32_t *)(void *)(arena + reference);
}

uint32_t smallvmA2O(const void *address) {
    /* Integer subtraction avoids undefined pointer comparison/subtraction when
     * validating an unrelated address supplied by a caller. */
    uintptr_t candidate = (uintptr_t)address;
    uintptr_t base = (uintptr_t)arena;
    if (!arena || candidate < base + SMALLVM_ARENA_RESERVED_BYTES ||
        candidate > base + ARENA_BYTES - sizeof(uint32_t) || ((candidate - base) & 3u)) {
        errno = EINVAL;
        return 0;
    }
    return (uint32_t)(candidate - base);
}
