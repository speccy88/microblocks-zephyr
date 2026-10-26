/* SPDX-License-Identifier: MPL-2.0 */
/* Bounded native transport pattern from this repository's XRP and S3 ports. */
#include "hosted_server.h"
#include "result_store.h"
#include "storage_protocol.h"
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/net/websocket.h>
#include <zephyr/sys/ring_buffer.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <string.h>
static const struct device *const serial=DEVICE_DT_GET(DT_NODELABEL(uart0));
RING_BUF_DECLARE(uart_rx,8192);
/* CPU-only WS queues use PSRAM. UART ISR and hardware DMA stay internal. */
static struct ring_buf ws_rx,ws_tx;
static bool queues_ready;
static struct k_spinlock io_lock;
/* 0 idle, 1 UART pending, 2 UART active, 3 WS pending, 4 WS active, 5 closing */
static int owner;
static uint32_t last_uart;
static int ws_fd=-1;
static atomic_t ws_busy;
K_SEM_DEFINE(ws_client,0,1);
K_SEM_DEFINE(ws_reset,0,1);
extern void smallvmResetTransport(void);
static void serial_irq(const struct device *dev,void *arg)
{
 (void)arg;uart_irq_update(dev);
 while(uart_irq_is_pending(dev)){
  if(!uart_irq_rx_ready(dev))break;
  uint8_t bytes[64];int n=uart_fifo_read(dev,bytes,sizeof(bytes));if(n<=0)break;
  k_spinlock_key_t key=k_spin_lock(&io_lock);
  if(owner==0){owner=1;last_uart=k_uptime_get_32();}
  if(owner==1||owner==2){
   last_uart=k_uptime_get_32();
   if(ring_buf_space_get(&uart_rx)>=(unsigned)n)ring_buf_put(&uart_rx,bytes,n);
   else owner=5;
  }
  k_spin_unlock(&io_lock,key);
 }
}
void p4_transport_init(void)
{
 uint8_t *buffers=shared_multi_heap_alloc(SMH_REG_ATTR_EXTERNAL,16384);
 if(buffers){ring_buf_init(&ws_rx,8192,buffers);ring_buf_init(&ws_tx,8192,buffers+8192);queues_ready=true;}
 if(device_is_ready(serial)){uart_irq_callback_user_data_set(serial,serial_irq,NULL);uart_irq_rx_enable(serial);}
}
bool p4_transport_ready(void){return queues_ready;}
void p4_transport_poll(void)
{
 int action=0;
 k_spinlock_key_t key=k_spin_lock(&io_lock);
 if(owner==2 && (uint32_t)(k_uptime_get_32()-last_uart)>5000)owner=5;
 if(owner==1){action=1;ring_buf_reset(&ws_rx);ring_buf_reset(&ws_tx);}
 if(owner==3){action=3;ring_buf_reset(&uart_rx);ring_buf_reset(&ws_rx);ring_buf_reset(&ws_tx);}
 if(owner==5){action=5;ring_buf_reset(&uart_rx);ring_buf_reset(&ws_rx);ring_buf_reset(&ws_tx);}
 k_spin_unlock(&io_lock,key);
 if(!action)return;
 /* This function only runs on the VM thread. No worker/ISR enters VM state. */
 smallvmResetTransport();media_session(0);mb_storage_protocol_reset();
 key=k_spin_lock(&io_lock);
 if(action==1 && owner==1)owner=2;
 if(action==3 && owner==3)owner=4;
 if(action==5 && owner==5)owner=0;
 k_spin_unlock(&io_lock,key);
 if(action==3)k_sem_give(&ws_reset);
}
bool p4_transport_is_usb(void){k_spinlock_key_t key=k_spin_lock(&io_lock);bool usb=owner==2;k_spin_unlock(&io_lock,key);return usb;}
const char *p4_transport_owner(void){k_spinlock_key_t key=k_spin_lock(&io_lock);int o=owner;k_spin_unlock(&io_lock,key);return o==2?"USB":o==4?"WebSocket":o?"transition":"none";}
int p4_transport_recv(uint8_t *dst,int n)
{
 if(n<=0)return 0;
 k_spinlock_key_t key=k_spin_lock(&io_lock);
 int count=owner==2?ring_buf_get(&uart_rx,dst,n):owner==4?ring_buf_get(&ws_rx,dst,n):0;
 k_spin_unlock(&io_lock,key);return count;
}
int p4_transport_send(uint8_t *data,int start,int end)
{
 if(start<0||end<start)return 0;
 k_spinlock_key_t key=k_spin_lock(&io_lock);int o=owner;
 int n=o==4?ring_buf_put(&ws_tx,data+start,end-start):end-start;
 k_spin_unlock(&io_lock,key);
 if(o==2)for(int i=start;i<end;i++)uart_poll_out(serial,data[i]);
 return n;
}
static void websocket_worker(void *a,void *b,void *c)
{
 (void)a;(void)b;(void)c;uint8_t input[1024],output[1024];
 for(;;){
  k_sem_take(&ws_client,K_FOREVER);int fd=ws_fd;
  bool valid=k_sem_take(&ws_reset,K_SECONDS(1))==0;
  if(valid)valid=websocket_send_msg(fd,(const uint8_t *)"ready",5,WEBSOCKET_OPCODE_DATA_TEXT,false,true,1000)==5;
  size_t message_bytes=0;bool binary=false;
  while(valid){
   uint32_t type=0;uint64_t remaining=0;
   int n=websocket_recv_msg(fd,input,sizeof(input),&type,&remaining,10);
   if(n==-EAGAIN)n=0;else if(n<0||(type&WEBSOCKET_FLAG_CLOSE))break;
   if(n>0){
    if(type&WEBSOCKET_FLAG_PING){if(websocket_send_msg(fd,input,n,WEBSOCKET_OPCODE_PONG,false,true,500)!=n)break;continue;}
    if(type&WEBSOCKET_FLAG_BINARY)binary=true;
    if(!binary||(type&WEBSOCKET_FLAG_TEXT)||message_bytes+n+remaining>8192)break;
    message_bytes+=n;bool queued=false;int64_t until=k_uptime_get()+500;
    do{
     k_spinlock_key_t key=k_spin_lock(&io_lock);
     if(owner==4 && ring_buf_space_get(&ws_rx)>=(unsigned)n){ring_buf_put(&ws_rx,input,n);queued=true;}
     k_spin_unlock(&io_lock,key);if(!queued)k_sleep(K_MSEC(1));
    }while(!queued&&k_uptime_get()<until);
    if(!queued)break;
    if((type&WEBSOCKET_FLAG_FINAL)&&!remaining){message_bytes=0;binary=false;}
   }
   k_spinlock_key_t key=k_spin_lock(&io_lock);
   int count=owner==4?ring_buf_get(&ws_tx,output,sizeof(output)):0;valid=owner==4;
   k_spin_unlock(&io_lock,key);
   if(count && websocket_send_msg(fd,output,count,WEBSOCKET_OPCODE_DATA_BINARY,false,true,1000)!=count)break;
  }
  k_spinlock_key_t key=k_spin_lock(&io_lock);if(owner==3||owner==4)owner=5;k_spin_unlock(&io_lock,key);
  websocket_unregister(fd);ws_fd=-1;atomic_clear(&ws_busy);
 }
}
K_THREAD_DEFINE(p4_ws_worker,6144,websocket_worker,NULL,NULL,NULL,7,0,0);
int p4_ws_setup(int fd,struct http_request_ctx *request,void *user)
{
 (void)user;if(!queues_ready)return -ENOMEM;
 if(!p4_same_origin(request)||!atomic_cas(&ws_busy,0,1))return -EACCES;
 k_sem_reset(&ws_reset);
 k_spinlock_key_t key=k_spin_lock(&io_lock);
 if(owner){k_spin_unlock(&io_lock,key);atomic_clear(&ws_busy);return -EBUSY;}
 owner=3;ws_fd=fd;k_spin_unlock(&io_lock,key);k_sem_give(&ws_client);return 0;
}
