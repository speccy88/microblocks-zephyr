/* SPDX-License-Identifier: MPL-2.0 */
#ifndef MB_STORAGE_PROTOCOL_H
#define MB_STORAGE_PROTOCOL_H
#include <stdint.h>
#include <stdbool.h>
void mb_storage_protocol_message(int type,int bytes,const char *body,uint64_t now);
void mb_storage_protocol_reset(void);
void mb_storage_protocol_poll(uint64_t now,bool connected);
#endif
