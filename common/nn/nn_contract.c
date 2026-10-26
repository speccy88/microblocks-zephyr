/* SPDX-License-Identifier: MIT */
#include "nn_contract.h"
#include <string.h>
int nn_shape_check(unsigned dtype,unsigned rank,const int32_t *dims,nn_tensor_desc *out)
{
 if(!out||!dims||!rank||rank>4||dtype<NN_FLOAT32||dtype>NN_INT32)return 0;
 unsigned elements=1;
 for(unsigned i=0;i<rank;i++){
  if(dims[i]<=0||(unsigned)dims[i]>NN_MAX_ELEMENTS/elements)return 0;
  elements*=dims[i];
 }
 memset(out,0,sizeof(*out));out->dtype=dtype;out->rank=rank;out->elements=elements;
 out->bytes=elements*(dtype==NN_INT8?1:4);memcpy(out->dims,dims,rank*sizeof(*dims));
 return 1;
}
