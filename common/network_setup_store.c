/* SPDX-License-Identifier: MIT */
#include "network_setup_store.h"
#include <string.h>

static uint32_t get32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void put32(uint8_t *p, uint32_t n)
{
    for (unsigned i = 0; i < 4; ++i) p[i] = n >> (8 * i);
}
static uint32_t crc32(const uint8_t *p, size_t size)
{
    uint32_t crc = UINT32_MAX;
    while (size--) {
        crc ^= *p++;
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (UINT32_C(0xedb88320) & (0u - (crc & 1u)));
    }
    return ~crc;
}
static bool valid(const uint8_t *record)
{
    bool header = !memcmp(record, "MBW2", 4) && record[4] == 1 && record[5] == 0 &&
        get32(record + 8) != 0 && !memcmp(record + 112, "DONE", 4) &&
        get32(record + 108) == crc32(record, 108) &&
        mbnw_credentials_valid(record + 12, record[6], record + 44, record[7]);
    if (!header) return false;
    for (unsigned i = record[6]; i < 32; ++i) if (record[12 + i]) return false;
    for (unsigned i = record[7]; i < 64; ++i) if (record[44 + i]) return false;
    return true;
}
static bool newer(uint32_t a, uint32_t b)
{
    return a != b && (uint32_t)(a - b) < UINT32_C(0x80000000);
}

int mbnw_store_load(const struct mbnw_store *store, struct mbnw_credentials *out, unsigned *slot)
{
    if (!out) return MBNW_FORMAT;
    mbnw_clear(out, sizeof(*out));
    if (slot) *slot = 0;
    if (!store || !store->read) return MBNW_FORMAT;
    uint8_t records[2][MBNW_RECORD_SIZE] = {{0}};
    int result = MBNW_IO;
    if (store->read(store->context, 0, 0, records[0], MBNW_RECORD_SIZE) ||
        store->read(store->context, 1, 0, records[1], MBNW_RECORD_SIZE)) goto done;
    bool a = valid(records[0]), b = valid(records[1]);
    result = MBNW_EMPTY;
    if (!a && !b) goto done;
    unsigned chosen = !a || (b && newer(get32(records[1] + 8), get32(records[0] + 8))) ? 1 : 0;
    const uint8_t *record = records[chosen];
    out->ssid_length = record[6]; out->key_length = record[7];
    out->generation = get32(record + 8);
    memcpy(out->ssid, record + 12, out->ssid_length);
    memcpy(out->key, record + 44, out->key_length);
    if (slot) *slot = chosen;
    result = MBNW_OK;
done:
    mbnw_clear(records, sizeof(records));
    return result;
}

int mbnw_store_save(const struct mbnw_store *store, const uint8_t *ssid, size_t sn,
                    const uint8_t *key, size_t kn)
{
    if (!store || !store->read || !store->write || !store->erase) return MBNW_FORMAT;
    if (!mbnw_credentials_valid(ssid, sn, key, kn)) return MBNW_CREDENTIALS;
    struct mbnw_credentials previous = {0};
    unsigned active = 0;
    int status = mbnw_store_load(store, &previous, &active);
    if (status != MBNW_OK && status != MBNW_EMPTY) return status;
    uint32_t generation = previous.generation + 1;
    if (!generation) generation = 1;
    unsigned target = status == MBNW_EMPTY ? 0 : 1 - active;
    mbnw_clear(&previous, sizeof(previous));
    uint8_t record[MBNW_RECORD_SIZE] = {0}, verify[MBNW_RECORD_SIZE] = {0};
    memcpy(record, "MBW2", 4); record[4] = 1;
    record[6] = sn; record[7] = kn; put32(record + 8, generation);
    memcpy(record + 12, ssid, sn); memcpy(record + 44, key, kn);
    put32(record + 108, crc32(record, 108)); memcpy(record + 112, "DONE", 4);
    int result = MBNW_IO;
    if (store->erase(store->context, target) ||
        store->write(store->context, target, 0, record, MBNW_RECORD_DATA_SIZE) ||
        store->write(store->context, target, MBNW_RECORD_DATA_SIZE,
                     record + MBNW_RECORD_DATA_SIZE, 4) ||
        store->read(store->context, target, 0, verify, sizeof(verify))) goto done;
    if (memcmp(record, verify, sizeof(record)) || !valid(verify)) goto done;
    result = MBNW_OK;
done:
    mbnw_clear(record, sizeof(record)); mbnw_clear(verify, sizeof(verify));
    return result;
}
