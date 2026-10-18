/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#define FJ_WIFI_MESSAGE 205
#define FJ_WIFI_MAX_REQUEST 108
struct fj_wifi_request {
    uint32_t request_id;
    unsigned operation;
    const uint8_t *ssid, *key;
    size_t ssid_length, key_length;
};
int fj_wifi_decode(const uint8_t *body, size_t size, struct fj_wifi_request *request);
int fj_wifi_credentials_valid(const uint8_t *ssid, size_t ssid_length,
                              const uint8_t *key, size_t key_length);
void fj_secure_clear(void *buffer, size_t size);
