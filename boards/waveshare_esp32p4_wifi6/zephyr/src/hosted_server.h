/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/net/http/server.h>
struct p4_asset {uint32_t offset,size;bool gzip;};
extern const unsigned char p4_asset_header[64];
extern const unsigned p4_asset_total;
int p4_asset_handler(struct http_client_ctx *,enum http_transaction_status,
 const struct http_request_ctx *,struct http_response_ctx *,void *);
int p4_assets_check(void);
int p4_server_start(void);
bool p4_same_origin(const struct http_request_ctx *);
int p4_ws_setup(int,struct http_request_ctx *,void *);
void p4_transport_init(void);
bool p4_transport_ready(void);
void p4_transport_poll(void);
int p4_transport_recv(uint8_t *,int);
int p4_transport_send(uint8_t *,int,int);
bool p4_transport_is_usb(void);
const char *p4_transport_owner(void);
