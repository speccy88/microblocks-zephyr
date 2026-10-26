/* SPDX-License-Identifier: MIT */
#ifndef MB_FILES_WIRE_H
#define MB_FILES_WIRE_H
#include "dispatcher.h"
#define MB_FILES_MESSAGE 217
#define MB_FILES_REQUEST_HEADER 26
#define MB_FILES_REQUEST_MAX (MB_FILES_REQUEST_HEADER+MB_FILES_CHUNK)
#define MB_FILES_RESPONSE_MAX 640
/* Caller owns this fixed workspace; not a SmallVM/GC buffer. No heap allocation. */
typedef struct { mb_files_request request; mb_files_reply reply; } mb_files_wire_workspace;
bool mb_files_wire(mb_files_dispatcher *dispatcher, uint32_t owner, uint64_t now_ms,
    const uint8_t *request, size_t request_length, uint8_t *reply, size_t reply_capacity,
    size_t *reply_length, mb_files_wire_workspace *workspace);
#endif
