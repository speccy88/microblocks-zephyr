/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdbool.h>
#include "discovery.h"
void p4_discovery_init(void);
bool p4_discovery_busy(void);
bool p4_discovery_scan(int bus,bool identify);
void p4_discovery_cancel(void);
unsigned p4_discovery_count(void);
void p4_discovery_ref(int index,char *,size_t);
bool p4_discovery_device(const char *,discovery_device *);
bool p4_discovery_read(const char *,const char *);
discovery_reading p4_discovery_reading(void);
void p4_discovery_status(char *,size_t);
void p4_discovery_read_text(char *,size_t);
