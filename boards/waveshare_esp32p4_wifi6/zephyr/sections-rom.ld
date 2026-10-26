/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/linker/iterable_sections.h>
ITERABLE_SECTION_ROM(http_resource_desc_p4_http, Z_LINK_ITERABLE_SUBALIGN)
/* Regression floor only: actual concurrent allocation/fragmentation still
 * requires runtime measurement. Never count the separate k_malloc heap here. */
ASSERT(_libc_heap_size >= 8192, "P4 hosted libc arena below 8192-byte audit floor")
