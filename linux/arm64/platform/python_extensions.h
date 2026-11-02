/* SPDX-License-Identifier: MPL-2.0 */
#ifndef SMALLVM_LINUX_PYTHON_EXTENSIONS_H
#define SMALLVM_LINUX_PYTHON_EXTENSIONS_H
/* Include vm/interp.h once before this header (the pinned header has no guard). */
#include <stddef.h>
/* Shared bounded asynchronous Unix RPC engine; preserves existing MicroDuck
 * job IDs, cancellation, peer verification and mutation validation. */
OBJ linuxRpcBegin(const char *method,char *params,size_t length,int confirmed);
OBJ linuxRpcPrimitive(int operation,int argc,OBJ *args);
int linuxRpcCopyString(OBJ value,char *destination,size_t maximum,size_t *length);
void addLinuxPythonPrims(void);
#endif
