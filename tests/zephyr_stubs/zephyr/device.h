/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
struct device { bool ready; };
static inline bool device_is_ready(const struct device *d) { return d && d->ready; }
extern struct device test_cdc;
#define DEVICE_DT_GET(node) (&test_cdc)
#define DT_NODELABEL(name) name
