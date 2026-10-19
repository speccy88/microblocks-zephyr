/* SPDX-License-Identifier: MIT */
#pragma once
#include "network_setup_store.h"
#include <zephyr/storage/flash_map.h>
/* Owns only the first two independent erase pages of a dedicated partition.
 * The caller serializes journal operations; no VM or filesystem shares it. */
struct mbnw_flash_store {
    struct mbnw_store io;
    const struct flash_area *area;
    size_t offsets[2], sizes[2], write_block;
};
int mbnw_flash_store_open(struct mbnw_flash_store *, unsigned partition_id);
