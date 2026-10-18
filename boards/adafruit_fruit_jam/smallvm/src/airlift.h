/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "nina_socket_protocol.h"
/* Explicit asynchronous diagnostics only; no boot-time coprocessor access. */
int fj_airlift_request(bool reset_first);
int fj_airlift_status(char *dst, unsigned size);
int fj_airlift_join(const uint8_t *ssid, size_t ssid_length,
                    const uint8_t *key, size_t key_length);
bool fj_airlift_network_ready(char *ip, unsigned size);
int fj_airlift_socket_command(uint8_t command,const struct fj_nina_parameter *params,
                              unsigned count,uint8_t *dst,size_t capacity,size_t *length);
