/* SPDX-License-Identifier: MIT */
/* Compile only with the actual P4 ABI; never linked into firmware. */
#include "flash_store.h"
const unsigned char mb_flash_context_size[sizeof(mb_flash)]={0};
const unsigned char mb_flash_metadata_size[sizeof(mb_flash_file)]={0};
