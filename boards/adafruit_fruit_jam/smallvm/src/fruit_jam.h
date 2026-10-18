/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
int fj_transport_init(void);
void fj_transport_poll(void);
bool fj_transport_connected(void);
void fj_io_init(void);
int fj_button(unsigned button);
int mb_store_load(void);
void mb_store_poll(void);
unsigned mb_store_generation(void);
/* Debugger-visible state. Nothing is printed into USB's VM byte stream. */
extern volatile int fruit_jam_status;
#ifdef __cplusplus
}
#endif
