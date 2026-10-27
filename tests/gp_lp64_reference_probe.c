/* SPDX-License-Identifier: MPL-2.0
 * Test only the upstream GP offset-reference macros. GP is NOT SmallVM.
 */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "gp_mem.h"

unsigned char *baseAddress;
gp_boolean cpuIsBigEndian;

int main(void) {
    assert(sizeof(void *) == 8 && sizeof(OBJ) == 4);
    baseAddress = calloc(1, 256);
    assert(baseAddress != NULL);
    ADDR address = (ADDR) (baseAddress + 64);
    OBJ reference = A2O(address);
    assert(reference == 64 && O2A(reference) == address);
    FIELD(reference, 0) = int2obj(12);
    assert(obj2int(FIELD(reference, 0)) == 12);
    assert(sizeof(FIELD(reference, 0)) == 4);
    size_t stride = (unsigned char *) &FIELD(reference, 1) - (unsigned char *) &FIELD(reference, 0);
    assert(stride == 4);
    printf("{\"result\":\"PASS_REFERENCE_ONLY\",\"obj_bytes\":%zu,"
           "\"pointer_bytes\":%zu,\"header_words\":%d,\"field_stride\":%zu,"
           "\"offset_roundtrip\":true,\"positive_integer_roundtrip\":true,"
           "\"smallvm_compatibility_claim\":false}\n",
           sizeof(OBJ), sizeof(void *), HEADER_WORDS, stride);
    free(baseAddress);
    return 0;
}
