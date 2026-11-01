/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
/* Copyright 2018 John Maloney, Bernat Romagosa, and Jens Mönig.
 * LP64 offset-reference allocator/collector derived from SmallVM v417,
 * 2071df569623ba9cdcd6f8106b61796e047df38b. Object and persisted word widths
 * remain 32 bits. Native addresses are obtained only through the arena API. */
#include "mem.h"
#include "interp.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEAP_WORDS (SMALLVM_HEAP_BYTES / sizeof(uint32_t))
#define MAX_HEAP_OBJECTS (HEAP_WORDS / 2u)
static uint8 allocated[(HEAP_WORDS + 7u) / 8u];
static OBJ worklist[MAX_HEAP_OBJECTS];
static size_t workCount;
static OBJ heapBegin, heapEnd, freeChunk;
static OBJ allocationFillRoot, resizeRoot;
OBJ tempGCRoot;
extern OBJ lastBroadcast;

void vmPanic(const char *message) {
    fprintf(stderr, "SmallVM panic: %s\n", message ? message : "unknown error");
    exit(EXIT_FAILURE);
}

static size_t wordIndex(OBJ ref) { return (ref - heapBegin) / sizeof(uint32_t); }
static void setAllocated(OBJ ref, int value) {
    size_t index = wordIndex(ref);
    if (index >= HEAP_WORDS) vmPanic("heap bitmap index outside arena");
    uint8 bit = (uint8)(1u << (index & 7u));
    if (value) allocated[index >> 3] |= bit;
    else allocated[index >> 3] &= (uint8)~bit;
}
static int isHeapObject(OBJ ref) {
    if (ref <= heapBegin || ref >= heapEnd || (ref & 3u)) return false;
    size_t index = wordIndex(ref);
    return (allocated[index >> 3] & (1u << (index & 7u))) != 0;
}
static int isCodeReference(OBJ ref) {
    OBJ start = A2O(smallvmCodeStart());
    return ref >= start && (size_t)(ref - start) <= smallvmCodeBytes() - sizeof(uint32_t) && !(ref & 3u);
}
static uint32_t chunkWords(OBJ ref) {
    if (ref <= heapBegin || ref >= heapEnd || (ref & 3u)) vmPanic("invalid heap chunk address");
    uint32_t count = WORDS(ref);
    if ((size_t)count * 4u > (size_t)(heapEnd - ref - 4u)) vmPanic("heap chunk crosses arena boundary");
    return count;
}
static OBJ nextChunk(OBJ ref) { return ref + 4u * (chunkWords(ref) + 2u); }
static uint32_t *forwardingSlot(OBJ ref) { return O2A(ref) - 1; }

int hasPSRAM(void) { return false; }

void memInit(void) {
    _Static_assert(sizeof(OBJ) == 4, "Object references must remain 32-bit");
    _Static_assert(sizeof(uint32) == 4 && sizeof(int) == 4, "SmallVM integer ABI must remain 32-bit");
    if (smallvmArenaInit() != 0) vmPanic("could not allocate object/code arena");
    heapBegin = A2O(smallvmHeapStart());
    heapEnd = heapBegin + (OBJ)smallvmHeapBytes();
    memClear();
}

void memClear(void) {
    if (!smallvmHeapStart()) vmPanic("object arena not initialized");
    for (int i = 0; i < MAX_VARS; ++i) vars[i] = zeroObj;
    lastBroadcast = zeroObj;
    tempGCRoot = allocationFillRoot = resizeRoot = falseObj;
    memset(smallvmHeapStart(), 0, smallvmHeapBytes());
    memset(allocated, 0, sizeof(allocated));
    workCount = 0;
    freeChunk = heapBegin + 4u;
    *O2A(freeChunk) = HEADER(FREE_CHUNK, HEAP_WORDS - 2u);
}

int wordsFree(void) {
    int result = (int)chunkWords(freeChunk) - 2;
    return result > 0 ? result : 0;
}

static void forEachRoot(void (*visit)(OBJ *)) {
    for (int i = 0; i < MAX_VARS; ++i) visit(&vars[i]);
    visit(&lastBroadcast);
    visit(&tempGCRoot);
    visit(&allocationFillRoot);
    visit(&resizeRoot);
    if (taskCount < 0 || taskCount > MAX_TASKS) vmPanic("invalid task count during collection");
    for (int i = 0; i < taskCount; ++i) {
        Task *task = &tasks[i];
        if (task->status == unusedTask) continue;
        if (task->sp < 0 || task->sp > STACK_LIMIT) vmPanic("invalid task stack during collection");
        for (int j = 0; j < task->sp; ++j) visit(&task->stack[j]);
    }
}

static void enqueueRoot(OBJ *slot) {
    OBJ ref = *slot;
    if (isInt(ref) || isBoolean(ref) || isCodeReference(ref)) return;
    if (!isHeapObject(ref)) vmPanic("invalid object reference during collection");
    if (*forwardingSlot(ref)) return;
    *forwardingSlot(ref) = 1u; /* Mark before enqueue, including cyclic lists. */
    if (workCount >= MAX_HEAP_OBJECTS) vmPanic("object marking worklist overflow");
    worklist[workCount++] = ref;
}

static void clearForwardingFields(void) {
    for (OBJ ref = heapBegin + 4u; ref < heapEnd; ref = nextChunk(ref)) *forwardingSlot(ref) = 0;
}

static void forwardRoot(OBJ *slot) {
    OBJ ref = *slot;
    if (isHeapObject(ref)) {
        OBJ forwarded = *forwardingSlot(ref);
        if (forwarded) *slot = forwarded;
    }
}

static void applyForwarding(void) {
    for (OBJ ref = heapBegin + 4u; ref < heapEnd; ref = nextChunk(ref)) {
        if (TYPE(ref) > BinaryObjectTypes) {
            uint32_t count = chunkWords(ref);
            for (uint32_t i = 0; i < count; ++i) forwardRoot(&FIELD(ref, i));
        }
    }
    forEachRoot(forwardRoot);
}

void gc(void) {
    captureIncomingBytes();
    updateMicrobitDisplay();
    uint32 start = microsecs();
    clearForwardingFields();
    workCount = 0;
    forEachRoot(enqueueRoot);
    while (workCount) {
        OBJ ref = worklist[--workCount];
        if (TYPE(ref) > BinaryObjectTypes) {
            uint32_t count = chunkWords(ref);
            for (uint32_t i = 0; i < count; ++i) enqueueRoot(&FIELD(ref, i));
        }
    }

    OBJ destination = heapBegin + 4u;
    for (OBJ ref = heapBegin + 4u; ref < heapEnd; ref = nextChunk(ref)) {
        if (*forwardingSlot(ref)) {
            *forwardingSlot(ref) = destination;
            destination += 4u * (chunkWords(ref) + 2u);
        } else {
            *O2A(ref) = HEADER(FREE_CHUNK, chunkWords(ref));
        }
    }
    applyForwarding();

    destination = heapBegin + 4u;
    memset(allocated, 0, sizeof(allocated));
    for (OBJ ref = heapBegin + 4u; ref < heapEnd;) {
        uint32_t count = chunkWords(ref);
        OBJ next = ref + 4u * (count + 2u);
        if (TYPE(ref) != FREE_CHUNK) {
            memmove(O2A(destination), O2A(ref), 4u * (count + 1u));
            *forwardingSlot(destination) = 0;
            setAllocated(destination, true);
            destination += 4u * (count + 2u);
        }
        ref = next;
    }
    if (destination >= heapEnd) vmPanic("collector left no free chunk header");
    *forwardingSlot(destination) = 0;
    *O2A(destination) = HEADER(FREE_CHUNK, (heapEnd - destination) / 4u - 1u);
    freeChunk = destination;

    char message[96];
    snprintf(message, sizeof(message), "GC took %u usecs; free %d words", microsecs() - start, wordsFree());
    outputString(message);
    captureIncomingBytes();
    updateMicrobitDisplay();
}

OBJ newObj(int typeID, int wordCount, OBJ fill) {
    if (typeID <= FREE_CHUNK || typeID > 15 || wordCount < 0 || wordCount > 65535) return fail(arraySizeError);
    if (!smallvmHeapStart()) vmPanic("object arena not initialized");
    uint32_t needed = (uint32_t)wordCount + 2u;
    if (chunkWords(freeChunk) < needed) {
        /* Protect a reference-valued fill across compaction. Binary fills are
         * arbitrary 32-bit payload words and must never be traversed as roots. */
        allocationFillRoot = typeID > BinaryObjectTypes ? fill : falseObj;
        gc();
        if (typeID > BinaryObjectTypes) fill = allocationFillRoot;
        allocationFillRoot = falseObj;
        if (chunkWords(freeChunk) < needed) return fail(insufficientMemoryError);
    }
    uint32_t available = chunkWords(freeChunk);
    OBJ result = freeChunk;
    freeChunk += 4u * needed;
    *O2A(freeChunk) = HEADER(FREE_CHUNK, available - needed);
    *forwardingSlot(freeChunk) = 0;
    *forwardingSlot(result) = 0;
    *O2A(result) = HEADER(typeID, wordCount);
    for (int i = 0; i < wordCount; ++i) FIELD(result, i) = fill;
    setAllocated(result, true);
    return result;
}

OBJ resizeObj(OBJ oldObj, int wordCount) {
    if (!isHeapObject(oldObj)) return oldObj;
    if (wordCount < 0 || wordCount > 65535) { fail(arraySizeError); return oldObj; }
    resizeRoot = oldObj;
    OBJ result = newObj((int)TYPE(oldObj), wordCount, zeroObj);
    oldObj = resizeRoot;
    resizeRoot = falseObj;
    if (!result) return oldObj;
    uint32_t count = WORDS(oldObj);
    if ((uint32_t)wordCount < count) count = (uint32_t)wordCount;
    memcpy(&FIELD(result, 0), &FIELD(oldObj, 0), 4u * count);
    if (TYPE(oldObj) == ByteArrayType && wordCount > 0) *O2A(result) |= *O2A(oldObj) & 0x60000000u;
    clearForwardingFields();
    *forwardingSlot(oldObj) = result;
    applyForwarding();
    *forwardingSlot(oldObj) = 0;
    *O2A(oldObj) = HEADER(FREE_CHUNK, WORDS(oldObj));
    setAllocated(oldObj, false);
    return result;
}

OBJ newString(int byteCount) {
    if (byteCount < 0 || byteCount > 65535 * 4 - 1) return fail(arraySizeError);
    return newObj(StringType, (byteCount + 4) / 4, 0);
}

OBJ newStringFromBytes(const char *bytes, int byteCount) {
    if (byteCount < 0 || byteCount > 65535 * 4 - 1 || (byteCount && !bytes)) return fail(arraySizeError);
    /* A source within the arena can move if allocation triggers collection.
     * Copy it first, unlike assuming a native pointer stays valid across GC. */
    char *copy = NULL;
    if (byteCount) {
        copy = malloc((size_t)byteCount);
        if (!copy) return fail(insufficientMemoryError);
        memcpy(copy, bytes, (size_t)byteCount);
    }
    OBJ result = newString(byteCount);
    if (result) {
        char *destination = (char *)&FIELD(result, 0);
        if (byteCount) memcpy(destination, copy, (size_t)byteCount);
        destination[byteCount] = '\0';
    }
    free(copy);
    return result;
}

char *obj2str(OBJ obj) {
    if (isInt(obj)) return (char *)"<Integer>";
    if (isBoolean(obj)) return (char *)(obj == trueObj ? "true" : "false");
    if (IS_TYPE(obj, StringType)) return (char *)&FIELD(obj, 0);
    if (IS_TYPE(obj, ListType)) return (char *)"<List>";
    if (IS_TYPE(obj, ByteArrayType)) return (char *)"<ByteArray>";
    return (char *)"<Object>";
}

void reportNum(const char *message, int value) {
    char text[160]; snprintf(text, sizeof(text), "%s: %d", message, value); outputString(text);
}
void reportHex(const char *message, int value) {
    char text[160]; snprintf(text, sizeof(text), "%s: 0x%x", message, (unsigned)value); outputString(text);
}
void reportObj(const char *message, OBJ obj) {
    char text[160];
    if (isInt(obj)) snprintf(text, sizeof(text), "%s: %d", message, obj2int(obj));
    else snprintf(text, sizeof(text), "%s: %s (type %d)", message, obj2str(obj), objType(obj));
    outputString(text);
}
void memDumpObj(OBJ obj) {
    char text[128];
    if (!isHeapObject(obj) && !isCodeReference(obj)) snprintf(text, sizeof(text), "invalid object offset 0x%x", obj);
    else snprintf(text, sizeof(text), "object offset 0x%x: type %u, words %u", obj, TYPE(obj), WORDS(obj));
    outputString(text);
}
void dumpObjectStore(void) {
    for (OBJ ref = heapBegin + 4u; ref < heapEnd; ref = nextChunk(ref)) memDumpObj(ref);
}
