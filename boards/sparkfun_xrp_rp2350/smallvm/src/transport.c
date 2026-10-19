/* SPDX-License-Identifier: MPL-2.0 */
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/ring_buffer.h>
#include <zephyr/sys/atomic.h>
#include <errno.h>
#include "xrp.h"
#include "generic_io.h"
#include "network_setup.h"
#include "network_transport.h"
#include <string.h>

static const struct device *const cdc = DEVICE_DT_GET(DT_NODELABEL(mb_cdc));
RING_BUF_DECLARE(rx, 4096);
RING_BUF_DECLARE(tx, 4096);
RING_BUF_DECLARE(ws_rx,8192);
RING_BUF_DECLARE(ws_tx,8192);
static atomic_t usb_owner,ws_owner,ws_pending;
static atomic_t overflow;
static bool ready, connected;
extern void smallvmResetTransport(void);
static void discard_rx(void)
{
    uint8_t *part;unsigned count;
    while ((count=ring_buf_get_claim(&rx,&part,4096))) {
        mbnw_clear(part,count);ring_buf_get_finish(&rx,count);
    }
    ring_buf_reset(&rx);
}

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
    mbnw_clear(bytes,sizeof(bytes));
}

int xrp_transport_init(void)
{
    if (!device_is_ready(cdc)) return -ENODEV;
    int err = uart_irq_callback_user_data_set(cdc, usb_irq, NULL);
    if (err) return err;
    uart_irq_rx_enable(cdc);
    ready = true;
    return 0;
}

void xrp_transport_poll(void)
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
        if (!link || lost) discard_rx();
        ring_buf_reset(&tx);
        connected = link;
        atomic_set(&usb_owner,link);
        if(link){atomic_clear(&ws_owner);atomic_clear(&ws_pending);ring_buf_reset(&ws_rx);ring_buf_reset(&ws_tx);}
        irq_unlock(key);
        /* The VM thread owns runtime buffers and interpreter state. */
        xrp_io_i2c_cancel();xrp_io_pwm_stop();smallvmResetTransport();
    }
    int request=atomic_set(&ws_pending,0);
    if(request){
        unsigned key=irq_lock();
        ring_buf_reset(&ws_rx);ring_buf_reset(&ws_tx);
        atomic_set(&ws_owner,request==1&&!connected);
        irq_unlock(key);xrp_io_i2c_cancel();xrp_io_pwm_stop();smallvmResetTransport();
    }
}

bool xrp_transport_connected(void) { return connected||atomic_get(&ws_owner); }
bool xrp_wifi_setup_local(void){return atomic_get(&usb_owner)!=0;}
int xrp_ws_request(void)
{
    if(atomic_get(&usb_owner)||atomic_get(&ws_owner)||!atomic_cas(&ws_pending,0,1))return -EBUSY;
    return 0;
}
bool xrp_ws_connected(void){return atomic_get(&ws_owner)!=0;}
void xrp_ws_close(void)
{
    unsigned key=irq_lock();
    /* USB preemption already clears the network queues/runtime. A late
     * socket close must not reset a newly arrived USB command a second time. */
    if(!atomic_get(&usb_owner)&&(atomic_get(&ws_owner)||atomic_get(&ws_pending)==1)){
        atomic_clear(&ws_owner);atomic_set(&ws_pending,-1);
    }
    irq_unlock(key);
}
int xrp_ws_input(const uint8_t *data,size_t size)
{
    if(!atomic_get(&ws_owner))return -ENOTCONN;
    unsigned key=irq_lock();
    int n=ring_buf_space_get(&ws_rx)>=size?(int)ring_buf_put(&ws_rx,data,size):-ENOBUFS;
    irq_unlock(key);return n;
}
int xrp_ws_output(uint8_t *data,size_t size)
{
    if(!atomic_get(&ws_owner))return 0;
    unsigned key=irq_lock();int n=ring_buf_get(&ws_tx,data,size);irq_unlock(key);return n;
}

int recvBytes(uint8_t *dst, int count)
{
    if (count <= 0) return 0;
    if(!connected&&atomic_get(&ws_owner)){
        unsigned key=irq_lock();int n=ring_buf_get(&ws_rx,dst,count);irq_unlock(key);return n;
    }
    if(!connected)return 0;
    unsigned key = irq_lock();
    int got=0;
    while (got<count) {
        uint8_t *part;
        unsigned n=ring_buf_get_claim(&rx,&part,count-got);
        if (!n) break;
        memcpy(dst+got,part,n);mbnw_clear(part,n);
        ring_buf_get_finish(&rx,n);got+=n;
    }
    irq_unlock(key);
    return got;
}

int sendBytes(uint8_t *data, int start, int end)
{
    if(start < 0 || end < start)return 0;
    if(!connected&&atomic_get(&ws_owner)){
        unsigned key=irq_lock();int n=ring_buf_put(&ws_tx,data+start,end-start);irq_unlock(key);return n;
    }
    /* Unattended autorun must not fill the VM's output queue forever. A
     * later owner starts a fresh framed stream in xrp_transport_poll(). */
    if(!connected)return end-start;
    uint32_t dtr=0;
    if(uart_line_ctrl_get(cdc,UART_LINE_CTRL_DTR,&dtr) || !dtr)return end-start;
    unsigned key = irq_lock();
    int sent = ring_buf_put(&tx, data + start, end - start);
    if (sent) uart_irq_tx_enable(cdc);
    irq_unlock(key);
    return sent;
}
