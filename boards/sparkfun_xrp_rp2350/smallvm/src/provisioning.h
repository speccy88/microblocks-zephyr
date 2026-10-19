/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
void xrp_provision_start(void);
void xrp_provision_message(char *,unsigned);
int xrp_network_status(char *,size_t);
const char *mb_network_ip(void);
#ifdef __cplusplus
}
#endif
