/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stddef.h>
int p4_whistle_request(int handle,int language);
int p4_whistle_fixture(int language);
int p4_whistle_busy(void);
int p4_whistle_available(void);
void p4_whistle_cancel(void);
void p4_whistle_status(char *out,size_t bytes);
void p4_whistle_result(char *out,size_t bytes);
