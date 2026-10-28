/* SPDX-License-Identifier: MIT */
#ifndef MB_SD_FILES_WIRE_H
#define MB_SD_FILES_WIRE_H
#include "wire.h"
/* Appended operations, retaining RAM operations 1..10 and framing unchanged. */
enum { MB_SD_CAPS=11,MB_SD_BEGIN,MB_SD_APPEND,MB_SD_CREATE,MB_SD_READ,
       MB_SD_STATUS,MB_SD_CHUNK,MB_SD_REMOVE,MB_SD_CANCEL,MB_SD_LIST };
bool mb_sd_files_wire(mb_files_dispatcher *dispatcher,uint32_t owner,uint64_t now,
 const uint8_t *request,size_t bytes,uint8_t *out,size_t capacity,size_t *written);
void mb_sd_files_wire_reset(void);
#endif
