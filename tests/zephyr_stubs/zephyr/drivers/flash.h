/* SPDX-License-Identifier: MIT */
#pragma once
#include <zephyr/storage/flash_map.h>
struct flash_parameters { size_t write_block_size;uint8_t erase_value; };
struct flash_pages_info { size_t start_offset,size; };
const struct flash_parameters *flash_get_parameters(const struct device *);
int flash_get_page_info_by_offs(const struct device *,size_t,struct flash_pages_info *);
