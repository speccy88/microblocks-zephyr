/* SPDX-License-Identifier: MIT */
#include "nn_contract.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>
int main(void)
{
 nn_tensor_desc d;int32_t shape[]={1,2,3,4};
 assert(nn_shape_check(NN_FLOAT32,4,shape,&d)&&d.elements==24&&d.bytes==96);
 assert(nn_shape_check(NN_INT8,4,shape,&d)&&d.bytes==24);
 assert(!nn_shape_check(NN_FLOAT32,0,shape,&d));assert(!nn_shape_check(NN_FLOAT32,5,shape,&d));
 assert(!nn_shape_check(99,4,shape,&d));assert(!nn_shape_check(NN_INT8,4,0,&d));
 int32_t bad[][2]={{0,1},{-1,1},{INT_MAX,INT_MAX},{16384,2}};
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++)assert(!nn_shape_check(NN_FLOAT32,2,bad[i],&d));
 for(int32_t x=1;x<=16384;x++){int32_t dims[]={1,x};assert(nn_shape_check(NN_INT32,2,dims,&d)&&d.bytes==(unsigned)x*4);}
 puts("NN tensor bounds, overflow and dtype contract PASS");return 0;
}
