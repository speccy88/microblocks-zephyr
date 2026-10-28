/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
void p4_http_diag(unsigned stage, int result);
void p4_http_diag_json(char *out, size_t capacity);
