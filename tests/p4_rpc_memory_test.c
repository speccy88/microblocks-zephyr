/* SPDX-License-Identifier: MIT */
/* Synthetic scan response; no names, radio access or credentials. The allocator
 * always moves realloc to expose old+new payload demand. Not a Zephyr heap sim. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <pb_decode.h>
#include "esp_hosted_mcu_rpc.pb.h"
static size_t live,peak,limit;
void *audit_realloc(void *old,size_t n){
 /* Only the AP-record array is populated in these fixtures. Account its
  * observed RV32 size separately from the host's pointer-bearing ABI. */
 assert(n%sizeof(wifi_ap_record)==0);
 size_t charged=(n/sizeof(wifi_ap_record))*128;
 size_t was=old?((size_t*)old)[-2]:0;
 if(charged>limit-live)return NULL;
 size_t *p=malloc(2*sizeof(size_t)+n);assert(p);p[0]=n;p[1]=charged;
 live+=charged;if(live>peak)peak=live;
 if(old){memcpy(p+2,old,was<n?was:n);live-=((size_t*)old)[-1];free((size_t*)old-2);}
 return p+2;
}
void audit_free(void *p){if(p){live-=((size_t*)p)[-1];free((size_t*)p-2);}}
static void run(unsigned count,size_t budget,bool expected,bool comma){
 assert(!live);limit=budget;peak=0;
 uint8_t wire[512];assert(count*2<=sizeof(wire));
 for(unsigned i=0;i<count;i++){wire[2*i]=0x1a;wire[2*i+1]=0;} /* repeated empty AP submessages */
 Rpc_Resp_WifiScanGetApRecords response=Rpc_Resp_WifiScanGetApRecords_init_zero;
 pb_istream_t stream=pb_istream_from_buffer(wire,count*2);
 bool ok=pb_decode(&stream,Rpc_Resp_WifiScanGetApRecords_fields,&response);
 assert(ok==expected);if(ok)assert(response.ap_records_count==count);
 else assert(!live); /* Real driver returns directly after pb_decode failure. */
 pb_release(Rpc_Resp_WifiScanGetApRecords_fields,&response);assert(!live);
 printf("%s{\"records\":%u,\"wire_bytes\":%u,\"payload_budget\":%zu,\"peak_payload_bytes\":%zu,\"decoded\":%s,\"leaked_bytes\":0}",comma?",":"",count,count*2,budget,peak,ok?"true":"false");
}
int main(void){
 printf("{\"rv32_record_bytes\":128,\"host_record_bytes\":%zu,\"allocator\":\"synthetic always-move realloc; RV32 record payload accounting, overhead excluded\",\"cases\":[",sizeof(wifi_ap_record));
 run(16,1760,false,false);run(16,8192,true,true);run(32,8192,true,true);
 run(64,9488,false,true);run(128,9488,false,true);run(16,9488,true,true);
 puts("],\"physical_tested\":false}");
}
