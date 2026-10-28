/* SPDX-License-Identifier: MIT */
#ifndef MB_SD_SERVICE_H
#define MB_SD_SERVICE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
/* VM-thread entry points. Backends own all asynchronous buffers and cleanup. */
bool mb_sd_available(void);
bool mb_sd_start(void);
bool mb_sd_busy(void);
void mb_sd_cancel(void);
void mb_sd_poll(void);
void mb_sd_status(char *out, size_t size);
const char *mb_sd_phase(void);
bool mb_sd_result(uint64_t *card_bytes,unsigned *entries);
#endif
