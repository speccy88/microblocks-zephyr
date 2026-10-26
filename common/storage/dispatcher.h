/* SPDX-License-Identifier: MIT */
#ifndef MB_FILES_DISPATCHER_H
#define MB_FILES_DISPATCHER_H
#include "storage.h"
#define MB_FILES_CHUNK 512
#define MB_FILES_IDLE_MS UINT64_C(30000)
typedef enum { MB_FILES_CAPS=1, MB_FILES_LIST, MB_FILES_STAT, MB_FILES_READ,
    MB_FILES_BEGIN, MB_FILES_APPEND, MB_FILES_FINISH, MB_FILES_CANCEL } mb_files_op;
typedef enum { MB_FILES_OK, MB_FILES_PROTOCOL, MB_FILES_DISCONNECTED, MB_FILES_PATH,
    MB_FILES_UNAVAILABLE, MB_FILES_SIZE, MB_FILES_BUSY, MB_FILES_CONFLICT,
    MB_FILES_EXISTS, MB_FILES_NOT_FOUND, MB_FILES_FULL, MB_FILES_CANCELLED,
    MB_FILES_TIMEOUT, MB_FILES_STATE } mb_files_status;
typedef struct {
    char path[MB_FILE_PATH];
    uint32_t revision;
    uint16_t bytes;
} mb_files_meta;
typedef struct {
    uint32_t id, session, token, arg;
    uint16_t count;
    uint8_t op, path_length;
    char path[MB_FILE_PATH];
    uint8_t data[MB_FILES_CHUNK];
} mb_files_request;
typedef struct {
    uint32_t id, session, token, used;
    uint16_t count;
    uint8_t op, file_count, free_slots;
    mb_files_status status;
    mb_files_meta files[MB_FILE_COUNT];
    uint8_t data[MB_FILES_CHUNK];
} mb_files_reply;
typedef struct {
    mb_store *store;
    uint32_t owner, session, generation, last_id, job;
    uint64_t last_ms;
} mb_files_dispatcher;

/* One execution owner serializes these calls with all other store operations.
   owner is assigned by trusted connection arbitration, never request bytes. */
void mb_files_init(mb_files_dispatcher *dispatcher, mb_store *store);
mb_files_status mb_files_open(mb_files_dispatcher *dispatcher, uint32_t owner,
    uint64_t now_ms, uint32_t *session);
bool mb_files_close(mb_files_dispatcher *dispatcher, uint32_t owner, uint32_t session);
bool mb_files_expire(mb_files_dispatcher *dispatcher, uint64_t now_ms);
void mb_files_dispatch(mb_files_dispatcher *dispatcher, uint32_t owner,
    uint64_t now_ms, const mb_files_request *request, mb_files_reply *reply);
#endif
