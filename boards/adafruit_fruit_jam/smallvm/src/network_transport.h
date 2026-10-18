/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
int fj_ws_request(void);
bool fj_ws_connected(void);
void fj_ws_close(void);
int fj_ws_input(const uint8_t *data,size_t size);
int fj_ws_output(uint8_t *data,size_t size);
bool fj_wifi_setup_local(void);
