/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* Explicit asynchronous diagnostics only; no boot-time coprocessor access. */
int fj_airlift_request(bool reset_first);
int fj_airlift_status(char *dst, unsigned size);
int fj_airlift_join(const uint8_t *ssid, size_t ssid_length,
                    const uint8_t *key, size_t key_length);
