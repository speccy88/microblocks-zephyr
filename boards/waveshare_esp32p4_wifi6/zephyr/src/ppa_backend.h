/* SPDX-License-Identifier: MIT */
#pragma once
int p4_ppa_request(int handle,int width,int height,int angle,int mirror);
int p4_ppa_busy(void);
int p4_ppa_result(void);
void p4_ppa_cancel(void);
const char *p4_ppa_status(void);
