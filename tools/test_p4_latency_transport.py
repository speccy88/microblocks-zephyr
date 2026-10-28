#!/usr/bin/env python3
"""Run the actual WebSocket worker through queueing, idle and close under sanitizers."""
from pathlib import Path
import ast,json,os,subprocess
repo=Path(__file__).resolve().parents[1];out=repo/'build-artifacts/p4-latency-tests';out.mkdir(parents=True,exist_ok=True)
tree=ast.parse((repo/'tools/test_p4_transport_loss.py').read_text())
fakes=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith('\n#pragma once'))
inc=out/'include';inc.mkdir(exist_ok=True)
(inc/'fakes.h').write_text(fakes+'\nbool ring_buf_is_empty(struct ring_buf*);\n')
for name in ['zephyr/kernel.h','zephyr/drivers/uart.h','zephyr/net/websocket.h','zephyr/sys/ring_buffer.h','zephyr/sys/atomic.h','zephyr/multi_heap/shared_multi_heap.h','zephyr/net/http/server.h','result_store.h','storage_protocol.h']:
 p=inc/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "fakes.h"\n')
source=out/'test.c';source.write_text(r'''
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include "hosted_transport.c"
static uint32_t clock_ms=90;
static unsigned receives,sends,closed,checks;
static bool locked;
static jmp_buf finished;
#define CHECK(x) do{assert(x);checks++;}while(0)
int k_spin_lock(struct k_spinlock *p){assert(p==&io_lock&&!locked);locked=true;return 0;}
void k_spin_unlock(struct k_spinlock *p,int key){assert(p==&io_lock&&locked&&!key);locked=false;}
uint32_t k_uptime_get_32(void){return clock_ms;}
int64_t k_uptime_get(void){return clock_ms;}
void k_sleep(int ms){clock_ms+=ms;}
int k_sem_take(struct k_sem *p,int timeout){(void)timeout;if(p==&ws_client&&closed)longjmp(finished,1);return 0;}
unsigned ring_buf_space_get(struct ring_buf *p){return 8192-p->used;}
unsigned ring_buf_put(struct ring_buf *p,const uint8_t *data,unsigned n){(void)data;assert(n<=8192-p->used);p->used+=n;return n;}
unsigned ring_buf_get(struct ring_buf *p,uint8_t *data,unsigned n){if(n>p->used)n=p->used;memset(data,0,n);p->used-=n;return n;}
bool ring_buf_is_empty(struct ring_buf *p){return p->used==0;}
void uart_poll_out(const struct device *p,uint8_t b){(void)p;(void)b;assert(false);}
void atomic_clear(atomic_t *p){*p=0;}
int websocket_send_msg(int fd,const uint8_t *data,unsigned n,int opcode,bool mask,bool final,int timeout){
 assert(fd==7&&!mask&&final&&timeout>0&&data);(void)opcode;clock_ms+=(sends++?7:2);return n;
}
void websocket_unregister(int fd){assert(fd==7);closed++;}
int websocket_recv_msg(int fd,uint8_t *data,unsigned n,uint32_t *type,uint64_t *remaining,int timeout){
 assert(fd==7&&n==1024&&timeout==10);receives++;
 if(receives==1){clock_ms=100;memset(data,0,3);*type=WEBSOCKET_FLAG_BINARY|WEBSOCKET_FLAG_FINAL;*remaining=0;return 3;}
 if(receives==2){
  uint8_t reply[3]={250,26,77};clock_ms=103;CHECK(p4_transport_recv(data,3)==3);CHECK(p4_transport_send(reply,0,3)==3);clock_ms=113;return -EAGAIN;
 }
 if(receives==3){clock_ms+=10;return -EAGAIN;}
 return -ECONNRESET;
}
int main(void){
 owner=4;ws_fd=7;ws_busy=1;
 if(!setjmp(finished))websocket_worker(NULL,NULL,NULL);
 CHECK(closed==1&&owner==5&&ws_busy==0);CHECK(!ws_rx.used&&!ws_tx.used);
 CHECK(latency.recv_calls==4&&latency.recv_max_ms==13);
 CHECK(latency.send_calls==2&&latency.send_max_ms==7);
 CHECK(latency.vm_rx_calls==1&&latency.vm_rx_max_ms==3);
 CHECK(latency.vm_tx_calls==1&&latency.vm_tx_max_ms==10);
 clock_ms=9;observe_io(true,UINT32_MAX-10);CHECK(latency.recv_max_ms==20);
 latency.recv_calls=UINT32_MAX;observe_io(true,9);CHECK(latency.recv_calls==UINT32_MAX);
 char json[512];p4_transport_latency_json(json,sizeof(json));CHECK(strstr(json,"\"recv_max_ms\":20")!=NULL);
 char short_buffer[2];p4_transport_latency_json(short_buffer,sizeof(short_buffer));CHECK(short_buffer[1]==0);
 printf("{\"result\":\"PASS\",\"checks\":%u,\"physical_tested\":false}\n",checks);
}
''')
binary=out/'test';subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-sign-compare','-DCONFIG_P4_WIFI_LATENCY_DIAGNOSTIC=1','-fno-pie','-no-pie','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(inc),'-I'+str(repo/'boards/waveshare_esp32p4_wifi6/zephyr/src'),str(source),'-o',str(binary)],check=True)
result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
if result.returncode:print(result.stderr)
result.check_returncode();report=json.loads(result.stdout);report['sanitizers']=['address','undefined'];report['scope']='actual worker, queue timings, idle, close, clock wrap and saturation'
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
