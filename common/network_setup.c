/* SPDX-License-Identifier: MIT */
#include "network_setup.h"
#include <string.h>

void mbnw_clear(void *buffer, size_t size)
{
    volatile uint8_t *bytes = buffer;
    while (size--) *bytes++ = 0;
}

bool mbnw_credentials_valid(const uint8_t *ssid, size_t sn,
                            const uint8_t *key, size_t kn)
{
    if (!ssid || !key || sn < 1 || sn > 32 || kn < 8 || kn > 64) return false;
    for (size_t i = 0; i < sn; ++i) if (!ssid[i]) return false;
    for (size_t i = 0; i < kn; ++i) {
        uint8_t c = key[i];
        if (!c) return false;
        if (kn == 64 && !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                          (c >= 'A' && c <= 'F'))) return false;
    }
    return true;
}

int mbnw_decode(const uint8_t *body, size_t size, struct mbnw_request *out)
{
    if (!out) return MBNW_FORMAT;
    memset(out, 0, sizeof(*out));
    if (!body || size < 10 || size > MBNW_MAX_REQUEST ||
        memcmp(body, "MBNW", 4) || body[4] != 2) return MBNW_FORMAT;
    struct mbnw_request request = {0};
    request.operation = body[5];
    request.id = (uint32_t)body[6] | ((uint32_t)body[7] << 8) |
                 ((uint32_t)body[8] << 16) | ((uint32_t)body[9] << 24);
    if (!request.id) return MBNW_FORMAT;
    if (request.operation == MBNW_PROBE || request.operation == MBNW_STATUS) {
        if (size != 10) return MBNW_FORMAT;
    } else if (request.operation == MBNW_CONNECT) {
        if (size < 13 || (body[10] & ~MBNW_REMEMBER)) return MBNW_FORMAT;
        request.flags = body[10];
        request.ssid_length = body[11]; request.key_length = body[12];
        if (size != 13 + request.ssid_length + request.key_length) return MBNW_FORMAT;
        request.ssid = body + 13; request.key = request.ssid + request.ssid_length;
        if (!mbnw_credentials_valid(request.ssid, request.ssid_length,
                                     request.key, request.key_length)) return MBNW_CREDENTIALS;
    } else return MBNW_UNSUPPORTED;
    *out = request;
    return MBNW_OK;
}

int mbnw_authorize(const struct mbnw_request *request, bool local, bool persistent)
{
    if (!local) return MBNW_NOT_LOCAL;
    if (!request || !request->id || request->flags & ~MBNW_REMEMBER) return MBNW_FORMAT;
    if (request->operation == MBNW_PROBE || request->operation == MBNW_STATUS)
        return request->flags == 0 ? MBNW_OK : MBNW_FORMAT;
    if (request->operation != MBNW_CONNECT) return MBNW_UNSUPPORTED;
    if (!mbnw_credentials_valid(request->ssid, request->ssid_length,
                                request->key, request->key_length)) return MBNW_CREDENTIALS;
    return request->flags & MBNW_REMEMBER && !persistent ? MBNW_UNSUPPORTED : MBNW_OK;
}
