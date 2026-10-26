/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define NN_MAX_MODEL_BYTES (256u*1024u)
#define NN_MAX_ARENA_BYTES (512u*1024u)
#define NN_MAX_ELEMENTS 16384u
#define NN_MAX_TENSORS 64u
#define NN_MAX_OPS 16u
#define NN_MAX_MACS 1000000u
enum nn_dtype {NN_FLOAT32=1,NN_INT8=2,NN_INT32=3};
typedef struct {unsigned dtype,rank,elements,bytes;int32_t dims[4];float scale;int32_t zero_point;} nn_tensor_desc;
int nn_shape_check(unsigned dtype,unsigned rank,const int32_t *dims,nn_tensor_desc *out);
#ifdef __cplusplus
}
#endif
