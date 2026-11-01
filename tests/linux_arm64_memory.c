/* SPDX-License-Identifier: MPL-2.0
 * Native LP64 tests for the SmallVM offset arena and compacting collector.
 * Interpreter hooks are simulated; allocator, roots, GC and object bytes are real. */
#include "mem.h"
#include "interp.h"
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

OBJ vars[MAX_VARS];
Task tasks[MAX_TASKS];
int taskCount;
OBJ lastBroadcast;
static unsigned checks;
static uint8 lastError;
static uint32 clockTicks;
#define CHECK(condition) do { assert(condition); ++checks; } while (0)
OBJ fail(uint8 error) { lastError = error; return falseObj; }
void captureIncomingBytes(void) {}
void updateMicrobitDisplay(void) {}
uint32 microsecs(void) { return ++clockTicks; }
void outputString(const char *message) { (void)message; }

static void resetMemory(void) {
    memset(tasks, 0, sizeof(tasks)); taskCount = 0;
    lastError = 0;
    memClear();
}

static void arenaAndTags(void) {
    CHECK(sizeof(OBJ) == 4);
    CHECK(sizeof(void *) == 8);
    CHECK(smallvmHeapBytes() == 262144u);
    CHECK(smallvmCodeBytes() == 524288u);
    CHECK((unsigned char *)smallvmCodeStart() == (unsigned char *)smallvmHeapStart() + smallvmHeapBytes());
    CHECK(A2O(smallvmHeapStart()) == SMALLVM_ARENA_RESERVED_BYTES);
    CHECK((uintptr_t)smallvmHeapStart() > UINT32_MAX); /* Sanitized LP64 heap really is above 4 GiB. */
    CHECK(O2A(A2O(smallvmCodeStart())) == smallvmCodeStart());
    CHECK(O2A(falseObj) == NULL && errno == EINVAL);
    CHECK(O2A(trueObj) == NULL && errno == EINVAL);
    CHECK(O2A(int2obj(12)) == NULL && errno == EINVAL);
    CHECK(O2A(UINT32_MAX - 3u) == NULL && errno == EINVAL);
    uint32 outside = 0;
    CHECK(A2O(&outside) == falseObj && errno == EINVAL);
    CHECK(A2O((unsigned char *)smallvmHeapStart() + 1) == falseObj && errno == EINVAL);
    CHECK(A2O((unsigned char *)smallvmCodeStart() + smallvmCodeBytes()) == falseObj && errno == EINVAL);
    int cases[] = {-1073741824, -1073741823, -65536, -1, 0, 1, 65536, 1073741822, 1073741823};
    for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        CHECK(isInt(int2obj(cases[i])));
        CHECK(obj2int(int2obj(cases[i])) == cases[i]);
    }
    CHECK(int2obj(-1) == UINT32_MAX);
    CHECK(objType(trueObj) == BooleanType && objType(int2obj(-1)) == IntegerType);
}

static void stringsAndByteArrays(void) {
    resetMemory();
    for (int size = 0; size <= 65; ++size) {
        OBJ string = newString(size);
        CHECK(TYPE(string) == StringType && WORDS(string) == (uint32)((size + 4) / 4));
        for (int i = 0; i < size; ++i) obj2str(string)[i] = 'A';
        CHECK(obj2str(string)[size] == '\0');
        OBJ bytes = newObj(ByteArrayType, (size + 3) / 4, 0);
        setByteCountAdjust(bytes, size);
        CHECK(BYTES(bytes) == (uint32)size);
        if (size) ((uint8 *)&FIELD(bytes, 0))[size - 1] = 0xC3;
        CHECK(objType(bytes) == ByteArrayType);
    }
    OBJ text = newStringFromBytes("hello \xC3\xA9", 8);
    CHECK(!strcmp(obj2str(text), "hello \xC3\xA9"));
    CHECK(newString(-1) == falseObj && lastError == arraySizeError);
    CHECK(newObj(ListType, -1, zeroObj) == falseObj && lastError == arraySizeError);
    CHECK(newObj(ListType, 65536, zeroObj) == falseObj && lastError == arraySizeError);
}

static void graphAndRoots(void) {
    resetMemory();
    /* Dead prefix forces every live object to move at collection. */
    CHECK(newStringFromBytes("dead prefix", 11) != falseObj);
    OBJ parent = newObj(ListType, 4, zeroObj);
    OBJ child = newObj(ListType, 3, zeroObj);
    OBJ text = newStringFromBytes("retained string", 15);
    FIELD(parent, 0) = int2obj(3);
    FIELD(parent, 1) = child;
    FIELD(parent, 2) = parent; /* self cycle */
    FIELD(parent, 3) = text;
    FIELD(child, 0) = int2obj(2);
    FIELD(child, 1) = parent; /* parent/child cycle */
    FIELD(child, 2) = int2obj(-1073741824);
    vars[0] = parent;
    vars[1] = text;
    lastBroadcast = child;
    tempGCRoot = text;
    taskCount = 2;
    tasks[0].status = running; tasks[0].sp = 2;
    tasks[0].stack[0] = parent; tasks[0].stack[1] = child;
    tasks[1].status = unusedTask; tasks[1].sp = STACK_LIMIT + 100; /* inactive stack ignored */
    OBJ before = parent;
    gc();
    parent = vars[0]; child = FIELD(parent, 1); text = vars[1];
    CHECK(parent < before);
    CHECK(FIELD(parent, 2) == parent);
    CHECK(FIELD(child, 1) == parent);
    CHECK(FIELD(parent, 3) == text && !strcmp(obj2str(text), "retained string"));
    CHECK(obj2int(FIELD(child, 2)) == -1073741824);
    CHECK(lastBroadcast == child && tempGCRoot == text);
    CHECK(tasks[0].stack[0] == parent && tasks[0].stack[1] == child);
    int freeBefore = wordsFree();
    for (unsigned round = 0; round < 100; ++round) {
        CHECK(newStringFromBytes("temporary garbage", 17) != falseObj);
        gc();
        CHECK(wordsFree() == freeBefore);
        CHECK(FIELD(vars[0], 2) == vars[0]);
    }
}

static void resizeAndExternalCode(void) {
    resetMemory();
    uint32 *code = smallvmCodeStart();
    code[0] = HEADER(StringType, 4);
    memcpy(code + 1, "code literal", 13);
    OBJ literal = A2O(code);
    vars[3] = literal;
    CHECK(!strcmp(obj2str(literal), "code literal"));
    CHECK(newObj(ByteArrayType, 200, 0) != falseObj);
    OBJ list = newObj(ListType, 3, zeroObj);
    FIELD(list, 0) = int2obj(2); FIELD(list, 1) = list; FIELD(list, 2) = literal;
    vars[0] = list;
    taskCount = 1; tasks[0].status = running; tasks[0].sp = 1; tasks[0].stack[0] = list;
    lastBroadcast = list; tempGCRoot = list;
    OBJ resized = resizeObj(list, 8);
    CHECK(resized != list && vars[0] == resized);
    CHECK(FIELD(resized, 1) == resized && FIELD(resized, 2) == literal);
    CHECK(tasks[0].stack[0] == resized && lastBroadcast == resized && tempGCRoot == resized);
    CHECK(FIELD(resized, 7) == zeroObj);
    gc();
    resized = vars[0];
    CHECK(FIELD(resized, 1) == resized && FIELD(resized, 2) == literal && vars[3] == literal);
    CHECK(!strcmp(obj2str(literal), "code literal"));
    resized = resizeObj(resized, 2);
    CHECK(WORDS(resized) == 2 && FIELD(resized, 1) == resized);
    CHECK(resizeObj(literal, 100) == literal);
    CHECK(resizeObj(int2obj(42), 3) == int2obj(42));
    OBJ bytes = newObj(ByteArrayType, 2, 0xFEEDC0D0u);
    setByteCountAdjust(bytes, 5); vars[4] = bytes;
    bytes = resizeObj(bytes, 3);
    CHECK(BYTES(bytes) == 9 && FIELD(bytes, 0) == 0xFEEDC0D0u);
    bytes = resizeObj(bytes, 0);
    CHECK(BYTES(bytes) == 0);
    /* memClear clears variables/heap, preserving the persistence code region. */
    resetMemory();
    CHECK(TYPE(literal) == StringType && !strcmp(obj2str(literal), "code literal"));
}

static void automaticCollectionAndResize(void) {
    resetMemory();
    CHECK(newObj(ByteArrayType, 100, 0) != falseObj);
    OBJ retained = newStringFromBytes("fill root", 9);
    vars[0] = retained;
    while (wordsFree() > 20) CHECK(newObj(ByteArrayType, 7, 0) != falseObj);
    OBJ list = newObj(ListType, 100, retained);
    CHECK(list != falseObj && vars[0] < retained);
    CHECK(FIELD(list, 99) == vars[0] && !strcmp(obj2str(FIELD(list, 99)), "fill root"));
    vars[1] = list;
    while (wordsFree() > 20) CHECK(newObj(ByteArrayType, 7, 0) != falseObj);
    OBJ larger = resizeObj(vars[1], 120);
    CHECK(larger && vars[1] == larger && FIELD(larger, 99) == vars[0]);
    CHECK(!strcmp(obj2str(FIELD(larger, 0)), "fill root"));
    CHECK(newObj(ByteArrayType, 65535, 0) == falseObj && lastError == insufficientMemoryError);
    CHECK(IS_TYPE(vars[1], ListType));
    /* Source points inside heap: copying to a new string must survive GC. */
    while (wordsFree() > 20) CHECK(newObj(ByteArrayType, 7, 0) != falseObj);
    CHECK(newObj(ByteArrayType, wordsFree() - 4, 0) != falseObj);
    OBJ copied = newStringFromBytes(obj2str(vars[0]), 9);
    CHECK(copied && !strcmp(obj2str(copied), "fill root"));
    while (wordsFree() > 20) CHECK(newObj(ByteArrayType, 7, 0) != falseObj);
    OBJ binary = newObj(ByteArrayType, 100, 0xFEEDC0D0u);
    CHECK(binary && FIELD(binary, 99) == 0xFEEDC0D0u);
}

static void deepAndWideGraphs(void) {
    resetMemory();
    CHECK(newObj(ByteArrayType, 1000, 0) != falseObj);
    OBJ tail = falseObj;
    for (int i = 0; i < 10000; ++i) {
        OBJ next = newObj(ListType, 2, zeroObj);
        CHECK(next != falseObj);
        FIELD(next, 0) = int2obj(1); FIELD(next, 1) = vars[0];
        if (!tail) tail = next;
        vars[0] = next;
    }
    FIELD(tail, 1) = vars[0]; /* 10,000-object cycle, no C recursion. */
    gc();
    OBJ current = vars[0];
    for (int i = 0; i < 10000; ++i) {
        CHECK(TYPE(current) == ListType && FIELD(current, 0) == int2obj(1));
        current = FIELD(current, 1);
    }
    CHECK(current == vars[0]);
    resetMemory();
    CHECK(newObj(ByteArrayType, 1000, 0) != falseObj);
    vars[0] = newObj(ListType, 16301, zeroObj);
    CHECK(vars[0] != falseObj);
    FIELD(vars[0], 0) = int2obj(16300);
    for (int i = 1; i <= 16300; ++i) {
        OBJ child = newObj(ArrayType, 0, zeroObj);
        CHECK(child != falseObj); FIELD(vars[0], i) = child;
    }
    gc(); /* A broad mark frontier exercises the bounded worklist. */
    for (int i = 1; i <= 16300; ++i) CHECK(TYPE(FIELD(vars[0], i)) == ArrayType);
}

int main(int argc, char **argv) {
    CHECK(smallvmArenaInit() == 0);
    memInit();
    if (argc > 1 && !strcmp(argv[1], "bad-root")) { vars[0] = 8; gc(); return 99; }
    if (argc > 1 && !strcmp(argv[1], "bad-stack")) {
        taskCount = 1; tasks[0].status = running; tasks[0].sp = STACK_LIMIT + 1; gc(); return 99;
    }
    arenaAndTags();
    stringsAndByteArrays();
    graphAndRoots();
    resizeAndExternalCode();
    automaticCollectionAndResize();
    deepAndWideGraphs();
    smallvmArenaDestroy();
    CHECK(O2A(16) == NULL && errno == EINVAL);
    puts("{\"result\":\"PASS\",\"scope\":\"real native LP64 offset arena and compacting GC; simulated interpreter hooks\"}");
    printf("checks=%u\n", checks);
    return 0;
}
