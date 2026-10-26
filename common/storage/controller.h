/* SPDX-License-Identifier: MIT */
#ifndef MB_FILES_CONTROLLER_H
#define MB_FILES_CONTROLLER_H
#include "wire.h"
#define MB_FILES_OPEN 9
#define MB_FILES_CLOSE 10
typedef struct { mb_files_dispatcher dispatcher; uint32_t nonce; } mb_files_controller;
void mb_files_controller_init(mb_files_controller *,mb_store *);
void mb_files_controller_reset(mb_files_controller *);
void mb_files_controller_poll(mb_files_controller *,uint64_t now);
bool mb_files_controller_message(mb_files_controller *,uint32_t owner,uint64_t now,
 const uint8_t *in,size_t length,uint8_t *out,size_t capacity,size_t *written,mb_files_wire_workspace *);
#endif
