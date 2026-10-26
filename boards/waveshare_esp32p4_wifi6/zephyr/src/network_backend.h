/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stddef.h>
void p4_network_init(void);
void p4_network_message(int,int,char *);
void p4_network_status(char *,size_t);
void p4_network_address(char *,size_t);
