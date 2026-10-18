/* SPDX-License-Identifier: MIT */
#include "wifi_control.h"
#include <errno.h>
#include <string.h>
void fj_secure_clear(void *buffer, size_t size)
{
    volatile uint8_t *p = buffer;
    while (size--) *p++ = 0;
}
int fj_wifi_credentials_valid(const uint8_t *ssid, size_t sn,
                              const uint8_t *key, size_t kn)
{
    if (!ssid || !key || sn < 1 || sn > 32 || kn < 8 || kn > 64) return -EINVAL;
    for (size_t i = 0; i < sn; ++i) if (!ssid[i]) return -EINVAL;
    for (size_t i = 0; i < kn; ++i) {
        uint8_t c = key[i];
        if (!c) return -EINVAL;
        if (kn == 64 && !((c >= '0' && c <= '9') ||
            (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) return -EINVAL;
    }
    return 0;
}
int fj_wifi_decode(const uint8_t *body, size_t size, struct fj_wifi_request *r)
{
    if (!r) return -EINVAL;
    memset(r, 0, sizeof(*r));
    if (!body || size < 10 || size > FJ_WIFI_MAX_REQUEST || memcmp(body,"FJNW",4) || body[4] != 1) return -EPROTO;
    r->operation=body[5];
    r->request_id=(uint32_t)body[6] | ((uint32_t)body[7]<<8) |
                  ((uint32_t)body[8]<<16) | ((uint32_t)body[9]<<24);
    if (!r->request_id) return -EINVAL;
    if (r->operation==1 || r->operation==3) return size==10 ? 0 : -EINVAL;
    if (r->operation!=2) return -ENOTSUP;
    if (size<12) return -EINVAL;
    r->ssid_length=body[10];r->key_length=body[11];
    if (size != 12+r->ssid_length+r->key_length) return -EINVAL;
    r->ssid=body+12;r->key=r->ssid+r->ssid_length;
    return fj_wifi_credentials_valid(r->ssid,r->ssid_length,r->key,r->key_length);
}
