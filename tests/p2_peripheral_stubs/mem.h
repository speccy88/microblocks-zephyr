/* SPDX-License-Identifier: MIT */
#ifndef P2_PERIPHERAL_TEST_MEM
#define P2_PERIPHERAL_TEST_MEM
#include <stdint.h>
typedef intptr_t OBJ;
enum { ListType = 3, StringType = 4, ByteArrayType = 5 };
#define trueObj ((OBJ)4)
#define falseObj ((OBJ)0)
#define zeroObj ((OBJ)1)
#define isInt(o) ((o)&1)
#define obj2int(o) ((int)((o)>>1))
#define int2obj(n) ((((OBJ)(n))*2)+1)
typedef struct { int type, count; OBJ fields[140]; } TestObject;
#define FIELD(o,i) (((TestObject *)(o))->fields[i])
#define IS_TYPE(o,t) (!isInt(o) && (o)>4 && ((TestObject *)(o))->type == (t))
#define BYTES(o) (((TestObject *)(o))->count)
#define obj2str(o) ((char *)&FIELD(o,0))
#endif
