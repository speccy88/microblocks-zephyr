/* SPDX-License-Identifier: MIT */
#ifndef MB_SERIAL_RATE_H
#define MB_SERIAL_RATE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
enum {SERIAL_BASE=0,SERIAL_SWITCHING=1,SERIAL_CONFIRM=2,SERIAL_FAST=3};
typedef struct {uint32_t baud,target,token;unsigned state;uint64_t switch_at,expires;} serial_rate;
typedef struct {unsigned operation;uint32_t token,baud;} serial_rate_request;
typedef int (*serial_rate_apply)(uint32_t baud,void *context);
void serial_rate_init(serial_rate *s);
bool serial_rate_decode(const uint8_t *data,size_t bytes,serial_rate_request *request);
unsigned serial_rate_command(serial_rate *s,const serial_rate_request *r,uint64_t now);
void serial_rate_poll(serial_rate *s,uint64_t now,bool tx_complete,serial_rate_apply apply,void *context);
void serial_rate_reply(const serial_rate *s,const serial_rate_request *r,unsigned status,uint8_t out[16]);
#endif
