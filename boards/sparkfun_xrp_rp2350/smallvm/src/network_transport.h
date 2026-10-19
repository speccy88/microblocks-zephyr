/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
int xrp_ws_request(void);
bool xrp_ws_connected(void);
void xrp_ws_close(void);
int xrp_ws_input(const uint8_t *data,size_t size);
int xrp_ws_output(uint8_t *data,size_t size);
bool xrp_wifi_setup_local(void);
