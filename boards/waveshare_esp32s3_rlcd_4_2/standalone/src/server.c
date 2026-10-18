/* SPDX-License-Identifier: MIT */
#include "server.h"
#include "device_secrets.h"
#include <zephyr/net/http/service.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_heap.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>

static uint16_t port = 80;
HTTP_SERVICE_DEFINE(mb_http, NULL, &port, 12, 12, NULL, NULL, NULL);
HTTP_SERVER_REGISTER_HEADER_CAPTURE(origin_header, "Origin");
HTTP_SERVER_REGISTER_HEADER_CAPTURE(pair_header, "X-MicroBlocks-Pair");
static char content_policy[384];

static const struct http_header asset_headers[] = {
    {"Cross-Origin-Opener-Policy", "same-origin"},
    {"Cross-Origin-Embedder-Policy", "require-corp"},
    {"X-Content-Type-Options", "nosniff"},
    {"Cache-Control", "no-cache"},
    {"Referrer-Policy", "no-referrer"},
    {"Content-Security-Policy", content_policy},
};
static const struct http_header gzip_headers[] = {
    {"Content-Encoding", "gzip"},
    {"Cross-Origin-Opener-Policy", "same-origin"},
    {"Cross-Origin-Embedder-Policy", "require-corp"},
    {"X-Content-Type-Options", "nosniff"},
    {"Cache-Control", "no-cache"},
    {"Referrer-Policy", "no-referrer"},
    {"Content-Security-Policy", content_policy},
};

int mb_asset_handler(struct http_client_ctx *client, enum http_transaction_status status,
                     const struct http_request_ctx *request,
                     struct http_response_ctx *response, void *user)
{
    ARG_UNUSED(client); ARG_UNUSED(request);
    if (status != HTTP_SERVER_REQUEST_DATA_FINAL) return 0;
    const struct mb_asset *asset = user;
    response->body = asset->data;
    response->body_len = asset->size;
    response->headers = asset->gzip ? gzip_headers : asset_headers;
    response->header_count = asset->gzip ? ARRAY_SIZE(gzip_headers) : ARRAY_SIZE(asset_headers);
    response->final_chunk = true;
    return 0;
}

static uint8_t ws_buffer[512];
static struct http_resource_detail_websocket vm_ws = {
    .common = {.type=HTTP_RESOURCE_TYPE_WEBSOCKET, .bitmask_of_supported_http_methods=BIT(HTTP_GET)},
    .cb=mb_ws_setup, .data_buffer=ws_buffer, .data_buffer_len=sizeof(ws_buffer),
};
HTTP_RESOURCE_DEFINE(vm_websocket, mb_http, "/ws/vm", &vm_ws);

int mb_server_start(void) {
    snprintf(content_policy, sizeof(content_policy),
        "default-src 'self' data: blob:; connect-src 'self' ws://%s; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
        mb_network_ip());
    return http_server_start();
}

static char wifi_body[128];
static size_t wifi_size;
static bool wifi_allowed;
static int wifi_handler(struct http_client_ctx *client, enum http_transaction_status status,
    const struct http_request_ctx *request, struct http_response_ctx *response, void *user)
{
    ARG_UNUSED(client); ARG_UNUSED(user);
    if (status == HTTP_SERVER_TRANSACTION_COMPLETE || status == HTTP_SERVER_TRANSACTION_ABORTED) {
        memset(wifi_body, 0, sizeof(wifi_body)); wifi_size = 0; wifi_allowed = false; return 0;
    }
    if (request->headers_status != HTTP_HEADER_STATUS_NONE) {
        wifi_allowed = false;
        if (mb_same_origin(request)) {
            for (size_t i = 0; i < request->header_count; ++i)
                if (!strcasecmp(request->headers[i].name, "X-MicroBlocks-Pair") &&
                    !strcmp(request->headers[i].value, MB_DEVICE_PAIR)) wifi_allowed = true;
        }
    }
    const char *reply = "{\"saved\":false}";
    if (!wifi_allowed) response->status = HTTP_403_FORBIDDEN;
    else if (wifi_size + request->data_len >= sizeof(wifi_body)) response->status = HTTP_413_PAYLOAD_TOO_LARGE;
    else {
        memcpy(wifi_body + wifi_size, request->data, request->data_len); wifi_size += request->data_len;
        if (status != HTTP_SERVER_REQUEST_DATA_FINAL) return 0;
        wifi_body[wifi_size] = 0;
        char *newline = strchr(wifi_body, '\n');
        if (!newline) response->status = HTTP_400_BAD_REQUEST;
        else {
            *newline++ = 0;
            int err = mb_network_save(wifi_body, newline);
            response->status = err ? HTTP_400_BAD_REQUEST : HTTP_200_OK;
            if (!err) reply = "{\"saved\":true,\"restarting\":true}";
        }
    }
    response->body = (const uint8_t *)reply; response->body_len = strlen(reply);
    response->headers = asset_headers; response->header_count = ARRAY_SIZE(asset_headers);
    response->final_chunk = true;
    return 0;
}
static struct http_resource_detail_dynamic wifi_setup = {
    .common={.type=HTTP_RESOURCE_TYPE_DYNAMIC,.bitmask_of_supported_http_methods=BIT(HTTP_POST),.content_type="application/json"},
    .cb=wifi_handler,
};
HTTP_RESOURCE_DEFINE(wifi_api, mb_http, "/api/wifi", &wifi_setup);

static int status_handler(struct http_client_ctx *client, enum http_transaction_status status,
    const struct http_request_ctx *request, struct http_response_ctx *response, void *user)
{
    ARG_UNUSED(client); ARG_UNUSED(request); ARG_UNUSED(user);
    if (status != HTTP_SERVER_REQUEST_DATA_FINAL) return 0;
    static char json[384];
    struct mb_transport_diagnostics ws;
    mb_transport_diagnostics_get(&ws);
    snprintf(json, sizeof(json), "{\"board\":\"Waveshare ESP32-S3-RLCD-4.2\",\"vm\":417,\"ide\":\"2.5.8\",\"saved_generation\":%u,"
        "\"websocket\":{\"sessions\":%u,\"auth_failures\":%u,\"rx_errors\":%u,\"tx_errors\":%u,\"queue_timeouts\":%u,\"last_error\":%d}}",
        mb_store_generation(), ws.sessions, ws.auth_failures, ws.rx_errors, ws.tx_errors, ws.queue_timeouts, ws.last_error);
    response->body=(const uint8_t *)json;response->body_len=strlen(json);response->final_chunk=true;
    return 0;
}
static struct http_resource_detail_dynamic status_detail = {
    .common={.type=HTTP_RESOURCE_TYPE_DYNAMIC,.bitmask_of_supported_http_methods=BIT(HTTP_GET),.content_type="application/json"},
    .cb=status_handler,
};
HTTP_RESOURCE_DEFINE(status_api, mb_http, "/api/status", &status_detail);

/* These symbols are supplied by the pinned Zephyr kernel/common libc.
 * The ESP-IDF heap_caps_get_free_size port is a stub, so do not use it.
 * Take the kernel heap lock; malloc_runtime_stats_get locks its own arena.
 */
extern struct k_heap _system_heap;
extern int malloc_runtime_stats_get(struct sys_memory_stats *stats);

static int memory_handler(struct http_client_ctx *client, enum http_transaction_status status,
    const struct http_request_ctx *request, struct http_response_ctx *response, void *user)
{
    ARG_UNUSED(client); ARG_UNUSED(request); ARG_UNUSED(user);
    if (status != HTTP_SERVER_REQUEST_DATA_FINAL) return 0;
    struct sys_memory_stats libc_stats = {0}, kernel_stats = {0};
    int libc_result = malloc_runtime_stats_get(&libc_stats);
    k_spinlock_key_t key = k_spin_lock(&_system_heap.lock);
    int kernel_result = sys_heap_runtime_stats_get(&_system_heap.heap, &kernel_stats);
    k_spin_unlock(&_system_heap.lock, key);
    static char json[512];
    snprintf(json, sizeof(json),
        "{\"libc_malloc\":{\"result\":%d,\"free_bytes\":%zu,\"allocated_bytes\":%zu,\"peak_allocated_bytes\":%zu},"
        "\"kernel_heap\":{\"result\":%d,\"free_bytes\":%zu,\"allocated_bytes\":%zu,\"peak_allocated_bytes\":%zu},"
        "\"uptime_ms\":%u,"
        "\"scope\":\"allocator pools; excludes static arrays, stacks and unassigned physical RAM\"}",
        libc_result, libc_stats.free_bytes, libc_stats.allocated_bytes, libc_stats.max_allocated_bytes,
        kernel_result, kernel_stats.free_bytes, kernel_stats.allocated_bytes, kernel_stats.max_allocated_bytes,
        k_uptime_get_32());
    response->body = (const uint8_t *)json; response->body_len = strlen(json);
    response->headers = asset_headers; response->header_count = ARRAY_SIZE(asset_headers);
    response->final_chunk = true;
    return 0;
}
static struct http_resource_detail_dynamic memory_detail = {
    .common={.type=HTTP_RESOURCE_TYPE_DYNAMIC,.bitmask_of_supported_http_methods=BIT(HTTP_GET),.content_type="application/json"},
    .cb=memory_handler,
};
HTTP_RESOURCE_DEFINE(memory_api, mb_http, "/api/memory", &memory_detail);
