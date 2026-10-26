/* SPDX-License-Identifier: MPL-2.0 */
#include "c6_trace.h"
#include <stdio.h>
#include <stdint.h>
#if defined(CONFIG_ESP_HOSTED_MCU)
#include <zephyr/kernel.h>
#include <string.h>
#include <pb_decode.h>
#include "esp_hosted_mcu.h"
typedef struct {uint32_t interface,number,flags,packet_type,length,offset,sequence;} trace_header;
typedef struct {
 uint32_t rx_polls,rx_counter,rx_consumed,tx_credit_polls,tx_credits,tx_spent;
 uint32_t rx_transfers,rx_bytes,tx_transfers,tx_bytes,invalid_headers,valid_headers;
 uint32_t bus_errors,floating_reads,interrupt_status;
 int last_bus_error,version_rpc_error;
 uint32_t tlv_length,endpoint_length,endpoint_kind,rpc_type,rpc_id,rpc_uid,rpc_payload,rpc_decode_errors,tag_count,tags[8][3];
 uint32_t request_id,request_payload,request_uid,request_checksum;
 trace_header first[8];
} trace_state;
static trace_state state;
static struct k_spinlock trace_lock;
static struct {bool busy;unsigned count;int result,reply_id,reply_status;int64_t elapsed;} control;
K_SEM_DEFINE(control_ready,0,1);
#if !defined(CONFIG_P4_HOSTED)
static void control_worker(void *a,void *b,void *c)
{
 (void)a;(void)b;(void)c;
 for(;;){
  k_sem_take(&control_ready,K_FOREVER);
  Rpc req=Rpc_init_zero,resp=Rpc_init_zero;
  req.msg_id=RpcId_Req_GetMACAddress;req.which_payload=Rpc_req_get_mac_address_tag;
  req.payload.req_get_mac_address.mode=0;
  int64_t began=k_uptime_get();int result=esp_hosted_mcu_rpc_call(&req,&resp,5000);
  int reply=resp.msg_id,status=resp.which_payload==Rpc_resp_get_mac_address_tag?resp.payload.resp_get_mac_address.resp:-1;
  /* The returned address is never copied to diagnostic storage or output. */
  pb_release(Rpc_fields,&resp);memset(&req,0,sizeof(req));memset(&resp,0,sizeof(resp));
  k_spinlock_key_t key=k_spin_lock(&trace_lock);
  control.result=result;control.reply_id=reply;control.reply_status=status;control.elapsed=k_uptime_get()-began;control.busy=false;
  k_spin_unlock(&trace_lock,key);
 }
}
K_THREAD_DEFINE(c6_control_worker,16384,control_worker,NULL,NULL,NULL,8,0,0);
int p4_c6_query_start(void)
{
 k_spinlock_key_t key=k_spin_lock(&trace_lock);
 if(control.busy){k_spin_unlock(&trace_lock,key);return 0;}
 control.busy=true;control.count++;control.result=-EINPROGRESS;control.reply_id=0;control.reply_status=-1;
 k_spin_unlock(&trace_lock,key);k_sem_give(&control_ready);return 1;
}
#else
/* Production AP control owns RPCs; the optional diagnostic needs no stack. */
int p4_c6_query_start(void){return 0;}
#endif
unsigned p4_c6_query_count(void){k_spinlock_key_t key=k_spin_lock(&trace_lock);unsigned n=control.count;k_spin_unlock(&trace_lock,key);return n;}
static void increment(uint32_t *value){if(*value!=UINT32_MAX)(*value)++;}
/* Called only with metadata: no payload address can enter this recorder. */
void esp_hosted_mcu_diag(unsigned stage,uint32_t a,uint32_t b,uint32_t c,uint32_t d,int error)
{
 (void)c;
 k_spinlock_key_t key=k_spin_lock(&trace_lock);
 if(stage==1){
  if(state.valid_headers<8)state.first[state.valid_headers]=(trace_header){a&15,(a>>8)&15,(a>>16)&255,a>>24,b,c,d};
  increment(&state.valid_headers);
 }else if(stage==2)increment(&state.invalid_headers);
 else if(stage==3){increment(&state.rx_polls);state.rx_counter=a;state.rx_consumed=b;if(a==0xfffff)increment(&state.floating_reads);}
 else if(stage==4){increment(&state.tx_credit_polls);state.tx_credits=a;state.tx_spent=b;}
 else if(stage==5){
  if(a){increment(&state.tx_transfers);if(!error && UINT32_MAX-state.tx_bytes>=b)state.tx_bytes+=b;}
  else {increment(&state.rx_transfers);if(!error && UINT32_MAX-state.rx_bytes>=b)state.rx_bytes+=b;}
 }else if(stage==6)state.interrupt_status=a;
 else if(stage==7)state.version_rpc_error=error;
 else if(stage==8){state.tlv_length=a;state.endpoint_length=b;state.endpoint_kind=c;}
 else if(stage==9){if(error)increment(&state.rpc_decode_errors);else{state.rpc_type=a;state.rpc_id=b;state.rpc_uid=c;state.rpc_payload=d;}}
 else if(stage==10){state.request_id=a;state.request_payload=b;state.request_uid=c;state.request_checksum=(a==350||a==257)?d:0;}
 else if(stage==11){if(state.tag_count<8){state.tags[state.tag_count][0]=a;state.tags[state.tag_count][1]=b;state.tags[state.tag_count][2]=c;}increment(&state.tag_count);}
 if(error && stage!=7 && stage!=9){increment(&state.bus_errors);state.last_bus_error=error;}
 k_spin_unlock(&trace_lock,key);
}
void p4_c6_trace_json(int index,char *out,size_t n)
{
 if(index==-4){
#if defined(CONFIG_P4_HOSTED)
  snprintf(out,n,"{\"available\":false,\"reason\":\"read-only probe disabled in hosted profile\"}");return;
#else
  k_spinlock_key_t key=k_spin_lock(&trace_lock);bool busy=control.busy;int result=control.result,reply=control.reply_id,status=control.reply_status;int64_t elapsed=control.elapsed;unsigned count=control.count;k_spin_unlock(&trace_lock,key);
  snprintf(out,n,"{\"busy\":%s,\"read_only_query_count\":%u,\"result\":%d,\"reply_id\":%d,\"reply_status\":%d,\"elapsed_ms\":%lld,\"address_recorded\":false,\"rf_configuration_requests\":false}",busy?"true":"false",count,result,reply,status,(long long)elapsed);return;
#endif
 }
 trace_state copy;k_spinlock_key_t key=k_spin_lock(&trace_lock);copy=state;k_spin_unlock(&trace_lock,key);
 if(index>=0 && index<8 && (uint32_t)index<copy.valid_headers){
  trace_header *h=&copy.first[index];
  snprintf(out,n,"{\"if\":%u,\"number\":%u,\"flags\":%u,\"packet_type\":%u,\"length\":%u,\"offset\":%u,\"sequence\":%u}",h->interface,h->number,h->flags,h->packet_type,h->length,h->offset,h->sequence);
 }else if(index==-1){
  snprintf(out,n,"{\"enabled\":true,\"rx_polls\":%u,\"rx_counter\":%u,\"rx_consumed\":%u,\"tx_credit_polls\":%u,\"tx_credits\":%u,\"tx_spent\":%u,\"rx_transfers\":%u,\"rx_bytes\":%u,\"tx_transfers\":%u,\"tx_bytes\":%u,\"valid_headers\":%u,\"invalid_headers\":%u,\"bus_errors\":%u,\"last_bus_error\":%d,\"floating_reads\":%u,\"interrupt_status\":%u,\"version_rpc_error\":%d}",
   copy.rx_polls,copy.rx_counter,copy.rx_consumed,copy.tx_credit_polls,copy.tx_credits,copy.tx_spent,copy.rx_transfers,copy.rx_bytes,copy.tx_transfers,copy.tx_bytes,copy.valid_headers,copy.invalid_headers,copy.bus_errors,copy.last_bus_error,copy.floating_reads,copy.interrupt_status,copy.version_rpc_error);
 }else if(index==-2){
  snprintf(out,n,"{\"tlv_length\":%u,\"endpoint_length\":%u,\"endpoint_kind\":%u,\"rpc_type\":%u,\"rpc_id\":%u,\"rpc_uid\":%u,\"rpc_payload\":%u,\"rpc_decode_errors\":%u,\"tag_count\":%u}",copy.tlv_length,copy.endpoint_length,copy.endpoint_kind,copy.rpc_type,copy.rpc_id,copy.rpc_uid,copy.rpc_payload,copy.rpc_decode_errors,copy.tag_count);
 }else if(index==-3)snprintf(out,n,"{\"request_id\":%u,\"request_payload\":%u,\"request_uid\":%u,\"request_checksum\":%u}",copy.request_id,copy.request_payload,copy.request_uid,copy.request_checksum);
 else if(index>=8 && index<16 && (uint32_t)(index-8)<copy.tag_count)snprintf(out,n,"{\"tag\":%u,\"length\":%u,\"capability_value\":%u}",copy.tags[index-8][0],copy.tags[index-8][1],copy.tags[index-8][2]);
 else snprintf(out,n,"{\"present\":false}");
}
#else
void p4_c6_trace_json(int index,char *out,size_t n){(void)index;snprintf(out,n,"{\"enabled\":false}");}
int p4_c6_query_start(void){return 0;}
unsigned p4_c6_query_count(void){return 0;}
#endif
