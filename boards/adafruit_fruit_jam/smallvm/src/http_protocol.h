/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
struct fj_http_request {char path[256],host[64],origin[96],key[25];bool websocket;};
/* Parses one complete bounded GET header. No filesystem paths are opened. */
int fj_http_parse(char *data,size_t size,const char *ip,struct fj_http_request *out);
int fj_ws_accept(const char key[25],char out[29]);
/* 0=incomplete, negative=malformed, positive=consumed; payload unmasked in place. */
int fj_ws_decode(uint8_t *data,size_t size,uint8_t *opcode,bool *final,uint8_t **payload,size_t *length);
size_t fj_ws_header(uint8_t *dst,unsigned opcode,size_t size);
