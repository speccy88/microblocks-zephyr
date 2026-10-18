/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
struct fj_nina_reader {
    int (*byte)(void *context, uint8_t *value);
    void (*retry_pause)(void *context);
    void *context;
};
/* Bounded identification/IP queries and explicit two-parameter WPA submission. */
int fj_nina_query_frame(uint8_t command, uint8_t *dst, size_t size);
int fj_nina_connect_frame(const uint8_t *ssid, size_t ssid_length,
                          const uint8_t *key, size_t key_length,
                          uint8_t *dst, size_t size);
int fj_nina_read_reply_params(const struct fj_nina_reader *io, uint8_t command,
                             uint8_t **destinations, const size_t *capacities,
                             size_t *lengths, unsigned parameters);
int fj_nina_read_reply(const struct fj_nina_reader *io, uint8_t command,
                      uint8_t *dst, size_t capacity, size_t *length);
