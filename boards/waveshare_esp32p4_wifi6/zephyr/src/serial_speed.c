/* SPDX-License-Identifier: MPL-2.0 */
#include "serial_speed.h"
#include "serial_rate.h"
#include "vm/interp.h"
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
static serial_rate rate={.baud=115200,.target=115200};
#if !defined(CONFIG_P4_HOSTED)
static const struct device *const uart=DEVICE_DT_GET(DT_NODELABEL(uart0));
static int apply(uint32_t baud,void *context){
    ARG_UNUSED(context);struct uart_config cfg;int e=uart_config_get(uart,&cfg);if(e)return e;
    cfg.baudrate=baud;uart_irq_rx_disable(uart);e=uart_configure(uart,&cfg);uart_irq_rx_enable(uart);return e;
}
#endif
uint32_t p4_serial_speed_baud(void){return rate.baud;}
void p4_serial_speed_poll(void){
#if !defined(CONFIG_P4_HOSTED)
    if(rate.state!=SERIAL_BASE)serial_rate_poll(&rate,k_uptime_get(),uart_irq_tx_complete(uart)>0,apply,NULL);
#endif
}
void p4_serial_speed_message(int type,int n,const char *body){
    if(type!=214)return;
    serial_rate_request request;if(!serial_rate_decode((const uint8_t *)body,n,&request))return;
    if(request.operation!=4&&!hasOutputSpace(21))return;
#if defined(CONFIG_P4_HOSTED)
    unsigned status=3;
#else
    unsigned status=serial_rate_command(&rate,&request,k_uptime_get());
#endif
    if(request.operation==4)return;
    uint8_t out[16];serial_rate_reply(&rate,&request,status,out);waitAndSendMessage(214,0,16,(char *)out);
}
