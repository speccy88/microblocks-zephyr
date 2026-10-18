/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
struct fj_nina_reader {
    int (*byte)(void *context, uint8_t *value);
    void (*retry_pause)(void *context);
    void *context;
};
/* Identification allowlist: version/status/MAC only. No credential commands. */
int fj_nina_query_frame(uint8_t command, uint8_t *dst, size_t size);
int fj_nina_read_reply(const struct fj_nina_reader *io, uint8_t command,
                      uint8_t *dst, size_t capacity, size_t *length);
