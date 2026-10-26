/* SPDX-License-Identifier: MIT */
#include <zephyr/ztest.h>
#include "rpc_allocator.h"
#include <pb_encode.h>
#include <pb_decode.h>
#include <esp_hosted_mcu_rpc.pb.h>
#include <errno.h>
#include <string.h>
#include "storage.h"
int esp_hosted_mcu_decode_rpc(const uint8_t *,size_t,Rpc *);
BUILD_ASSERT(IS_ENABLED(CONFIG_SYS_HEAP_VALIDATE));
static uint8_t wire[1600];
static wifi_ap_record records[600];
static struct p4_rpc_memory_stats stats(void){struct p4_rpc_memory_stats s;p4_rpc_memory_stats(&s);return s;}
static size_t fixture(unsigned n){
 memset(records,0,sizeof(records));zassert_true(n<=ARRAY_SIZE(records));
 Rpc r=Rpc_init_zero;r.msg_type=RpcType_Resp;r.msg_id=RpcId_Resp_WifiScanGetApRecords;r.uid=7;
 r.which_payload=Rpc_resp_wifi_scan_get_ap_records_tag;
 r.payload.resp_wifi_scan_get_ap_records.number=n;
 r.payload.resp_wifi_scan_get_ap_records.ap_records_count=n;
 r.payload.resp_wifi_scan_get_ap_records.ap_records=records;
 pb_ostream_t out=pb_ostream_from_buffer(wire,sizeof(wire));
 zassert_true(pb_encode(&out,Rpc_fields,&r));return out.bytes_written;
}
static void clear(Rpc *r){pb_release(Rpc_fields,r);memset(r,0,sizeof(*r));}
ZTEST(rpc,allocator_contract){
 zassert_equal(stats().used,0);zassert_equal(stats().capacity,65536);
 uint8_t *p=p4_rpc_realloc(NULL,128);zassert_not_null(p);memset(p,0x5a,128);
 size_t used=stats().used;zassert_is_null(p4_rpc_realloc(p,SIZE_MAX));zassert_equal(stats().used,used);
 for(unsigned i=0;i<128;i++)zassert_equal(p[i],0x5a);
 p=p4_rpc_realloc(p,4096);zassert_not_null(p);for(unsigned i=0;i<128;i++)zassert_equal(p[i],0x5a);
 p=p4_rpc_realloc(p,16);zassert_not_null(p);for(unsigned i=0;i<16;i++)zassert_equal(p[i],0x5a);
 zassert_is_null(p4_rpc_realloc(p,0));p4_rpc_free(NULL);zassert_equal(stats().used,0);
}
ZTEST(rpc,complete_and_retained){
 Rpc a,b;size_t n=fixture(64);zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&a));
 zassert_equal(a.payload.resp_wifi_scan_get_ap_records.ap_records_count,64);
 a.payload.resp_wifi_scan_get_ap_records.ap_records[0].rssi=-42;
 size_t held=stats().used;
 zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&b));zassert_true(stats().used>held);
 zassert_equal(a.payload.resp_wifi_scan_get_ap_records.ap_records[0].rssi,-42);
 clear(&b);zassert_equal(stats().used,held);clear(&a);zassert_equal(stats().used,0);
}
ZTEST(rpc,partial_alloc_failure){
 size_t n=fixture(32);
 for(unsigned fail=1;fail<=32;fail++){
  Rpc r;p4_rpc_fail_allocation(fail);zassert_equal(esp_hosted_mcu_decode_rpc(wire,n,&r),-EBADMSG);
  zassert_equal(stats().used,0);zassert_equal(r.which_payload,0);zassert_equal(r.uid,0);
 }
 p4_rpc_fail_allocation(0);Rpc r;zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&r));clear(&r);zassert_equal(stats().used,0);
}
ZTEST(rpc,whole_message_exhaustion){
 Rpc r;size_t n=fixture(600);zassert_true(n<P4_RPC_PROTO_BYTES);
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,n,&r),-EBADMSG);zassert_equal(r.which_payload,0);zassert_equal(stats().used,0);
 n=fixture(16);zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&r));clear(&r);zassert_equal(stats().used,0);
}
ZTEST(rpc,shared_capacity_failure){
 void *held[20];unsigned count=0;while(count<ARRAY_SIZE(held) && (held[count]=p4_rpc_realloc(NULL,4096)))count++;
 zassert_true(count>0 && count<ARRAY_SIZE(held));size_t inuse=stats().used;
 Rpc r;size_t n=fixture(64);zassert_equal(esp_hosted_mcu_decode_rpc(wire,n,&r),-EBADMSG);zassert_equal(stats().used,inuse);
 while(count){p4_rpc_free(held[--count]);}
 zassert_equal(stats().used,0);
 zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&r));clear(&r);zassert_equal(stats().used,0);
}
ZTEST(rpc,malformed_and_bounds){
 Rpc r;size_t n=fixture(16);
 zassert_equal(esp_hosted_mcu_decode_rpc(NULL,n,&r),-EMSGSIZE);
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,0,&r),-EMSGSIZE);
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,P4_RPC_PROTO_BYTES+1,&r),-EMSGSIZE);
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,n,NULL),-EINVAL);
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,n-1,&r),-EBADMSG);
 uint8_t bad[]={0xff,0xff,0xff,0xff,0xff,0xff};zassert_equal(esp_hosted_mcu_decode_rpc(bad,sizeof(bad),&r),-EBADMSG);
 /* Correct protobuf encoding but missing/wrong RPC body is not accepted. */
 Rpc invalid=Rpc_init_zero;invalid.msg_type=RpcType_Resp;invalid.msg_id=RpcId_Resp_WifiScanGetApRecords;
 pb_ostream_t out=pb_ostream_from_buffer(wire,sizeof(wire));zassert_true(pb_encode(&out,Rpc_fields,&invalid));
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,out.bytes_written,&r),-EBADMSG);
 n=fixture(16);Rpc wrong=Rpc_init_zero;pb_istream_t in=pb_istream_from_buffer(wire,n);
 zassert_true(pb_decode(&in,Rpc_fields,&wrong));wrong.msg_id=RpcId_Resp_WifiStart;
 out=pb_ostream_from_buffer(wire,sizeof(wire));zassert_true(pb_encode(&out,Rpc_fields,&wrong));clear(&wrong);
 zassert_equal(esp_hosted_mcu_decode_rpc(wire,out.bytes_written,&r),-EBADMSG);zassert_equal(stats().used,0);
 n=fixture(16); /* Unknown well-formed field remains compatible. */
 wire[n++]=0xf8;wire[n++]=0x3e;wire[n++]=1;
 zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&r));clear(&r);zassert_equal(stats().used,0);
}
ZTEST(rpc,repeated_and_fuzz){
 Rpc r;for(unsigned i=0;i<300;i++){size_t n=fixture(32);zassert_ok(esp_hosted_mcu_decode_rpc(wire,n,&r));clear(&r);zassert_equal(stats().used,0);}
 uint32_t seed=0x68f82e19;
 for(unsigned i=0;i<10000;i++){
  size_t n=1+(i%100);for(size_t j=0;j<n;j++){seed=seed*1664525u+1013904223u;wire[j]=(uint8_t)(seed>>24);}
  if(!esp_hosted_mcu_decode_rpc(wire,n,&r))clear(&r);
  zassert_equal(stats().used,0);
 }
}
K_THREAD_STACK_DEFINE(worker_stack,8192);
static struct k_thread worker_thread;
K_SEM_DEFINE(worker_done,0,1);
K_SEM_DEFINE(worker_ready,0,1);
K_SEM_DEFINE(worker_continue,0,1);
static uint8_t concurrent_wire[1600];static size_t concurrent_len;
static void worker(void *a,void *b,void *c){
 ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);
 for(unsigned i=0;i<200;i++){
  Rpc r;zassert_ok(esp_hosted_mcu_decode_rpc(concurrent_wire,concurrent_len,&r));
  k_sem_give(&worker_ready);zassert_ok(k_sem_take(&worker_continue,K_SECONDS(5)));
  zassert_equal(r.payload.resp_wifi_scan_get_ap_records.ap_records_count,32);clear(&r);
 }
 k_sem_give(&worker_done);
}
ZTEST(rpc,concurrent_lifetime){
 static mb_store files;mb_store_init(&files);
 concurrent_len=fixture(32);memcpy(concurrent_wire,wire,concurrent_len);
 k_thread_create(&worker_thread,worker_stack,K_THREAD_STACK_SIZEOF(worker_stack),worker,NULL,NULL,NULL,k_thread_priority_get(k_current_get()),0,K_NO_WAIT);
 for(unsigned i=0;i<200;i++){
  Rpc r;zassert_ok(esp_hosted_mcu_decode_rpc(concurrent_wire,concurrent_len,&r));
  uint32_t job;uint8_t value=(uint8_t)i,readback=0;
  zassert_ok(mb_store_begin(&files,"/RAM/a",6,1,i!=0,&job));
  zassert_ok(mb_store_append(&files,job,0,&value,1));zassert_ok(mb_store_finish(&files,job));
  zassert_ok(k_sem_take(&worker_ready,K_SECONDS(5)));
  zassert_true(stats().used>=2*32*sizeof(wifi_ap_record));
  zassert_equal(r.payload.resp_wifi_scan_get_ap_records.ap_records_count,32);clear(&r);
  zassert_true(mb_store_poll(&files));zassert_ok(mb_store_read(&files,"/RAM/a",6,0,&readback,1));zassert_equal(value,readback);
  k_sem_give(&worker_continue);
 }
 zassert_ok(k_sem_take(&worker_done,K_SECONDS(5)));zassert_ok(k_thread_join(&worker_thread,K_SECONDS(5)));
 zassert_equal(stats().used,0);zassert_true(stats().peak<=65536);
 printk("RPC_POOL_TEST capacity=%zu peak=%zu used=%zu failures=%zu\n",stats().capacity,stats().peak,stats().used,stats().failures);
}
static void after(void *unused){ARG_UNUSED(unused);zassert_true(p4_rpc_heap_valid());zassert_equal(stats().used,0);}
ZTEST_SUITE(rpc,NULL,NULL,NULL,after,NULL);
