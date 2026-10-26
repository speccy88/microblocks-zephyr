/* SPDX-License-Identifier: MPL-2.0 */
#ifndef MB_STORAGE_PRIMITIVES_H
#define MB_STORAGE_PRIMITIVES_H
#include "storage.h"
/* VM-thread-only shared service; initialization does not erase on reconnect. */
mb_store *mb_storage_store(void);
void addStoragePrims(void);
void mb_storage_poll(void);
void mb_storage_stop(void);
#endif
