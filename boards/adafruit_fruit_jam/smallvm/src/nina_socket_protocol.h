/* SPDX-License-Identifier: MIT */
#pragma once
#include "nina_protocol.h"
#include <stdbool.h>
struct fj_nina_parameter { const uint8_t *data; size_t size; };
/* Only bounded TCP operations used by the local server are allowed. */
int fj_nina_socket_frame(uint8_t command, const struct fj_nina_parameter *params,
                         unsigned count, uint8_t *dst, size_t capacity);
int fj_nina_socket_reply(const struct fj_nina_reader *io, uint8_t command,
                         uint8_t *dst, size_t capacity, size_t *length);
