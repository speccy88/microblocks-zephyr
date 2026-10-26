/* SPDX-License-Identifier: MIT */
/* Compile actual pinned driver; suppress only device registration. No transport
 * or startup function is invoked. Zephyr mutex/semaphore/heap remain real. */
#include <zephyr/ztest.h>
#include <zephyr/device.h>
#include "rpc_allocator.h"
#include "esp_hosted_mcu.h"
#include <pb_encode.h>
#include <pb_decode.h>
#include <stdlib.h>
#undef DEVICE_DT_INST_DEFINE
#define DEVICE_DT_INST_DEFINE(...)
#define CONFIG_ESP_HOSTED_MCU_LOG_LEVEL 0
#define CONFIG_ESP_HOSTED_MCU_FW_VERSION_MAJOR 2
#define CONFIG_ESP_HOSTED_MCU_FW_VERSION_MINOR 0
#define CONFIG_ESP_HOSTED_MCU_FW_VERSION_PATCH 0
#define CONFIG_ESP_HOSTED_MCU_EVENT_TASK_STACK_SIZE 4096
#define CONFIG_ESP_HOSTED_MCU_EVENT_TASK_PRIORITY 5
#define CONFIG_ESP_HOSTED_MCU_EVENT_TASK_POLL_MS 10
struct esp_hosted_mcu_spi_config {unsigned unused;};
const struct esp_hosted_mcu_spi_config esp_hosted_mcu_spi_config_0={0};
const struct esp_hosted_mcu_transport_api esp_hosted_mcu_spi_api={0};
#include "esp_hosted_mcu.c"
static uint8_t frame[1600];
static size_t used(void){struct p4_rpc_memory_stats s;p4_rpc_memory_stats(&s);return s.used;}
static size_t prepare(void){
 static wifi_ap_record rows[16];Rpc message=Rpc_init_zero;
 message.msg_type=RpcType_Resp;message.msg_id=RpcId_Resp_WifiScanGetApRecords;message.uid=7;
 message.which_payload=Rpc_resp_wifi_scan_get_ap_records_tag;
 message.payload.resp_wifi_scan_get_ap_records.ap_records_count=16;
 message.payload.resp_wifi_scan_get_ap_records.ap_records=rows;
 memset(frame,0,sizeof(frame));struct esp_hosted_mcu_header *h=(void*)frame;
 struct esp_hosted_mcu_tlv *t=(void*)(frame+sizeof(*h));
 pb_ostream_t out=pb_ostream_from_buffer(t->data_value,sizeof(frame)-sizeof(*h)-sizeof(*t));
 zassert_true(pb_encode(&out,Rpc_fields,&message));
 t->ep_type=ESP_HOSTED_MCU_TLV_EP;t->ep_length=6;memcpy(t->ep_value,"RPCRsp",6);
 t->data_type=ESP_HOSTED_MCU_TLV_DATA;t->data_length=out.bytes_written;
 h->if_type=ESP_HOSTED_MCU_SERIAL_IF;h->offset=sizeof(*h);h->len=sizeof(*t)+out.bytes_written;
 return h->offset+h->len;
}
static void arm(Rpc *r){
 memset(r,0,sizeof(*r));k_sem_init(&esp_hosted_mcu_data_0.rpc_sem,0,1);
 esp_hosted_mcu_data_0.rx_stride_aligned=false;
 esp_hosted_mcu_rpc=(struct esp_hosted_mcu_rpc_ctx){.uid=7,.expected_msg_id=RpcId_Resp_WifiScanGetApRecords,.resp=r,.pending=true};
}
ZTEST(rpc_driver,matched_late_and_partial){
 Rpc r;arm(&r);size_t n=prepare();
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n-1),0);
 zassert_true(esp_hosted_mcu_rpc.pending);zassert_equal(used(),0);
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);
 zassert_false(esp_hosted_mcu_rpc.pending);zassert_ok(k_sem_take(&esp_hosted_mcu_data_0.rpc_sem,K_NO_WAIT));
 zassert_equal(r.payload.resp_wifi_scan_get_ap_records.ap_records_count,16);size_t held=used();zassert_true(held>0);
 /* A late duplicate is not handed off again and cannot free the retained result. */
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);zassert_equal(used(),held);
 pb_release(Rpc_fields,&r);zassert_equal(used(),0);
}
ZTEST(rpc_driver,invalid_and_failed_frames){
 Rpc r;arm(&r);size_t n=prepare();struct esp_hosted_mcu_header *h=(void*)frame;
 h->len=ESP_HOSTED_MCU_MAX_PAYLOAD+1;zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);zassert_equal(used(),0);
 n=prepare();h->offset++;zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);zassert_equal(used(),0);
 n=prepare();struct esp_hosted_mcu_tlv *t=(void*)(frame+sizeof(*h));t->data_length=UINT16_MAX;
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);zassert_equal(used(),0);
 n=prepare();h->len=1;zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,sizeof(*h)+1),sizeof(*h)+1);zassert_equal(used(),0);
 n=prepare();p4_rpc_fail_allocation(3);
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);p4_rpc_fail_allocation(0);
 zassert_true(esp_hosted_mcu_rpc.pending);zassert_not_equal(k_sem_take(&esp_hosted_mcu_data_0.rpc_sem,K_NO_WAIT),0);zassert_equal(used(),0);
 /* Existing bounded timeout owner can disarm; subsequent late data is released. */
 esp_hosted_mcu_rpc.pending=false;zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n),n);zassert_equal(used(),0);
}
ZTEST(rpc_driver,aggregate_padding_boundary){
 Rpc r;arm(&r);size_t n=prepare();size_t stride=ROUND_UP(n,4);
 zassert_true(stride>n,"Fixture must exercise missing padding");
 uint8_t *short_frame=malloc(n);zassert_not_null(short_frame);memcpy(short_frame,frame,n);
 esp_hosted_mcu_data_0.rx_stride_aligned=true;
 /* Incomplete padding must be carried, not interpreted beyond received bytes. */
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,short_frame,n),0);
 zassert_true(esp_hosted_mcu_rpc.pending);zassert_equal(used(),0);free(short_frame);
 zassert_equal(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,stride),stride);
 zassert_false(esp_hosted_mcu_rpc.pending);pb_release(Rpc_fields,&r);zassert_equal(used(),0);
}
ZTEST(rpc_driver,mutated_frames){
 uint32_t seed=0x81c993u;
 for(unsigned i=0;i<2000;i++){
  Rpc r;arm(&r);size_t n=prepare();seed=seed*1664525u+1013904223u;
  frame[seed%n]^=(uint8_t)(seed>>24);
  esp_hosted_mcu_data_0.rx_stride_aligned=(i%2)!=0;
  zassert_true(esp_hosted_mcu_process_frame(&esp_hosted_mcu_data_0,frame,n)<=n);
  pb_release(Rpc_fields,&r);esp_hosted_mcu_rpc.pending=false;zassert_equal(used(),0);
 }
}
static void after(void *unused){ARG_UNUSED(unused);zassert_true(p4_rpc_heap_valid());zassert_equal(used(),0);}
ZTEST_SUITE(rpc_driver,NULL,NULL,NULL,after,NULL);
