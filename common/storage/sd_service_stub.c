/* SPDX-License-Identifier: MIT */
#include "sd_service.h"
#include "sd_file.h"
#include <stdio.h>
bool mb_sd_available(void) { return false; }
bool mb_sd_start(void) { return false; }
bool mb_sd_busy(void) { return false; }
void mb_sd_cancel(void) {}
void mb_sd_poll(void) {}
const char *mb_sd_phase(void) {return "SD checking is unavailable in this firmware";}
bool mb_sd_result(uint64_t *bytes,unsigned *entries) {(void)bytes;(void)entries;return false;}
void mb_sd_status(char *out,size_t n) {
    snprintf(out,n,"{\"available\":false,\"phase\":\"unsupported profile\",\"card_accessed\":false}");
}
bool mb_sd_file_available(void){return false;}
bool mb_sd_file_start(mb_sd_file_op op,const char *name,size_t n,const uint8_t *data,size_t length){(void)op;(void)name;(void)n;(void)data;(void)length;return false;}
bool mb_sd_file_result_get(mb_sd_file_result *out){(void)out;return false;}
bool mb_sd_file_copy(size_t offset,uint8_t *out,size_t length){(void)offset;(void)out;(void)length;return false;}
const uint8_t *mb_sd_file_view(size_t *length){(void)length;return NULL;}
const char *mb_sd_file_last_name(void){return "";}
uint32_t mb_sd_file_generation(void){return 0;}
