/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/device.h>
struct flash_area { const struct device *fa_dev; size_t fa_off,fa_size; };
int flash_area_open(unsigned,const struct flash_area **);
void flash_area_close(const struct flash_area *);
int flash_area_read(const struct flash_area *,size_t,void *,size_t);
int flash_area_write(const struct flash_area *,size_t,const void *,size_t);
int flash_area_erase(const struct flash_area *,size_t,size_t);
