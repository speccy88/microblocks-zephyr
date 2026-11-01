/* SPDX-License-Identifier: MPL-2.0
 * Run the UNMODIFIED pinned SmallVM memory startup guard on an LP64 host.
 * Platform/transport functions are stubs. No bytecode or device is exercised.
 */
#include <assert.h>
#include <inttypes.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "mem.h"
#include "interp.h"

OBJ vars[MAX_VARS];
OBJ lastBroadcast;
Task tasks[MAX_TASKS];
int taskCount;
static jmp_buf panic_exit;
static int panic_observed;

void outputString(const char *message) {
    if (strstr(message, "MicroBlocks expects int, int*, and float to all be 32-bits")) {
        panic_observed = 1;
        longjmp(panic_exit, 1); /* Avoid the upstream intentional infinite panic loop. */
    }
    abort();
}
void processMessage(void) { abort(); }
void captureIncomingBytes(void) { }
void updateMicrobitDisplay(void) { }
uint32 microsecs(void) { return 0; }
OBJ fail(uint8 error) { (void) error; return falseObj; }

int main(void) {
    assert(sizeof(void *) == 8 && sizeof(int) == 4);
    if (setjmp(panic_exit) == 0) memInit();
    assert(panic_observed); /* Do not disable or bypass the actual upstream guard. */

    _Alignas(16) uint32_t storage[16] = {0};
    OBJ object = (OBJ) storage;
    size_t field_offset = (unsigned char *) &FIELD(object, 0) - (unsigned char *) object;
    size_t word_offset = (unsigned char *) &object[HEADER_WORDS] - (unsigned char *) object;
    assert(field_offset == 8 && word_offset == 4);
    assert(sizeof(FIELD(object, 0)) == 8);
    assert(sizeof(*object) == 4);
    uintptr_t wide_address = UINT64_C(0x1234567887654320);
    uint32_t forwarding_word = (uint32_t) wide_address;
    assert((uintptr_t) forwarding_word != wide_address);

    printf("{\"result\":\"EXPECTED_REJECTION\",\"int_bytes\":%zu,"
           "\"pointer_bytes\":%zu,\"obj_bytes\":%zu,\"heap_word_bytes\":%zu,"
           "\"field_zero_offset\":%zu,\"raw_body_offset\":%zu,"
           "\"mem_init_panic_observed\":true,\"forwarding_truncates_high_bits\":true,"
           "\"vm_bytecode_executed\":false}\n",
           sizeof(int), sizeof(void *), sizeof(OBJ), sizeof(*object), field_offset, word_offset);
    return 0;
}
