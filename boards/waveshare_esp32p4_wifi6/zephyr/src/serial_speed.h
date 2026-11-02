/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
void p4_serial_speed_message(int type,int bytes,const char *body);
void p4_serial_speed_poll(void);
uint32_t p4_serial_speed_baud(void);
