/* SPDX-License-Identifier: MPL-2.0 */
/* Synthetic I/O only; the sender implementation is extracted from pinned VM. */
#include "storage.h"
#include <assert.h>
mb_store test_store;
unsigned char test_output[1024];
unsigned test_output_length,test_output_capacity=1024;
mb_store *mb_storage_store(void){return &test_store;}
int hasOutputSpace(int n){return n>=0&&test_output_capacity-test_output_length>(unsigned)n;}
static void queueByte(int value){assert(test_output_length<sizeof(test_output));test_output[test_output_length++]=(unsigned char)value;}
static void waitForOutbufBytes(int n){assert(hasOutputSpace(n));}
#include "vm_sender.inc"
