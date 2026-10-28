/* SPDX-License-Identifier: MIT */
#ifndef P4_SD_FILE_IO_H
#define P4_SD_FILE_IO_H
#include "sd_file.h"
/* One SD worker is the sole owner of all filesystem calls. Buffers are CPU-only
 * PSRAM; this implementation bounces every file read/write through internal
 * stack memory. Its filesystem sector window must also remain internal. */
int p4_sd_file_io(mb_sd_file_op op,const char *name,const uint8_t *input,
                 size_t expected,uint8_t *output,mb_sd_file_result *result,
                 int (*stop)(void *),void *context);
#endif
