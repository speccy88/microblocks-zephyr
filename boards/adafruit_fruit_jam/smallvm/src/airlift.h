/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
/* Explicit asynchronous diagnostics only; no boot-time coprocessor access. */
int fj_airlift_request(bool reset_first);
int fj_airlift_status(char *dst, unsigned size);
