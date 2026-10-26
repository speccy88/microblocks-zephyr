/* SPDX-License-Identifier: MIT */
#include "hosted_assets_fakes.h"
#include <stdio.h>
#include <string.h>
#include <stdatomic.h>
#include "../boards/waveshare_esp32p4_wifi6/zephyr/src/hosted_server.c"

const unsigned char p4_asset_header[64]={0};
const unsigned p4_asset_total=16384;
static struct flash_area area={16384};
static unsigned calls,fail_call,max_read;
static unsigned checks;
#define CHECK(x) do{assert(x);checks++;}while(0)
static uint8_t byte_at(size_t x){return (uint8_t)((x*37u)^(x>>8));}
int flash_area_open(int id,const struct flash_area **a){(void)id;*a=&area;return 0;}
int flash_area_read(const struct flash_area *a,size_t offset,void *dest,size_t n){
 assert(a==&area && offset<=a->fa_size && n<=a->fa_size-offset);
 /* Every handler read targets the internal scratch, never a returned body. */
 assert(dest==flash_scratch && n<=sizeof(flash_scratch));
 calls++;if(n>max_read)max_read=n;if(fail_call==calls)return -EIO;
 for(size_t i=0;i<n;i++)((uint8_t*)dest)[i]=byte_at(offset+i);
 return 0;
}
uint32_t crc32_ieee_update(uint32_t c,const void *p,size_t n){(void)p;(void)n;return c;}
void p4_network_address(char *out,size_t n){snprintf(out,n,"192.0.2.1");}
void p4_network_status(char *out,size_t n){snprintf(out,n,"{}");}
int p4_ws_setup(int fd,struct http_request_ctx *req,void *u){(void)fd;(void)req;(void)u;return 0;}
static struct http_client_ctx clients[5];
static int next(unsigned c,struct p4_asset *a,struct http_response_ctx *r){memset(r,0,sizeof(*r));return p4_asset_handler(&clients[c],HTTP_SERVER_REQUEST_DATA_FINAL,NULL,r,a);}
static void done(unsigned c,struct p4_asset *a,bool abort){assert(!p4_asset_handler(&clients[c],abort?HTTP_SERVER_TRANSACTION_ABORTED:HTTP_SERVER_TRANSACTION_COMPLETE,NULL,NULL,a));}
static void verify(const struct http_response_ctx *r,size_t offset,size_t n){assert(r->body_len==n);assert(r->body!=flash_scratch);for(size_t i=0;i<n;i++)assert(r->body[i]==byte_at(offset+i));}
static void clean(void){memset(transfers,0,sizeof(transfers));calls=fail_call=max_read=0;assets=&area;}
static void *worker(void *arg){
 unsigned c=(unsigned)(uintptr_t)arg;struct p4_asset a={64+c*701,7001,false};
 for(unsigned round=0;round<100;round++){
  size_t pos=0;struct http_response_ctx r;
  do{assert(!next(c,&a,&r));verify(&r,a.offset+pos,MIN(a.size-pos,2048));pos+=r.body_len;}while(!r.final_chunk);
  assert(pos==a.size);done(c,&a,round%2);
 }
 return NULL;
}
int main(void){
 struct http_response_ctx r;struct p4_asset a={64,0,false};clean();
 const size_t sizes[]={0,1,511,512,513,2047,2048,2049,4096,7001};
 for(unsigned i=0;i<ARRAY_SIZE(sizes);i++){
  a.size=sizes[i];size_t pos=0;bool first=true;
  do{CHECK(!next(0,&a,&r));verify(&r,a.offset+pos,MIN(a.size-pos,2048));CHECK(r.header_count==(first?6u:0u));pos+=r.body_len;CHECK(r.final_chunk==(pos==a.size));first=false;}while(!r.final_chunk);
  CHECK(pos==a.size);done(0,&a,false);
 }
 CHECK(max_read==512);
 clean();a.size=4097;a.gzip=true;
 struct http_response_ctx held[4];
 for(unsigned c=0;c<4;c++){CHECK(!next(c,&a,&held[c]));CHECK(held[c].header_count==7);}
 CHECK(next(4,&a,&r)==-ENOMEM);
 for(unsigned c=0;c<4;c++)verify(&held[c],64,2048);
 done(1,&a,true);CHECK(!next(4,&a,&r));verify(&r,64,2048);
 for(unsigned c=0;c<4;c++)if(c!=1){verify(&held[c],64,2048);done(c,&a,false);}
 done(4,&a,true);CHECK(!next(1,&a,&r));verify(&r,64,2048);done(1,&a,false);
 /* Fail inside the chunk: no partial body escapes, slot immediately reusable. */
 for(unsigned failed=1;failed<=4;failed++){
  clean();fail_call=failed;CHECK(next(0,&a,&r)==-EIO);CHECK(r.body==NULL && r.body_len==0);
  fail_call=0;CHECK(!next(0,&a,&r));verify(&r,64,2048);done(0,&a,false);
 }
 clean();assets=NULL;CHECK(next(0,&a,&r)==-EBADMSG);assets=&area;
 struct p4_asset bad[]={{16385,0,false},{16384,1,false},{UINT32_MAX,2,false},{64,UINT32_MAX,false}};
 for(unsigned i=0;i<ARRAY_SIZE(bad);i++)CHECK(next(0,&bad[i],&r)==-EBADMSG);
 CHECK(calls==0);CHECK(p4_asset_handler(NULL,HTTP_SERVER_REQUEST_DATA_FINAL,NULL,&r,&a)==-EINVAL);
 CHECK(p4_asset_handler(&clients[0],HTTP_SERVER_REQUEST_DATA_FINAL,NULL,&r,NULL)==-EINVAL);
 CHECK(p4_asset_handler(&clients[0],HTTP_SERVER_REQUEST_DATA_FINAL,NULL,NULL,&a)==-EINVAL);
 CHECK(!p4_asset_handler(&clients[0],HTTP_SERVER_REQUEST_DATA_MORE,NULL,&r,&a));CHECK(calls==0);
 CHECK(!next(0,&a,&r));a.size=1;CHECK(next(0,&a,&r)==-EBADMSG);a.size=4097;CHECK(!next(0,&a,&r));done(0,&a,true);
 /* Different assets on a reused client must start at byte zero after cleanup. */
 struct p4_asset b={123,2049,false};CHECK(!next(0,&b,&r));verify(&r,123,2048);done(0,&b,true);
 clean();pthread_t workers[4];
 for(uintptr_t i=0;i<4;i++)assert(!pthread_create(&workers[i],NULL,worker,(void*)i));
 for(unsigned i=0;i<4;i++)assert(!pthread_join(workers[i],NULL));
 CHECK(max_read==512);for(unsigned i=0;i<4;i++)CHECK(!transfers[i].client);
 printf("{\"checks\":%u,\"concurrent_clients\":4,\"concurrent_transfers\":400,\"max_flash_read\":%u,\"physical_tested\":false}\n",checks,max_read);
}
