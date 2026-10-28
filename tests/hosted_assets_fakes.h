/* SPDX-License-Identifier: MIT */
/* Host-only OS/flash interfaces. The actual application handler is compiled. */
#ifndef HOSTED_ASSETS_FAKES_H
#define HOSTED_ASSETS_FAKES_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <errno.h>
#include <pthread.h>
#include <assert.h>
#include <stdatomic.h>
#define CONFIG_HTTP_SERVER_MAX_CLIENTS 4
#ifndef CONFIG_ZVFS_POLL_MAX
#define CONFIG_ZVFS_POLL_MAX 8
#endif
#define BUILD_ASSERT(condition,message) _Static_assert(condition,message)
#define MIN(a,b) ((a)<(b)?(a):(b))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BIT(a) (1u<<(a))
#define K_FOREVER 0
#define K_MSEC(a) (a)
#define K_MUTEX_DEFINE(a) static pthread_mutex_t a=PTHREAD_MUTEX_INITIALIZER
static inline int k_mutex_lock(pthread_mutex_t *m,int t){(void)t;return pthread_mutex_lock(m);}
static inline int k_mutex_unlock(pthread_mutex_t *m){return pthread_mutex_unlock(m);}
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
static atomic_uint fake_cycles;
static inline uint32_t k_cycle_get_32(void){return atomic_fetch_add(&fake_cycles,1);}
static inline uint64_t k_cyc_to_us_floor64(uint64_t cycles){return cycles;}
static inline uint32_t k_uptime_get_32(void){return atomic_load(&fake_cycles)/1000;}
static inline void k_sleep(int t){atomic_fetch_add(&fake_cycles,t*1000);}
#else
static inline void k_sleep(int t){(void)t;}
#endif
struct http_client_ctx {unsigned id;};
struct http_header {const char *name,*value;};
struct http_request_ctx {size_t header_count;const struct http_header *headers;};
struct http_response_ctx {const uint8_t *body;size_t body_len;const struct http_header *headers;size_t header_count;bool final_chunk;};
enum http_transaction_status {HTTP_SERVER_REQUEST_DATA_MORE,HTTP_SERVER_REQUEST_DATA_FINAL,HTTP_SERVER_TRANSACTION_COMPLETE,HTTP_SERVER_TRANSACTION_ABORTED};
struct http_resource_detail {int type;unsigned bitmask_of_supported_http_methods;const char *content_type;};
struct http_resource_detail_dynamic {struct http_resource_detail common;int (*cb)(struct http_client_ctx*,enum http_transaction_status,const struct http_request_ctx*,struct http_response_ctx*,void*);};
struct http_resource_detail_websocket {struct http_resource_detail common;int (*cb)(int,struct http_request_ctx*,void*);uint8_t *data_buffer;size_t data_buffer_len;};
#define HTTP_GET 0
#define HTTP_RESOURCE_TYPE_WEBSOCKET 1
#define HTTP_RESOURCE_TYPE_DYNAMIC 2
#define HTTP_SERVICE_DEFINE(name,host,port,...) static const void *name __attribute__((used))=port
#define HTTP_SERVER_REGISTER_HEADER_CAPTURE(name,value)
#define HTTP_RESOURCE_DEFINE(name,service,path,detail) static const void *name __attribute__((used))=detail
static inline int http_server_start(void){return 0;}
struct flash_area {size_t fa_size;};
#define FIXED_PARTITION_ID(a) 0
int flash_area_open(int id,const struct flash_area **area);
int flash_area_read(const struct flash_area *area,size_t offset,void *dest,size_t n);
uint32_t crc32_ieee_update(uint32_t crc,const void *data,size_t n);
static inline uint32_t sys_get_le32(const void *p){const uint8_t *b=p;return b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);}
#endif
