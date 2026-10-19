/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/device.h>
static inline unsigned irq_lock(void) { return 0; }
static inline void irq_unlock(unsigned key) { (void)key; }
