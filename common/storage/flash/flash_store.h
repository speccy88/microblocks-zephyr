/* SPDX-License-Identifier: MIT */
#ifndef MB_FLASH_STORE_H
#define MB_FLASH_STORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define MB_FLASH_FILES 8
#define MB_FLASH_BYTES 8192
#define MB_FLASH_PATH 64
#define MB_FLASH_RECORD (80 + MB_FLASH_BYTES + 4)
#define MB_FLASH_REV_MAX UINT32_C(0x3fffffff)

/* Fixed keys only: 0 sequence, 1..8 slots. The port owns its temp path.
 * replace must sync/close/atomically rename, never autoformat. Errors after a
 * mutation may be uncertain. All calls run on one externally serialized owner. */
typedef struct {
    int (*mount)(void *);
    int (*unmount)(void *);
    int (*read)(void *, unsigned, uint8_t *, size_t, size_t *);
    int (*replace)(void *, unsigned, const uint8_t *, size_t);
    int (*remove)(void *, unsigned);
    int (*space)(void *, uint64_t *, uint64_t *);
} mb_flash_port;
typedef struct {
    char path[MB_FLASH_PATH];
    uint32_t revision, bytes;
} mb_flash_file;
typedef struct {
    const mb_flash_port *port;
    void *context;
    mb_flash_file files[MB_FLASH_FILES];
    uint8_t scratch[MB_FLASH_RECORD];
    uint32_t sequence;
    bool mounted, ready, busy;
} mb_flash;

void mb_flash_init(mb_flash *, const mb_flash_port *, void *);
int mb_flash_mount(mb_flash *);
int mb_flash_unmount(mb_flash *);
int mb_flash_stat(mb_flash *, const char *, size_t, mb_flash_file *);
int mb_flash_list(mb_flash *, mb_flash_file *out, size_t capacity, size_t *count);
int mb_flash_read(mb_flash *, const char *, size_t, uint32_t revision,
                  size_t offset, uint8_t *out, size_t bytes);
int mb_flash_put(mb_flash *, const char *, size_t, uint32_t expected_revision,
                 const uint8_t *data, size_t bytes, uint32_t *new_revision);
int mb_flash_delete(mb_flash *, const char *, size_t, uint32_t expected_revision);
int mb_flash_capacity(mb_flash *, uint32_t *used, unsigned *slots,
                      uint64_t *physical_total, uint64_t *physical_free);
bool mb_flash_path(const char *, size_t);
#endif
