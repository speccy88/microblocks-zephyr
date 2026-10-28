/* SPDX-License-Identifier: MIT */
#ifndef P4_SD_READONLY_PROBE_H
#define P4_SD_READONLY_PROBE_H
#include <stdbool.h>
#include <stdint.h>
struct p4_sd_probe_result {
 uint64_t card_bytes,filesystem_bytes,free_bytes;
 unsigned entries,files,directories;
 unsigned filesystem_type;
 int error,free_space_error,close_error,unmount_error;
 bool free_space_available,truncated;
};
/* Single owner only. No recursive traversal or file-content access. */
int p4_sd_readonly_probe(struct p4_sd_probe_result *result);
/* stop returns 0, -ECANCELED or -ETIMEDOUT. Checked between blocking calls;
 * cleanup is always attempted. It is not a forced interruption of DMA. */
int p4_sd_readonly_probe_controlled(struct p4_sd_probe_result *result,
                                  int (*stop)(void *), void *context);
#endif
