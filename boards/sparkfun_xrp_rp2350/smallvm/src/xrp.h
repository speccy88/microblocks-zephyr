/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
int xrp_transport_init(void);
void xrp_transport_poll(void);
bool xrp_transport_connected(void);
void xrp_io_init(void);
int xrp_button(unsigned);
void xrp_motors_coast(void);
void xrp_capture_stop(void);
int mb_store_load(void);
void mb_store_poll(void);
unsigned mb_store_generation(void);
extern volatile int xrp_status;
#ifdef __cplusplus
}
#endif
