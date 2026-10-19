/* SPDX-License-Identifier: MIT */
#pragma once
#include <zephyr/net/http/server.h>
struct mb_asset { const unsigned char *data; size_t size; bool gzip; };
int mb_asset_handler(struct http_client_ctx *, enum http_transaction_status,
                     const struct http_request_ctx *, struct http_response_ctx *, void *);
int mb_server_start(void);
int mb_network_start(void);
const char *mb_network_ip(void);
int mb_ws_setup(int, struct http_request_ctx *, void *);
int mb_transport_recv(unsigned char *, int);
int mb_transport_send(unsigned char *, int, int);
void mb_transport_poll(void);
int mb_store_load(void);
void mb_store_poll(void);
unsigned mb_store_generation(void);
int mb_network_save(const char *, const char *);
bool mb_same_origin(const struct http_request_ctx *);
struct mb_transport_diagnostics {
    unsigned sessions, rx_errors, tx_errors, queue_timeouts;
    int last_error;
};
void mb_transport_diagnostics_get(struct mb_transport_diagnostics *out);
