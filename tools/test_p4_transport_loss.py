#!/usr/bin/env python3
"""Exercise actual hosted transport ownership/session cleanup after link loss."""
from pathlib import Path
import json, os, subprocess
repo=Path(__file__).resolve().parents[1]
out=repo/'build-artifacts/p4-transport-loss-tests';out.mkdir(parents=True,exist_ok=True)
inc=out/'include';inc.mkdir(exist_ok=True)
for name in ['zephyr/kernel.h','zephyr/drivers/uart.h','zephyr/net/websocket.h',
 'zephyr/sys/ring_buffer.h','zephyr/sys/atomic.h','zephyr/multi_heap/shared_multi_heap.h',
 'zephyr/net/http/server.h','result_store.h','storage_protocol.h']:
 p=inc/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "fakes.h"\n')
(inc/'fakes.h').write_text(r'''
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
struct device {int unused;};
#define DT_NODELABEL(x) 0
#define DEVICE_DT_GET(x) ((const struct device*)1)
struct ring_buf {unsigned used;};
#define RING_BUF_DECLARE(n,s) struct ring_buf n
struct k_spinlock {int unused;};typedef int k_spinlock_key_t;
int k_spin_lock(struct k_spinlock*);void k_spin_unlock(struct k_spinlock*,int);
struct k_sem {int value;};
#define K_SEM_DEFINE(n,a,b) struct k_sem n={a}
#define K_THREAD_DEFINE(...)
#define K_FOREVER -1
#define K_SECONDS(n) (n)
#define K_MSEC(n) (n)
int k_sem_take(struct k_sem*,int);void k_sem_give(struct k_sem*);void k_sem_reset(struct k_sem*);
int64_t k_uptime_get(void);uint32_t k_uptime_get_32(void);void k_sleep(int);
unsigned ring_buf_space_get(struct ring_buf*);unsigned ring_buf_put(struct ring_buf*,const uint8_t*,unsigned);
unsigned ring_buf_get(struct ring_buf*,uint8_t*,unsigned);void ring_buf_reset(struct ring_buf*);
void ring_buf_init(struct ring_buf*,unsigned,void*);
typedef int atomic_t;bool atomic_cas(atomic_t*,int,int);void atomic_clear(atomic_t*);
bool device_is_ready(const struct device*);int uart_irq_update(const struct device*);
bool uart_irq_is_pending(const struct device*);bool uart_irq_rx_ready(const struct device*);
int uart_fifo_read(const struct device*,uint8_t*,int);void uart_poll_out(const struct device*,uint8_t);
void uart_irq_callback_user_data_set(const struct device*,void(*)(const struct device*,void*),void*);
void uart_irq_rx_enable(const struct device*);
#define SMH_REG_ATTR_EXTERNAL 1
void *shared_multi_heap_alloc(int,unsigned);
#define WEBSOCKET_OPCODE_DATA_TEXT 1
#define WEBSOCKET_OPCODE_DATA_BINARY 2
#define WEBSOCKET_OPCODE_PONG 3
#define WEBSOCKET_FLAG_CLOSE 1
#define WEBSOCKET_FLAG_PING 2
#define WEBSOCKET_FLAG_BINARY 4
#define WEBSOCKET_FLAG_TEXT 8
#define WEBSOCKET_FLAG_FINAL 16
int websocket_send_msg(int,const uint8_t*,unsigned,int,bool,bool,int);
int websocket_recv_msg(int,uint8_t*,unsigned,uint32_t*,uint64_t*,int);void websocket_unregister(int);
void media_session(int);void mb_storage_protocol_reset(void);
struct http_client_ctx;struct http_request_ctx;struct http_response_ctx;
enum http_transaction_status {HTTP_SERVER_DATA_MORE,HTTP_SERVER_DATA_FINAL};
''')
source=out/'test.c';source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include "hosted_transport.c"
static unsigned checks,vm_resets,media_resets,file_resets;
#define CHECK(x) do{assert(x);checks++;}while(0)
int k_spin_lock(struct k_spinlock *p){assert(p==&io_lock);return 0;}
void k_spin_unlock(struct k_spinlock *p,int key){assert(p==&io_lock&&!key);}
uint32_t k_uptime_get_32(void){return 100;}
void ring_buf_reset(struct ring_buf *r){r->used=0;}
void k_sem_give(struct k_sem *s){s->value=1;}
void smallvmResetTransport(void){vm_resets++;}
void media_session(int n){assert(!n);media_resets++;}
void mb_storage_protocol_reset(void){file_resets++;}
int main(void){
 for(int initial=0;initial<=5;initial++){
  owner=initial;vm_resets=media_resets=file_resets=0;
  uart_rx.used=ws_rx.used=ws_tx.used=7;ws_reset.value=0;last_uart=100;
  p4_transport_network_lost();
  CHECK(owner==((initial==3||initial==4)?5:initial));
  CHECK(!vm_resets&&!media_resets&&!file_resets); /* callback never enters VM */
  p4_transport_network_lost();CHECK(!vm_resets); /* duplicate loss is idempotent */
  if(initial==3||initial==4||initial==5){
   p4_transport_poll();CHECK(!owner&&vm_resets==1&&media_resets==1&&file_resets==1);
   CHECK(!uart_rx.used&&!ws_rx.used&&!ws_tx.used&&!ws_reset.value);
   p4_transport_poll();CHECK(vm_resets==1&&media_resets==1&&file_resets==1);
  }else if(initial==0||initial==2){
   p4_transport_poll();CHECK(owner==initial&&!vm_resets&&!media_resets&&!file_resets);
   CHECK(uart_rx.used==7&&ws_rx.used==7&&ws_tx.used==7);
  }else{
   p4_transport_poll();CHECK(owner==2&&vm_resets==1); /* USB pending still activates */
  }
 }
 printf("{\"result\":\"PASS\",\"checks\":%u,\"physical_tested\":false}\n",checks);
}
''')
binary=out/'test'
subprocess.run(['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-sign-compare',
 '-fno-pie','-no-pie','-ffunction-sections','-fdata-sections','-Wl,--gc-sections',
 '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(inc),
 '-I'+str(repo/'boards/waveshare_esp32p4_wifi6/zephyr/src'),str(source),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10,
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
if run.returncode:print(run.stderr)
run.check_returncode();report=json.loads(run.stdout)
report.update(scope='actual hosted_transport.c ownership and VM-thread cleanup',sanitizers=['address','undefined'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
