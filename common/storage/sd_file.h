/* SPDX-License-Identifier: MIT */
#ifndef MB_SD_FILE_H
#define MB_SD_FILE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define MB_SD_FILE_BYTES 8192
#define MB_SD_NAME_BYTES 13
typedef enum { MB_SD_FILE_READ=1, MB_SD_FILE_CREATE, MB_SD_FILE_REMOVE_OWN, MB_SD_FILE_LIST } mb_sd_file_op;
typedef struct {
    int error, close_error, unmount_error, native_result;
    size_t bytes;
    bool created, synced, verified, removed, truncated;
} mb_sd_file_result;
/* Simple upper-case 8.3 names only. No root/path/volume supplied by a caller.
 * Backend confines them to its MBFILES directory. */
bool mb_sd_file_name(const char *name,size_t length);
/* A backend must copy VM inputs before returning and serialize with SD probes.
 * No write/format fallback. CREATE must use exclusive creation, never truncate.
 * REMOVE_OWN must verify exact bytes against its successful creation snapshot.
 * Cancellation is cooperative; a created partial file is retained on failure.
 * A future generic SD file manager is separate from this first bounded API. */
bool mb_sd_file_available(void);
bool mb_sd_file_start(mb_sd_file_op op,const char *name,size_t name_length,
                      const uint8_t *data,size_t length);
bool mb_sd_file_result_get(mb_sd_file_result *out);
bool mb_sd_file_copy(size_t offset,uint8_t *out,size_t length);
/* VM owner only; stable CPU buffer across GC, until another SD operation. */
const uint8_t *mb_sd_file_view(size_t *length);
const char *mb_sd_file_last_name(void);
uint32_t mb_sd_file_generation(void);
#endif
