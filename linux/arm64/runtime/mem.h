/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
/* Copyright 2018 John Maloney, Bernat Romagosa, and Jens Mönig.
 * LP64 adaptation: object references are offsets, native pointers stay native.
 * Derived from MicroBlocks SmallVM 2071df569623ba9cdcd6f8106b61796e047df38b. */
#ifndef _MEM_H_
#define _MEM_H_
#include <stdint.h>
#include "arena.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef unsigned char uint8;
typedef unsigned short uint16;
typedef unsigned int uint32;
typedef unsigned long long uint64;
typedef signed short int int16;
typedef uint32_t OBJ;

#if !defined(__cplusplus)
#ifndef true
#define true 1
#define false 0
#endif
#endif

#define FREE_CHUNK 0
#define BooleanType 1
#define IntegerType 2
#define ByteArrayType 3
#define StringType 4
#define BinaryObjectTypes 7
#define ArrayType 8
#define ListType 9
#define falseObj ((OBJ)0)
#define trueObj ((OBJ)4)
#define isBoolean(obj) (((obj) == falseObj) || ((obj) == trueObj))
#define isInt(obj) (((OBJ)(obj) & 1u) != 0)
/* Shift unsigned to avoid undefined behavior for negative integers. Decode
 * signed31 without relying on implementation-defined right shift of negatives. */
#define int2obj(n) ((OBJ)(((uint32_t)(n) << 1) | 1u))
static inline int smallvmObj2Int(OBJ obj) {
    uint32_t magnitude = obj >> 1;
    return (magnitude & 0x40000000u) ? -(int)(0x80000000u - magnitude) : (int)magnitude;
}
#define obj2int(obj) smallvmObj2Int((OBJ)(obj))
#define zeroObj ((OBJ)1)

#define HEADER_WORDS 1
#define HEADER(typeID, wordCount) (((uint32_t)(wordCount) << 4) | ((uint32_t)(typeID) & 0xFu))
#define WORDS(obj) ((*O2A(obj) >> 4) & 0xFFFFu)
#define TYPE(obj) (*O2A(obj) & 0xFu)
#define BYTECOUNT_ADJUST(obj) ((*O2A(obj) >> 29) & 3u)
#define BYTES(obj) (4u * WORDS(obj) - BYTECOUNT_ADJUST(obj))
#define FIELD(obj, i) (O2A(obj)[HEADER_WORDS + (i)])
#define IS_TYPE(obj, typeID) (!isInt(obj) && (OBJ)(obj) > trueObj && O2A(obj) && TYPE(obj) == (typeID))

static inline int objWords(OBJ obj) {
    return (isInt(obj) || isBoolean(obj)) ? 0 : (int)WORDS(obj);
}
static inline int objType(OBJ obj) {
    if (isInt(obj)) return IntegerType;
    if (isBoolean(obj)) return BooleanType;
    return O2A(obj) ? (int)TYPE(obj) : FREE_CHUNK;
}
static inline void setByteCountAdjust(OBJ obj, int byteCount) {
    if (!IS_TYPE(obj, ByteArrayType)) return;
    uint32_t delta = (4u - ((uint32_t)byteCount & 3u)) & 3u;
    *O2A(obj) = (delta << 29) | (*O2A(obj) & 0x9FFFFFFFu);
}

extern OBJ tempGCRoot;
void memInit(void);
void memClear(void);
int wordsFree(void);
int hasPSRAM(void);
void gc(void);
OBJ newObj(int typeID, int wordCount, OBJ fill);
OBJ resizeObj(OBJ obj, int wordCount);
OBJ newString(int byteCount);
OBJ newStringFromBytes(const char *bytes, int byteCount);
char *obj2str(OBJ obj);
void reportNum(const char *msg, int n);
void reportHex(const char *msg, int n);
void reportObj(const char *msg, OBJ obj);
void dumpObjectStore(void);
void memDumpObj(OBJ obj);
void vmPanic(const char *message);

#ifdef __cplusplus
}
#endif
#endif
