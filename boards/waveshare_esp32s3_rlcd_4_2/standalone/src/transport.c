/* SPDX-License-Identifier: MPL-2.0 */
#include "server.h"
#include "device_secrets.h"
#include <zephyr/kernel.h>
#include <zephyr/net/websocket.h>
#include <zephyr/sys/ring_buffer.h>
#include <zephyr/sys/atomic.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>

RING_BUF_DECLARE(rx_queue, 8192);
RING_BUF_DECLARE(tx_queue, 8192);
K_MUTEX_DEFINE(queues);
K_SEM_DEFINE(client_ready, 0, 1);
K_SEM_DEFINE(reset_done, 0, 1);
static atomic_t busy;
static atomic_t authenticated;
static atomic_t reset_pending;
static int client_socket = -1;
extern void smallvmResetTransport(void);

void mb_transport_poll(void)
{
    if (atomic_cas(&reset_pending, 1, 0)) {
        k_mutex_lock(&queues, K_FOREVER);
        ring_buf_reset(&rx_queue);
        ring_buf_reset(&tx_queue);
        smallvmResetTransport();
        k_mutex_unlock(&queues);
        k_sem_give(&reset_done);
    }
}

int mb_transport_recv(unsigned char *data, int count)
{
    k_mutex_lock(&queues, K_FOREVER);
    int n = ring_buf_get(&rx_queue, data, MAX(count, 0));
    k_mutex_unlock(&queues);
    return n;
}

int mb_transport_send(unsigned char *data, int start, int end)
{
    if (!atomic_get(&authenticated)) return end - start;
    k_mutex_lock(&queues, K_FOREVER);
    int n = ring_buf_put(&tx_queue, data + start, end - start);
    k_mutex_unlock(&queues);
    return n;
}

static void websocket_worker(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);
    uint8_t input[1024], output[1024];
    for (;;) {
        k_sem_take(&client_ready, K_FOREVER);
        int fd = client_socket;
        uint32_t type;
        uint64_t remaining;
        int n = websocket_recv_msg(fd, input, sizeof(input), &type, &remaining, 5000);
        bool valid = n == 5 + sizeof(MB_DEVICE_PAIR) - 1 && remaining == 0 &&
                     (type & WEBSOCKET_FLAG_TEXT) && (type & WEBSOCKET_FLAG_FINAL) &&
                     !memcmp(input, "auth:", 5) &&
                     !memcmp(input + 5, MB_DEVICE_PAIR, sizeof(MB_DEVICE_PAIR) - 1);
        if (valid) {
            k_sem_reset(&reset_done);
            atomic_set(&reset_pending, 1);
            valid = k_sem_take(&reset_done, K_SECONDS(1)) == 0;
        }
        if (valid) {
            atomic_set(&authenticated, 1);
            valid = websocket_send_msg(fd, (const uint8_t *)"ready", 5,
                WEBSOCKET_OPCODE_DATA_TEXT, false, true, 1000) >= 0;
        }
        size_t message_bytes = 0;
        bool binary = false;
        while (valid) {
            n = websocket_recv_msg(fd, input, sizeof(input), &type, &remaining, 10);
            if (n == -EAGAIN) n = 0;
            else if (n < 0 || (type & WEBSOCKET_FLAG_CLOSE)) break;
            if (n > 0) {
                if (type & WEBSOCKET_FLAG_PING) {
                    if (websocket_send_msg(fd, input, n, WEBSOCKET_OPCODE_PONG, false, true, 500) < 0) break;
                    continue;
                }
                if (type & WEBSOCKET_FLAG_BINARY) binary = true;
                if (!binary || (type & WEBSOCKET_FLAG_TEXT) || message_bytes + n + remaining > 8192) break;
                message_bytes += n;
                bool queued = false;
                int64_t deadline = k_uptime_get() + 500;
                do {
                    k_mutex_lock(&queues, K_FOREVER);
                    if (ring_buf_space_get(&rx_queue) >= n) {
                        ring_buf_put(&rx_queue, input, n); queued = true;
                    }
                    k_mutex_unlock(&queues);
                    if (!queued) k_sleep(K_MSEC(1));
                } while (!queued && k_uptime_get() < deadline);
                if (!queued) break;
                if ((type & WEBSOCKET_FLAG_FINAL) && remaining == 0) { message_bytes = 0; binary = false; }
            }
            k_mutex_lock(&queues, K_FOREVER);
            int count = ring_buf_get(&tx_queue, output, sizeof(output));
            k_mutex_unlock(&queues);
            if (count && websocket_send_msg(fd, output, count, WEBSOCKET_OPCODE_DATA_BINARY,
                false, true, 1000) < 0) break;
        }
        atomic_set(&authenticated, 0);
        websocket_unregister(fd);
        client_socket = -1;
        atomic_clear(&busy);
    }
}
K_THREAD_DEFINE(ws_worker, 6144, websocket_worker, NULL, NULL, NULL, 7, 0, 0);

int mb_ws_setup(int fd, struct http_request_ctx *request, void *user)
{
    ARG_UNUSED(user);
    if (!mb_same_origin(request) || !atomic_cas(&busy, 0, 1)) return -EACCES;
    client_socket = fd;
    k_sem_give(&client_ready);
    return 0;
}
