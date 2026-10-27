"""Audited v417 persistence migration to the LP64 arena, retaining 32-bit records."""
# SPDX-License-Identifier: MPL-2.0


def once(source, before, after):
    count = source.count(before)
    if count != 1:
        raise ValueError(f'Unexpected pinned persistence anchor ({count}): {before[:80]!r}')
    return source.replace(before, after, 1)


def patch_persist(source):
    source = once(source, '#include "persist.h"', '#include "persist.h"\n#include "arena.h"')
    source = once(source, '\t#if defined(ESP8266)\n\t\t#define USE_CODE_FILE',
                  '\t#if defined(SMALLVM_LINUX_ARM64)\n\t\t#define USE_CODE_FILE true\n\t\t#define HALF_SPACE (512 * 1024)\n\t#elif defined(ESP8266)\n\t\t#define USE_CODE_FILE')
    source = once(source, 'static uint8 flash[HALF_SPACE] __attribute__ ((aligned (32))); // simulated Flash memory',
                  'static uint8 *flash; // arena-backed, native address; persisted records stay 32-bit')
    source = once(source,
                  'static int *start0 = (int *) START;\nstatic int *end0 = (int *) (START + HALF_SPACE);\nstatic int *start1 = (int *) (START + HALF_SPACE);\nstatic int *end1 = (int *) (START + (2 * HALF_SPACE));;',
                  'static int *start0;\nstatic int *end0;\nstatic int *start1;\nstatic int *end1;')
    source = once(source, 'static void initPersistentMemory() {',
                  'static void initPersistentMemory() {\n'
                  '\tif (smallvmArenaInit() != 0 || smallvmCodeBytes() != HALF_SPACE) vmPanic("Linux code arena unavailable");\n'
                  '\tflash = (uint8 *) smallvmCodeStart();')
    source = once(source, 'chunks[chunkIndex].code = p;', 'chunks[chunkIndex].code = A2O(p);')
    source = once(source, 'chunks[chunkIndex].code = NULL;', 'chunks[chunkIndex].code = 0;')
    source = once(source,
                  '\tstatic void flashWriteData(int *dst, int wordCount, uint8 *src) {\n\t\tfor ( ; wordCount > 0; wordCount--) {\n\t\t\tint n = *src++;\n\t\t\tn |= *src++ << 8;\n\t\t\tn |= *src++ << 16;\n\t\t\tn |= *src++ << 24;\n\t\t\t*dst++ = n;\n\t\t}\n\t}',
                  '\tstatic void flashWriteData(int *dst, int wordCount, uint8 *src) {\n\t\tfor ( ; wordCount > 0; wordCount--) {\n\t\t\tuint32 n = *src++;\n\t\t\tn |= (uint32) *src++ << 8;\n\t\t\tn |= (uint32) *src++ << 16;\n\t\t\tn |= (uint32) *src++ << 24;\n\t\t\t*dst++ = (int32_t) n;\n\t\t}\n\t}')
    source = once(source, 'int codeFileBytes = initCodeFile(flash, HALF_SPACE);',
                  'int codeFileBytes = initCodeFile(flash, HALF_SPACE);\n'
                  '\t\tif (codeFileBytes < 4 || codeFileBytes > HALF_SPACE || (codeFileBytes & 3)) vmPanic("Invalid Linux code file length");')
    source = source.replace('(%lu msecs)', '(%u msecs)')
    # Difference values are bounded by the fixed code arena; keep diagnostics
    # type-correct on LP64 without changing the persisted data representation.
    source = source.replace('(p - start),', '(int) (p - start),')
    source = source.replace('(p - start0),', '(int) (p - start0),')
    source = source.replace('freeStart - ((0 == current) ? start0 : start1),',
                            '(int) (freeStart - ((0 == current) ? start0 : start1)),')
    return source
