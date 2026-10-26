/* SPDX-License-Identifier: MIT */
#ifndef MB_STORAGE_H
#define MB_STORAGE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MB_FILE_COUNT 8
#define MB_FILE_BYTES 8192
#define MB_FILE_PATH 64
#define MB_FILE_CHUNK 1024
#define MB_FILE_REFERENCE_MAX UINT32_C(0x3fffffff)

typedef enum {
    MB_STORE_OK, MB_STORE_PATH, MB_STORE_UNAVAILABLE, MB_STORE_NOT_FOUND,
    MB_STORE_EXISTS, MB_STORE_FULL, MB_STORE_SIZE, MB_STORE_BUSY,
    MB_STORE_STALE, MB_STORE_STATE, MB_STORE_ORDER, MB_STORE_TEXT,
    MB_STORE_CONFLICT, MB_STORE_EXHAUSTED
} mb_store_error;
typedef enum {
    MB_WRITE_IDLE, MB_WRITE_RECEIVING, MB_WRITE_READY,
    MB_WRITE_DONE, MB_WRITE_CANCELLED, MB_WRITE_FAILED
} mb_write_state;
typedef struct {
    uint8_t data[MB_FILE_BYTES];
    char path[MB_FILE_PATH];
    uint32_t revision;
    uint16_t length;
    bool present;
} mb_ram_file;
typedef struct {
    mb_ram_file files[MB_FILE_COUNT];
    uint8_t staging[MB_FILE_BYTES];
    char path[MB_FILE_PATH];
    uint32_t generation;
    uint32_t revision_counter, expected_revision;
    mb_store_error job_error;
    uint16_t expected, received;
    uint8_t slot;
    mb_write_state state;
} mb_store;

void mb_store_init(mb_store *store);
mb_store_error mb_store_path(const char *path, size_t length);
bool mb_store_utf8(const uint8_t *data, size_t length);
mb_store_error mb_store_padded_text(const char *data, size_t capacity, size_t max, size_t *length);
mb_store_error mb_store_begin(mb_store *store, const char *path, size_t path_length,
    size_t length, bool replace, uint32_t *job);
/* Revision zero creates only. A nonzero revision requires that exact file. */
mb_store_error mb_store_begin_revision(mb_store *store, const char *path, size_t path_length,
    size_t length, uint32_t expected_revision, uint32_t *job);
mb_store_error mb_store_append(mb_store *store, uint32_t job, size_t offset,
    const uint8_t *data, size_t length);
mb_store_error mb_store_finish(mb_store *store, uint32_t job);
mb_store_error mb_store_cancel(mb_store *store, uint32_t job);
mb_store_error mb_store_job(const mb_store *store, uint32_t job, mb_write_state *state);
bool mb_store_poll(mb_store *store);
void mb_store_stop(mb_store *store);
mb_store_error mb_store_view(const mb_store *store, const char *path, size_t length,
    const mb_ram_file **file);
mb_store_error mb_store_read(const mb_store *store, const char *path, size_t path_length,
    size_t offset, uint8_t *out, size_t length);
mb_store_error mb_store_read_revision(const mb_store *store, const char *path, size_t path_length,
    uint32_t revision, size_t offset, uint8_t *out, size_t length);
mb_store_error mb_store_delete(mb_store *store, const char *path, size_t length);
size_t mb_store_used(const mb_store *store);
unsigned mb_store_count(const mb_store *store);
const char *mb_store_error_text(mb_store_error error);
const char *mb_store_state_text(mb_write_state state);
#endif
