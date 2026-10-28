/* SPDX-License-Identifier: MPL-2.0 */
/* HTTP chunking follows the repository's tested S3/XRP native servers. */
#include "hosted_server.h"
#include "network_backend.h"
#include <zephyr/kernel.h>
#include <zephyr/net/http/service.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/crc.h>
#include <zephyr/sys/byteorder.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
#include "http_diagnostics.h"
#define P4_ASSET_DIAG(stage, result) p4_http_diag(stage, result)
#else
#define P4_ASSET_DIAG(stage, result) ((void)0)
#endif
static uint16_t port=80;
BUILD_ASSERT(CONFIG_ZVFS_POLL_MAX >= CONFIG_HTTP_SERVER_MAX_CLIENTS + 2,
 "P4 HTTP poll budget requires stop eventfd, listener and all client slots");
HTTP_SERVICE_DEFINE(p4_http,NULL,&port,4,4,NULL,NULL,NULL);
HTTP_SERVER_REGISTER_HEADER_CAPTURE(p4_origin,"Origin");
HTTP_SERVER_REGISTER_HEADER_CAPTURE(p4_host,"Host");
static const struct flash_area *assets;
static const struct http_header headers[]={
 {"Cross-Origin-Opener-Policy","same-origin"},{"Cross-Origin-Embedder-Policy","require-corp"},
 {"X-Content-Type-Options","nosniff"},{"Cache-Control","no-cache"},{"Referrer-Policy","no-referrer"},
 {"Content-Security-Policy","default-src 'self' data: blob:; connect-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"},
 /* Dynamic responses in the pinned Zephyr do not copy common.content_encoding. */
 {"Content-Encoding","gzip"}
};
struct transfer {
 struct http_client_ctx *client;const struct p4_asset *asset;size_t offset;
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 uint32_t began_ms,returned_cycles,calls,flash_reads;
 uint64_t flash_us,yield_us,gap_us;uint32_t flash_max_us,gap_max_us;
#endif
 uint8_t buffer[2048];
};
/* HTTP/1 consumes body before the next callback; native TCP copies it. These
 * slots are CPU-only and remain owned until completion/abort. See the pinned
 * source/lifetime audit in docs/HOSTED_MEMORY_AUDIT.md before changing backends. */
#if defined(CONFIG_ESP_SPIRAM)
#define ASSET_TRANSFER_RAM __attribute__((section(".ext_ram.bss.http_assets"), aligned(16)))
#else
#define ASSET_TRANSFER_RAM
#endif
static struct transfer transfers[CONFIG_HTTP_SERVER_MAX_CLIENTS] ASSET_TRANSFER_RAM;
/* Keep flash's destination internal while cache is disabled. Serialized by
 * transfers_lock; never returned to HTTP and never dynamically allocated. */
static uint8_t flash_scratch[512] __attribute__((aligned(16)));
K_MUTEX_DEFINE(transfers_lock);
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
/* Numeric last-completed-transfer observations; no path, content or peer. */
static struct {uint32_t bytes,calls,reads,total_ms,flash_max_us,gap_max_us;
 uint64_t flash_us,yield_us,gap_us;bool aborted;} last_transfer;
static uint32_t elapsed_us(uint32_t began)
{return (uint32_t)k_cyc_to_us_floor64((uint32_t)(k_cycle_get_32()-began));}
void p4_asset_timing_json(char *out,size_t n)
{
 k_mutex_lock(&transfers_lock,K_FOREVER);
 snprintf(out,n,"{\"bytes\":%u,\"calls\":%u,\"reads\":%u,\"total_ms\":%u,\"flash_us\":%llu,\"yield_us\":%llu,\"gap_us\":%llu,\"flash_max_us\":%u,\"gap_max_us\":%u,\"aborted\":%s}",
 last_transfer.bytes,last_transfer.calls,last_transfer.reads,last_transfer.total_ms,
 (unsigned long long)last_transfer.flash_us,(unsigned long long)last_transfer.yield_us,
 (unsigned long long)last_transfer.gap_us,last_transfer.flash_max_us,last_transfer.gap_max_us,
 last_transfer.aborted?"true":"false");
 k_mutex_unlock(&transfers_lock);
}
static void finish_timing(const struct transfer *s,bool aborted)
{
 last_transfer.bytes=s->offset;last_transfer.calls=s->calls;last_transfer.reads=s->flash_reads;
 last_transfer.total_ms=k_uptime_get_32()-s->began_ms;last_transfer.flash_us=s->flash_us;
 last_transfer.yield_us=s->yield_us;last_transfer.gap_us=s->gap_us;
 last_transfer.flash_max_us=s->flash_max_us;last_transfer.gap_max_us=s->gap_max_us;
 last_transfer.aborted=aborted;
}
#endif
int p4_assets_check(void)
{
 int err=flash_area_open(FIXED_PARTITION_ID(p4_assets),&assets);if(err)return err;
 uint8_t header[64],buffer[4096];err=flash_area_read(assets,0,header,sizeof(header));
 if(err||memcmp(header,p4_asset_header,sizeof(header))||p4_asset_total>assets->fa_size)return -EBADMSG;
 uint32_t crc=0;
 for(size_t offset=64;offset<p4_asset_total;offset+=sizeof(buffer)){
  size_t n=MIN(sizeof(buffer),p4_asset_total-offset);err=flash_area_read(assets,offset,buffer,n);if(err)return err;
  crc=crc32_ieee_update(crc,buffer,n);k_sleep(K_MSEC(1));
 }
 return crc==sys_get_le32(header+20)?0:-EBADMSG;
}
int p4_asset_handler(struct http_client_ctx *client,enum http_transaction_status status,
 const struct http_request_ctx *request,struct http_response_ctx *response,void *user)
{
 (void)request;const struct p4_asset *asset=user;struct transfer *state=NULL,*empty=NULL;
 if(!client || !asset)return -EINVAL;
 k_mutex_lock(&transfers_lock,K_FOREVER);
 for(unsigned i=0;i<ARRAY_SIZE(transfers);i++){if(transfers[i].client==client&&transfers[i].asset==asset)state=&transfers[i];if(!transfers[i].client&&!empty)empty=&transfers[i];}
 if(status==HTTP_SERVER_TRANSACTION_COMPLETE||status==HTTP_SERVER_TRANSACTION_ABORTED){if(state){
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 finish_timing(state,status==HTTP_SERVER_TRANSACTION_ABORTED);
#endif
 memset(state,0,sizeof(*state));}k_mutex_unlock(&transfers_lock);return 0;}
 if(status!=HTTP_SERVER_REQUEST_DATA_FINAL){k_mutex_unlock(&transfers_lock);return 0;}
 if(!response){k_mutex_unlock(&transfers_lock);return -EINVAL;}
 if(!assets || asset->offset>p4_asset_total || asset->size>p4_asset_total-asset->offset ||
    (state && state->offset>asset->size)){if(state)memset(state,0,sizeof(*state));P4_ASSET_DIAG(6,-EBADMSG);k_mutex_unlock(&transfers_lock);return -EBADMSG;}
 if(!state){state=empty;if(!state){P4_ASSET_DIAG(4,-ENOMEM);k_mutex_unlock(&transfers_lock);return -ENOMEM;}state->client=client;state->asset=asset;}
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 if(!state->calls)state->began_ms=k_uptime_get_32();
 else{uint32_t gap=elapsed_us(state->returned_cycles);state->gap_us+=gap;
  if(gap>state->gap_max_us)state->gap_max_us=gap;}
 state->calls++;
 uint32_t flash_began=k_cycle_get_32();
#endif
 size_t n=MIN(asset->size-state->offset,sizeof(state->buffer));
 for(size_t copied=0;copied<n;){
  size_t part=MIN(n-copied,sizeof(flash_scratch));
  int err=flash_area_read(assets,asset->offset+state->offset+copied,flash_scratch,part);
  if(err){P4_ASSET_DIAG(5,err);memset(state,0,sizeof(*state));k_mutex_unlock(&transfers_lock);return err;}
  /* flash_area_read has restored cache access before this CPU-only copy. */
  memcpy(state->buffer+copied,flash_scratch,part);copied+=part;
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
  state->flash_reads++;
#endif
 }
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 uint32_t flash_elapsed=elapsed_us(flash_began);state->flash_us+=flash_elapsed;
 if(flash_elapsed>state->flash_max_us)state->flash_max_us=flash_elapsed;
#endif
 response->body=state->buffer;response->body_len=n;
 if(!state->offset){response->headers=headers;response->header_count=ARRAY_SIZE(headers)-(asset->gzip?0:1);}
 state->offset+=n;response->final_chunk=state->offset==asset->size;k_mutex_unlock(&transfers_lock);
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 uint32_t yield_began=k_cycle_get_32();
#endif
 k_sleep(K_MSEC(1));
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 k_mutex_lock(&transfers_lock,K_FOREVER);state->yield_us+=elapsed_us(yield_began);
 state->returned_cycles=k_cycle_get_32();k_mutex_unlock(&transfers_lock);
#endif
 return 0;
}
bool p4_same_origin(const struct http_request_ctx *request)
{
 bool host=false,origin=false;
 char ip[32],host_port[40],url[48],url_port[52];p4_network_address(ip,sizeof(ip));if(!ip[0])return false;
 snprintf(host_port,sizeof(host_port),"%s:80",ip);snprintf(url,sizeof(url),"http://%s",ip);snprintf(url_port,sizeof(url_port),"http://%s:80",ip);
 for(size_t i=0;i<request->header_count;i++){
  const char *name=request->headers[i].name,*value=request->headers[i].value;
  if(!strcasecmp(name,"Host") && (!strcmp(value,ip)||!strcmp(value,host_port)))host=true;
  if(!strcasecmp(name,"Origin") && (!strcmp(value,url)||!strcmp(value,url_port)))origin=true;
 }
 return host&&origin;
}
static uint8_t ws_buffer[512];
static struct http_resource_detail_websocket websocket={.common={.type=HTTP_RESOURCE_TYPE_WEBSOCKET,.bitmask_of_supported_http_methods=BIT(HTTP_GET)},.cb=p4_ws_setup,.data_buffer=ws_buffer,.data_buffer_len=sizeof(ws_buffer)};
HTTP_RESOURCE_DEFINE(p4_vm_websocket,p4_http,"/ws/vm",&websocket);
static int status_handler(struct http_client_ctx *client,enum http_transaction_status status,const struct http_request_ctx *request,struct http_response_ctx *response,void *user)
{
 (void)client;(void)request;(void)user;if(status!=HTTP_SERVER_REQUEST_DATA_FINAL)return 0;
 static char body[512];p4_network_status(body,sizeof(body));response->body=(uint8_t *)body;response->body_len=strlen(body);response->headers=headers;response->header_count=ARRAY_SIZE(headers)-1;response->final_chunk=true;return 0;
}
static struct http_resource_detail_dynamic status_api={.common={.type=HTTP_RESOURCE_TYPE_DYNAMIC,.bitmask_of_supported_http_methods=BIT(HTTP_GET),.content_type="application/json"},.cb=status_handler};
HTTP_RESOURCE_DEFINE(p4_status,p4_http,"/api/status",&status_api);
int p4_server_start(void){return http_server_start();}
