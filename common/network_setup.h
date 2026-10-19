/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MBNW_MAX_REQUEST 109u
#define MBNW_REMEMBER 1u
enum mbnw_operation { MBNW_PROBE = 1, MBNW_CONNECT = 2, MBNW_STATUS = 3 };
enum mbnw_error {
    MBNW_OK = 0, MBNW_FORMAT = -1, MBNW_CREDENTIALS = -2,
    MBNW_NOT_LOCAL = -3, MBNW_UNSUPPORTED = -4, MBNW_IO = -5,
    MBNW_EMPTY = -6
};
struct mbnw_request {
    uint32_t id;
    uint8_t operation, flags;
    const uint8_t *ssid, *key;
    size_t ssid_length, key_length;
};
void mbnw_clear(void *buffer, size_t size);
bool mbnw_credentials_valid(const uint8_t *ssid, size_t ssid_length,
                            const uint8_t *key, size_t key_length);
/* Output views borrow the caller's input. Output is zeroed on any error. */
int mbnw_decode(const uint8_t *body, size_t size, struct mbnw_request *request);
int mbnw_authorize(const struct mbnw_request *request, bool local_usb_owner,
                   bool persistence_supported);
