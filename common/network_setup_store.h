/* SPDX-License-Identifier: MIT */
#pragma once
#include "network_setup.h"

#define MBNW_RECORD_SIZE 116u
#define MBNW_RECORD_DATA_SIZE 112u
struct mbnw_credentials {
    uint8_t ssid[32], key[64];
    size_t ssid_length, key_length;
    uint32_t generation;
};
/* Board integration owns partition mapping and erase alignment. Return zero on
 * complete I/O success; any partial/failed operation must return nonzero.
 * These functions never log credentials. The format is plaintext, not encrypted. */
struct mbnw_store {
    void *context;
    int (*read)(void *, unsigned slot, size_t offset, void *, size_t);
    int (*erase)(void *, unsigned slot);
    int (*write)(void *, unsigned slot, size_t offset, const void *, size_t);
};
int mbnw_store_load(const struct mbnw_store *, struct mbnw_credentials *, unsigned *slot);
int mbnw_store_save(const struct mbnw_store *, const uint8_t *ssid, size_t ssid_length,
                    const uint8_t *key, size_t key_length);
