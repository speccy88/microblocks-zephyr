/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#define DISCOVERY_LIMIT 32
enum discovery_kind { DISC_UNKNOWN, DISC_TMP117, DISC_IMX219, DISC_OV5647, DISC_ES8311 };
enum discovery_confidence { DISC_ADDRESS, DISC_CANDIDATE, DISC_CONFIRMED };
enum discovery_error { DISC_OK, DISC_IO, DISC_UNSUPPORTED, DISC_NOT_READY, DISC_SHUTDOWN, DISC_REPLACED, DISC_CANCELLED, DISC_TIMEOUT, DISC_FULL };
typedef struct { uint8_t address,kind,confidence; } discovery_device;
typedef struct {
 void *context;
 int (*probe)(void *,uint8_t);
 int (*read)(void *,uint8_t,uint16_t,unsigned,uint8_t *,unsigned);
 bool (*stop)(void *); /* deadline/cancel, checked between driver calls */
} discovery_bus;
typedef struct { discovery_device devices[DISCOVERY_LIMIT]; unsigned count,visited; int error; } discovery_results;
typedef struct { int32_t value; unsigned scale; const char *unit; int error; } discovery_reading;
void discovery_scan(const discovery_bus *,bool identify,discovery_results *);
const char *discovery_name(const discovery_device *);
const char *discovery_confidence_name(const discovery_device *);
unsigned discovery_measurement_count(const discovery_device *);
const char *discovery_measurement(const discovery_device *,unsigned);
discovery_reading discovery_read(const discovery_bus *,const discovery_device *,const char *);
const char *discovery_error_name(int);
