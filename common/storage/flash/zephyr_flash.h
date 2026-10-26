/* SPDX-License-Identifier: MIT */
#ifndef MB_ZEPHYR_FLASH_H
#define MB_ZEPHYR_FLASH_H
#include "flash_store.h"
#include <zephyr/sys/util.h>
#include <zephyr/fs/fs.h>
typedef struct {
    struct fs_mount_t *mount;
#ifdef CONFIG_ZTEST
    /* Faults are test-only, one-shot, and scoped to a fixed record key. */
    unsigned fault, fault_key;
#endif
} mb_flash_zephyr;
extern const mb_flash_port mb_flash_zephyr_port;
#ifdef CONFIG_ZTEST
enum { MB_FS_SHORT=1, MB_FS_WRITE, MB_FS_SYNC, MB_FS_CLOSE,
       MB_FS_RENAME_BEFORE, MB_FS_RENAME_AFTER, MB_FS_READ, MB_FS_REMOVE };
#endif
#endif
