/* SPDX-License-Identifier: MIT */
#include "rpc_allocator.h"
#include <pb_decode.h>
#include <esp_hosted_mcu_rpc.pb.h>
#include <string.h>
#include <errno.h>
#if defined(CONFIG_ESP_HOSTED_MCU)
#include "esp_hosted_mcu.h"
_Static_assert(P4_RPC_PROTO_BYTES==ESP_HOSTED_MCU_MAX_PAYLOAD-sizeof(struct esp_hosted_mcu_tlv),
               "Re-audit protobuf budget after transport framing changes");
#endif
/* Overrides the driver's weak decode hook. On failure no decoded ownership
 * escapes; nanopb releases partial fields. Existing pending-call timeout stays. */
int esp_hosted_mcu_decode_rpc(const uint8_t *data,size_t size,Rpc *rpc)
{
 if(!rpc)return -EINVAL;
 memset(rpc,0,sizeof(*rpc));
 if(!data || !size || size>P4_RPC_PROTO_BYTES)return -EMSGSIZE;
 pb_istream_t stream=pb_istream_from_buffer(data,size);
 if(!pb_decode(&stream,Rpc_fields,rpc)){memset(rpc,0,sizeof(*rpc));return -EBADMSG;}
 /* Complete protobuf fields alone are not a complete RPC. IDs mirror oneof
  * tags in the pinned companion schema; never publish an absent/wrong body. */
 if((rpc->msg_type!=RpcType_Resp && rpc->msg_type!=RpcType_Event) ||
    rpc->msg_id<=0 || (uint32_t)rpc->which_payload!=(uint32_t)rpc->msg_id){
  pb_release(Rpc_fields,rpc);memset(rpc,0,sizeof(*rpc));return -EBADMSG;
 }
 return 0;
}
