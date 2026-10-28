#!/usr/bin/env python3
"""Actual pinned Zephyr poll + native socket prepare; synthetic OS/eventfd only.

Source functions come from the existing Apache-2.0 Zephyr checkout. Generated
host artifacts stay under build-artifacts, never a target/card connection.
"""
# SPDX-License-Identifier: MIT
from pathlib import Path
import argparse,hashlib,json,subprocess
parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);args=parser.parse_args()
repo=Path(__file__).resolve().parents[1];root=repo/'build-artifacts/p4-http-poll-tests';root.mkdir(parents=True,exist_ok=True)
ws=args.workspace.resolve();z=ws/'zephyr'
assert subprocess.check_output(['git','-C',str(z),'rev-parse','HEAD'],text=True).strip()=='a915b2f12675b48b16d56653ea145dcd8f20cbbf'
poll=(z/'lib/os/zvfs/zvfs_poll.c').read_text()
socket=(z/'subsys/net/lib/sockets/sockets_inet.c').read_text()
start=socket.index('static int zsock_poll_prepare_ctx(');end=socket.index('\n}',start)+2
prepare=socket[start:end]
poll='\n'.join(line for line in poll.splitlines() if not line.startswith('#include'))
fake=r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdio.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define ARG_UNUSED(a) (void)(a)
#define IS_ENABLED(a) (a)
#define CONFIG_NET_NATIVE_TCP 1
#define K_POLL_TYPE_FIFO_DATA_AVAILABLE 1
#define K_POLL_TYPE_SEM_AVAILABLE 2
#define K_POLL_MODE_NOTIFY_ONLY 0
#define K_POLL_STATE_NOT_READY 0
#define NET_SOCK_STREAM 1
#define NET_CONTEXT_CONNECTING 1
#define ZSOCK_POLLIN 1
#define ZSOCK_POLLOUT 2
#define ZVFS_POLLNVAL 4
#define ZFD_IOCTL_POLL_PREPARE 1
#define ZFD_IOCTL_POLL_UPDATE 2
#define ZFD_IOCTL_POLL_OFFLOAD 3
#define SYS_FOREVER_MS -1
typedef struct {int ticks;} k_timeout_t;
typedef k_timeout_t k_timepoint_t;
#define K_FOREVER ((k_timeout_t){-1})
#define K_NO_WAIT ((k_timeout_t){0})
#define K_TIMEOUT_EQ(a,b) ((a).ticks==(b).ticks)
#define K_MSEC(a) ((k_timeout_t){a})
static k_timepoint_t sys_timepoint_calc(k_timeout_t t){return t;}
static k_timeout_t sys_timepoint_timeout(k_timepoint_t t){return t;}
static int k_ticks_to_ms_floor32(int n){return n;}
struct k_poll_event {void *obj;int type,mode,state;};
struct zvfs_pollfd {int fd;short events,revents;};
#define zsock_pollfd zvfs_pollfd
struct net_context {int recv_q,sem;bool eventfd;};
struct k_mutex {int held;};struct fd_op_vtable {int unused;};
static struct net_context contexts[12];static struct k_mutex mutex;
static struct fd_op_vtable table;static unsigned polls;
static int k_mutex_lock(struct k_mutex *m,k_timeout_t t){(void)t;assert(!m->held);m->held=1;return 0;}
static void k_mutex_unlock(struct k_mutex *m){assert(m->held);m->held=0;}
static int net_context_get_type(struct net_context *c){(void)c;return NET_SOCK_STREAM;}
static void *net_context_get_iface(struct net_context *c){(void)c;return NULL;}
static bool net_if_is_ip_offloaded(void *i){(void)i;return false;}
static int net_context_get_state(struct net_context *c){(void)c;return 0;}
static int *net_tcp_conn_sem_get(struct net_context *c){return &c->sem;}
static int *net_tcp_tx_sem_get(struct net_context *c){return &c->sem;}
static bool sock_is_eof(struct net_context *c){(void)c;return false;}
static bool sock_is_error(struct net_context *c){(void)c;return false;}
static void *zvfs_get_fd_obj_and_vtable(int fd,const struct fd_op_vtable **v,struct k_mutex **m){if(fd<0||fd>=12)return NULL;*v=&table;*m=&mutex;contexts[fd].eventfd=fd==0;return contexts+fd;}
static int k_poll(struct k_poll_event *events,int n,k_timeout_t t){(void)events;(void)t;assert(!mutex.held && n<=CONFIG_ZVFS_POLL_MAX);polls++;return 0;}
'''
io=r'''
static int fake_ioctl(void *obj,int op,...){
 va_list ap;va_start(ap,op);struct net_context *c=obj;struct zvfs_pollfd *p=va_arg(ap,struct zvfs_pollfd*);
 struct k_poll_event **pev=va_arg(ap,struct k_poll_event**);int result=0;
 if(op==ZFD_IOCTL_POLL_PREPARE){
  struct k_poll_event *end=va_arg(ap,struct k_poll_event*);
  if(c->eventfd){if(*pev==end)result=-ENOMEM;else{(*pev)->obj=&c->sem;(*pev)++;}}
  else result=zsock_poll_prepare_ctx(c,(struct zsock_pollfd*)p,pev,end);
 }else{assert(op==ZFD_IOCTL_POLL_UPDATE);p->revents=ZSOCK_POLLIN;}
 va_end(ap);return result;
}
#define zvfs_fdtable_call_ioctl(v,obj,op,...) fake_ioctl(obj,op,__VA_ARGS__)
'''
main=r'''
int main(void){
 struct zvfs_pollfd fds[8];unsigned checks=0;
 for(unsigned count=1;count<=6;count++){
  for(unsigned i=0;i<count;i++)fds[i]=(struct zvfs_pollfd){(int)i,ZSOCK_POLLIN,0};
  errno=0;polls=0;int r=zvfs_poll_internal(fds,count,K_NO_WAIT);
  if(count>CONFIG_ZVFS_POLL_MAX){assert(r==-1 && errno==ENOMEM && !polls);}
  else{assert(r==(int)count && polls==1);}
  assert(!mutex.held);checks++;
 }
 for(unsigned i=0;i<8;i++)fds[i]=(struct zvfs_pollfd){-1,ZSOCK_POLLIN,0};
 fds[1].fd=0;fds[6].fd=1;assert(zvfs_poll_internal(fds,8,K_NO_WAIT)==2);checks++;
 printf("{\"budget\":%d,\"checks\":%u,\"second_HTTP_client_requires\":4}\n",CONFIG_ZVFS_POLL_MAX,checks);
}
'''
source=root/'poll_budget_test.c';source.write_text(fake+'\n'+prepare+'\n'+io+'\n'+poll+'\n'+main)
reports=[]
for size in [3,6,8]:
 binary=root/f'poll_budget_{size}'
 cmd=['cc','-std=c11','-g','-O1','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all',f'-DCONFIG_ZVFS_POLL_MAX={size}',str(source),'-o',str(binary)]
 subprocess.run(cmd,check=True,capture_output=True)
 r=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=10);reports.append(json.loads(r.stdout))
report={'result':'PASS','source':'pinned actual zvfs_poll_internal + zsock_poll_prepare_ctx','OS_and_eventfd':'synthetic; eventfd consumes one slot','physical_tested':False,'budgets':reports,'sanitizers':['address','undefined'],
 'poll_source_sha256':hashlib.sha256((z/'lib/os/zvfs/zvfs_poll.c').read_bytes()).hexdigest(),'socket_prepare_sha256':hashlib.sha256(prepare.encode()).hexdigest()}
(root/'poll-budget-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
