/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
struct fj_web_asset {const char *path,*type;const uint8_t *data;size_t size;bool gzip;};
extern const struct fj_web_asset fj_web_assets[];
extern const unsigned fj_web_asset_count;
int fj_network_status(char *dst,unsigned size);
