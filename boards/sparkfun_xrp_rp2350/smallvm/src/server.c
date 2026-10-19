/* SPDX-License-Identifier: MIT */
#include "server.h"
#include "provisioning.h"
#include <zephyr/net/http/service.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_heap.h>
#include <zephyr/sys/atomic.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>

static uint16_t port = 80;
HTTP_SERVICE_DEFINE(mb_http, NULL, &port, 4, 4, NULL, NULL, NULL);
HTTP_SERVER_REGISTER_HEADER_CAPTURE(origin_header, "Origin");
HTTP_SERVER_REGISTER_HEADER_CAPTURE(host_header, "Host");
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

#define ASSET_CHUNK_BYTES 2048u
struct asset_transfer {
    struct http_client_ctx *client;
    const struct mb_asset *asset;
    size_t offset;
};
static struct asset_transfer transfers[CONFIG_HTTP_SERVER_MAX_CLIENTS];
K_MUTEX_DEFINE(asset_transfers_lock);
static atomic_t asset_completed, asset_aborted;

int mb_asset_handler(struct http_client_ctx *client, enum http_transaction_status status,
                     const struct http_request_ctx *request,
                     struct http_response_ctx *response, void *user)
{
    ARG_UNUSED(request);
    const struct mb_asset *asset = user;
    struct asset_transfer *state = NULL, *empty = NULL;
    k_mutex_lock(&asset_transfers_lock, K_FOREVER);
    for (size_t i = 0; i < ARRAY_SIZE(transfers); ++i) {
        if (transfers[i].client == client && transfers[i].asset == asset) state = &transfers[i];
        if (!transfers[i].client && !empty) empty = &transfers[i];
    }
    if (status == HTTP_SERVER_TRANSACTION_COMPLETE || status == HTTP_SERVER_TRANSACTION_ABORTED) {
        if (state) {
            if (status == HTTP_SERVER_TRANSACTION_COMPLETE) atomic_inc(&asset_completed);
            else atomic_inc(&asset_aborted);
            memset(state, 0, sizeof(*state));
        }
        k_mutex_unlock(&asset_transfers_lock);
        return 0;
    }
    if (status != HTTP_SERVER_REQUEST_DATA_FINAL) {
        k_mutex_unlock(&asset_transfers_lock);
        return 0;
    }
    if (!state) {
        state = empty;
        if (!state) { k_mutex_unlock(&asset_transfers_lock); return -ENOMEM; }
        *state = (struct asset_transfer){.client = client, .asset = asset};
    }
    bool first = state->offset == 0;
    size_t count = MIN(asset->size - state->offset, ASSET_CHUNK_BYTES);
    response->body = asset->data + state->offset;
    response->body_len = count;
    if (first) {
        response->headers = asset->gzip ? gzip_headers : asset_headers;
        response->header_count = asset->gzip ? ARRAY_SIZE(gzip_headers) : ARRAY_SIZE(asset_headers);
    }
    state->offset += count;
    response->final_chunk = state->offset == asset->size;
    k_mutex_unlock(&asset_transfers_lock);
    /* A bulk body must not monopolize network servicing. Zephyr requests the
     * next response chunk after sending this one and refreshes its timer. */
    if (!first) k_sleep(K_MSEC(1));
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

static int status_handler(struct http_client_ctx *c,enum http_transaction_status st,
    const struct http_request_ctx *req,struct http_response_ctx *res,void *user)
{
    ARG_UNUSED(c);ARG_UNUSED(req);ARG_UNUSED(user);
    if(st!=HTTP_SERVER_REQUEST_DATA_FINAL)return 0;
    static char json[384];xrp_network_status(json,sizeof(json));
    res->body=(const uint8_t *)json;res->body_len=strlen(json);res->final_chunk=true;return 0;
}
static struct http_resource_detail_dynamic status_detail={
    .common={.type=HTTP_RESOURCE_TYPE_DYNAMIC,.bitmask_of_supported_http_methods=BIT(HTTP_GET),.content_type="application/json"},
    .cb=status_handler,
};
HTTP_RESOURCE_DEFINE(status_api,mb_http,"/api/status",&status_detail);
bool mb_same_origin(const struct http_request_ctx *req)
{
    char expected[64];snprintf(expected,sizeof(expected),"http://%s",mb_network_ip());
    bool host=false,origin=false;
    for(size_t i=0;i<req->header_count;++i){
        if(!strcasecmp(req->headers[i].name,"Host") && !strcmp(req->headers[i].value,mb_network_ip()))host=true;
        if(!strcasecmp(req->headers[i].name,"Origin") && !strcmp(req->headers[i].value,expected))origin=true;
    }
    return host && origin;
}
