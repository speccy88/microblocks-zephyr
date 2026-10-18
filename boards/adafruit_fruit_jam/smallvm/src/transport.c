/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/ring_buffer.h>
#include <zephyr/sys/atomic.h>
#include <errno.h>
#include "fruit_jam.h"

static const struct device *const cdc = DEVICE_DT_GET(DT_NODELABEL(mb_cdc));
RING_BUF_DECLARE(rx, 4096);
RING_BUF_DECLARE(tx, 4096);
static atomic_t overflow;
static bool ready, connected;
extern void smallvmResetTransport(void);

static void usb_irq(const struct device *dev, void *unused)
{
    (void)unused;
    uint8_t bytes[64];
    uint32_t dtr = 0;
    uart_line_ctrl_get(dev, UART_LINE_CTRL_DTR, &dtr);
    uart_irq_update(dev);
    while (uart_irq_rx_ready(dev)) {
        int n = uart_fifo_read(dev, bytes, sizeof(bytes));
        if (n <= 0) break;
        if (dtr && ring_buf_put(&rx, bytes, n) != (unsigned)n) atomic_set(&overflow, 1);
    }
    if (uart_irq_tx_ready(dev)) {
        unsigned n = ring_buf_peek(&tx, bytes, sizeof(bytes));
        if (n) {
            int sent = uart_fifo_fill(dev, bytes, n);
            if (sent > 0) ring_buf_get(&tx, bytes, sent);
        }
        if (ring_buf_is_empty(&tx)) uart_irq_tx_disable(dev);
    }
}

int fj_transport_init(void)
{
    if (!device_is_ready(cdc)) return -ENODEV;
    int err = uart_irq_callback_user_data_set(cdc, usb_irq, NULL);
    if (err) return err;
    uart_irq_rx_enable(cdc);
    ready = true;
    return 0;
}

void fj_transport_poll(void)
{
    if (!ready) return;
    uint32_t dtr = 0;
    if (uart_line_ctrl_get(cdc, UART_LINE_CTRL_DTR, &dtr)) dtr = 0;
    bool link = dtr != 0;
    bool lost = atomic_set(&overflow, 0) != 0;
    if (link != connected || lost) {
        unsigned key = irq_lock();
        uart_irq_tx_disable(cdc);
        /* Retain the first packet if it arrived after DTR rose but before
         * this VM-thread poll. Disconnected bytes are discarded in usb_irq. */
        if (!link || lost) ring_buf_reset(&rx);
        ring_buf_reset(&tx);
        connected = link;
        irq_unlock(key);
        /* The VM thread owns runtime buffers and interpreter state. */
        smallvmResetTransport();
    }
}

bool fj_transport_connected(void) { return connected; }

int recvBytes(uint8_t *dst, int count)
{
    if (!connected || count <= 0) return 0;
    unsigned key = irq_lock();
    int got = ring_buf_get(&rx, dst, count);
    irq_unlock(key);
    return got;
}

int sendBytes(uint8_t *data, int start, int end)
{
    if (!connected || start < 0 || end < start) return 0;
    unsigned key = irq_lock();
    int sent = ring_buf_put(&tx, data + start, end - start);
    if (sent) uart_irq_tx_enable(cdc);
    irq_unlock(key);
    return sent;
}
