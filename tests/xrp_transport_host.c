/* SPDX-License-Identifier: MPL-2.0
 * Execute the actual XRP transport with single-threaded simulated UART/rings.
 * This verifies byte/ownership contracts, not real IRQ timing or USB hardware. */
#include "xrp.h"
#include "network_transport.h"
#include <zephyr/drivers/uart.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
struct device test_cdc={true};
static unsigned checks,resets,pwm_stops;
static uint32_t dtr;
static uart_irq_callback_user_data_t callback;
static uint8_t incoming[5000];
static unsigned incoming_size;
#define CHECK(v) do { ++checks;if(!(v)){fprintf(stderr,"check failed line %d\n",__LINE__);exit(1);} } while(0)
void smallvmResetTransport(void) { ++resets; }
void xrp_io_i2c_cancel(void) {}
void xrp_io_pwm_stop(void) { ++pwm_stops; }
int uart_line_ctrl_get(const struct device *d,uint32_t ctrl,uint32_t *out)
{ (void)d;(void)ctrl;*out=dtr;return 0; }
int uart_irq_callback_user_data_set(const struct device *d,uart_irq_callback_user_data_t f,void *u)
{ (void)d;(void)u;callback=f;return 0; }
void uart_irq_rx_enable(const struct device *d) { (void)d; }
void uart_irq_tx_enable(const struct device *d) { (void)d; }
void uart_irq_tx_disable(const struct device *d) { (void)d; }
int uart_irq_update(const struct device *d) { (void)d;return 0; }
int uart_irq_rx_ready(const struct device *d) { (void)d;return incoming_size!=0; }
int uart_irq_tx_ready(const struct device *d) { (void)d;return 0; }
int uart_fifo_read(const struct device *d,uint8_t *dst,int n)
{ (void)d;if((unsigned)n>incoming_size)n=incoming_size;memcpy(dst,incoming,n);memmove(incoming,incoming+n,incoming_size-n);incoming_size-=n;return n; }
int uart_fifo_fill(const struct device *d,const uint8_t *src,int n)
{ (void)d;(void)src;(void)n;return 0; }
int recvBytes(uint8_t *,int);
int sendBytes(uint8_t *,int,int);
static void inject(const uint8_t *p,unsigned n)
{ CHECK(n<=sizeof(incoming));memcpy(incoming,p,n);incoming_size=n;callback(&test_cdc,NULL); }
int main(void)
{
    uint8_t bytes[]={251,205,0,1,2,3,4,5},out[8192];
    CHECK(xrp_transport_init()==0);xrp_transport_poll();
    CHECK(!xrp_transport_connected());
    CHECK(sendBytes(bytes,0,8)==8); /* offline autorun drains, no deadlock */
    CHECK(sendBytes(bytes,4,2)==0);
    CHECK(xrp_ws_request()==0);CHECK(xrp_ws_request()==-EBUSY);
    xrp_transport_poll();CHECK(xrp_ws_connected());CHECK(!xrp_wifi_setup_local());
    CHECK(xrp_ws_input(bytes,8)==8);CHECK(recvBytes(out,8)==8 && !memcmp(out,bytes,8));
    CHECK(sendBytes(bytes,0,8)==8);CHECK(xrp_ws_output(out,8)==8 && !memcmp(out,bytes,8));
    dtr=1;inject(bytes,8); /* first DTR packet before VM poll is retained */
    xrp_transport_poll();CHECK(!xrp_ws_connected());CHECK(xrp_wifi_setup_local());
    CHECK(recvBytes(out,8)==8 && !memcmp(out,bytes,8));
    unsigned prior=resets;xrp_ws_close();xrp_transport_poll();CHECK(resets==prior);
    CHECK(xrp_ws_request()==-EBUSY);CHECK(xrp_ws_input(bytes,8)==-ENOTCONN);
    CHECK(sendBytes(bytes,0,8)==8);
    dtr=0;CHECK(sendBytes(bytes,0,8)==8); /* DTR loss can break a blocked VM writer */
    xrp_transport_poll();CHECK(!xrp_transport_connected());CHECK(!xrp_wifi_setup_local());
    inject(bytes,8);CHECK(recvBytes(out,8)==0);
    dtr=1;xrp_transport_poll();CHECK(recvBytes(out,8)==0);
    uint8_t excess[5000];memset(excess,0xa5,sizeof(excess));inject(excess,sizeof(excess));
    prior=resets;xrp_transport_poll();CHECK(resets==prior+1);CHECK(recvBytes(out,sizeof(out))==0);
    dtr=0;xrp_transport_poll();CHECK(xrp_ws_request()==0);xrp_transport_poll();
    CHECK(xrp_ws_connected());CHECK(xrp_ws_input(excess,sizeof(excess))==(int)sizeof(excess));
    CHECK(xrp_ws_input(excess,sizeof(excess))==-ENOBUFS);
    xrp_ws_close();xrp_transport_poll();CHECK(!xrp_transport_connected());
    CHECK(resets==pwm_stops);
    printf("{\"passed\":true,\"checks\":%u,\"transport_resets\":%u}\n",checks,resets);
    return 0;
}
