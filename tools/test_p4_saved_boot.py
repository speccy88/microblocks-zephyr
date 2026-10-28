#!/usr/bin/env python3
"""Run the actual P4 network worker against synthetic Zephyr/network/settings."""
from pathlib import Path
import json, os, subprocess
repo=Path(__file__).resolve().parents[1]
out=repo/'build-artifacts/p4-saved-boot-tests';out.mkdir(parents=True,exist_ok=True)
inc=out/'include'
headers=['zephyr/kernel.h','zephyr/net/net_if.h','zephyr/net/wifi_mgmt.h','zephyr/net/dhcpv4.h',
 'zephyr/storage/flash_map.h','zephyr/kvss/nvs.h','zephyr/drivers/flash.h','zephyr/sys/byteorder.h',
 'zephyr/net/http/server.h','hosted_server.h','http_diagnostics.h','vm/interp.h']
for name in headers:
 path=inc/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('#include "fakes.h"\n')
(inc/'fakes.h').write_text(r'''
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <netinet/in.h>
#define IS_ENABLED(x) (x)
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define K_FOREVER -1
#define K_SECONDS(x) (x)
#define K_MSEC(x) (x)
typedef int64_t k_timeout_t;
int64_t k_uptime_get(void);
#define NET_IPV4_ADDR_LEN 16
#define NET_EVENT_WIFI_CONNECT_RESULT 1
#define NET_EVENT_WIFI_DISCONNECT_RESULT 2
#define NET_EVENT_IPV4_DHCP_BOUND 4
#define NET_REQUEST_WIFI_CONNECT 16
#define NET_REQUEST_WIFI_DISCONNECT 17
#define NET_ADDR_PREFERRED 1
#define WIFI_CHANNEL_ANY 0
#define WIFI_FREQ_BAND_2_4_GHZ 0
#define WIFI_SECURITY_TYPE_PSK 1
#define DT_NODELABEL(x) 0
#define DEVICE_DT_GET(x) ((void*)1)
#define FIXED_PARTITION_ID(x) 0
struct k_mutex {int unused;};struct k_sem {int value;};
#define K_MUTEX_DEFINE(n) struct k_mutex n
#define K_SEM_DEFINE(n,a,b) struct k_sem n={a}
struct k_thread {int unused;};typedef struct k_thread *k_tid_t;
#define K_THREAD_DEFINE(n,...) struct k_thread n##_thread; k_tid_t n=&n##_thread
extern struct fake_work_q {struct k_thread thread;} k_sys_work_q;
int k_mutex_lock(struct k_mutex*,int);int k_mutex_unlock(struct k_mutex*);
int k_sem_take(struct k_sem*,k_timeout_t);void k_sem_give(struct k_sem*);void k_sem_reset(struct k_sem*);
int k_thread_stack_space_get(k_tid_t,size_t*);
struct net_if {int unused;};struct net_mgmt_event_callback {void *info;};
struct http_client_ctx;struct http_request_ctx;struct http_response_ctx;
enum http_transaction_status {HTTP_SERVER_DATA_MORE,HTTP_SERVER_DATA_FINAL};
struct wifi_status {int status;};
struct wifi_connect_req_params {uint8_t *ssid,*psk;unsigned ssid_length,psk_length,channel,band,security;};
void net_mgmt_init_event_callback(struct net_mgmt_event_callback*,void(*)(struct net_mgmt_event_callback*,uint64_t,struct net_if*),uint64_t);
void net_mgmt_add_event_callback(struct net_mgmt_event_callback*);
bool device_is_ready(const void*);struct net_if *net_if_get_wifi_sta(void);
int net_if_up(struct net_if*);void net_dhcpv4_start(struct net_if*);void net_dhcpv4_stop(struct net_if*);
int net_mgmt(int,struct net_if*,void*,size_t);
const struct in_addr *net_if_ipv4_get_global_addr(struct net_if*,int);
const char *net_addr_ntop(int,const void*,char*,size_t);
struct flash_area {void *fa_dev;size_t fa_off,fa_size;};
struct flash_pages_info {size_t size;};
struct nvs_fs {void *flash_device;size_t offset,sector_size,sector_count;};
int flash_area_open(int,const struct flash_area**);int flash_get_page_info_by_offs(void*,size_t,struct flash_pages_info*);
int nvs_mount(struct nvs_fs*);int nvs_read(struct nvs_fs*,int,void*,size_t);int nvs_write(struct nvs_fs*,int,const void*,size_t);
int p4_assets_check(void);bool p4_transport_ready(void);int p4_server_start(void);
const char *p4_transport_owner(void);bool p4_transport_is_usb(void);
void p4_transport_network_lost(void);
void p4_http_diag_json(char*,size_t);void waitAndSendMessage(int,int,int,char*);
static inline uint32_t sys_get_le32(const uint8_t *p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static inline void sys_put_le32(uint32_t n,uint8_t *p){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
''')
source=out/'test.c'
source.write_text(r'''
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include "network_backend.c"
static unsigned checks,probe_calls,settings_reads,connect_calls,service_calls,storage_writes,max_status;
static int probe_error,probe_id,probe_status,storage_error,asset_error,connect_error,association_error,association_status,dhcp_error,service_error;
static bool has_key,bad_key,driver_ready,queue_ready,has_interface,has_address;
static bool advance_clock,usb_owner,cleanup_missing,fail_first_recovery_dhcp,drop_first_recovery_dhcp,early_dhcp_only;
static int disconnect_error,disconnect_status;
static unsigned disconnect_calls,dhcp_stops,transport_losses;
static int64_t now_ms,attempt_times[5];
static jmp_buf done;
static struct net_if iface;
struct fake_work_q k_sys_work_q;
static struct k_thread http_thread;
const k_tid_t http_server_tid=&http_thread;
#define CHECK(x) do{assert(x);checks++;}while(0)
int k_mutex_lock(struct k_mutex *m,int n){(void)m;(void)n;return 0;}
int k_mutex_unlock(struct k_mutex *m){(void)m;return 0;}
void k_sem_give(struct k_sem *s){s->value=1;}
void k_sem_reset(struct k_sem *s){s->value=0;}
int64_t k_uptime_get(void){return now_ms;}
int k_sem_take(struct k_sem *s,k_timeout_t timeout){
 if(s==&network_work){
  if(s->value){s->value=0;return 0;}
  if(CONFIG_P4_WIFI_LOSS_RETRY&&advance_clock&&timeout!=K_FOREVER){CHECK(timeout>=0);now_ms+=timeout;return -EAGAIN;}
  longjmp(done,1);
 }
#if CONFIG_P4_WIFI_LOSS_RETRY
 if(s==&disconnected){CHECK(timeout==10);if(!s->value)return -EAGAIN;s->value=0;return 0;}
#endif
 assert(timeout==30);if(s==&association)return association_error;
 assert(s==&dhcp);
 if(dhcp_error||(fail_first_recovery_dhcp&&connect_calls==2))return -EAGAIN;
 if(drop_first_recovery_dhcp&&connect_calls==2){struct wifi_status result={0};struct net_mgmt_event_callback cb={&result};network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);return 0;}
 if(early_dhcp_only)return s->value?0:-EAGAIN;
 network_event(NULL,NET_EVENT_IPV4_DHCP_BOUND,&iface);return 0;
}
int k_thread_stack_space_get(k_tid_t t,size_t *n){(void)t;*n=1024;return 0;}
void net_mgmt_init_event_callback(struct net_mgmt_event_callback *c,void(*fn)(struct net_mgmt_event_callback*,uint64_t,struct net_if*),uint64_t mask){(void)c;(void)fn;assert(mask);}
void net_mgmt_add_event_callback(struct net_mgmt_event_callback *c){(void)c;}
bool device_is_ready(const void *d){(void)d;return driver_ready;}
struct net_if *net_if_get_wifi_sta(void){return has_interface?&iface:NULL;}
int net_if_up(struct net_if *i){assert(i==&iface);return 0;}
void net_dhcpv4_start(struct net_if *i){assert(i==&iface);if(early_dhcp_only)network_event(NULL,NET_EVENT_IPV4_DHCP_BOUND,i);}
void net_dhcpv4_stop(struct net_if *i){assert(i==&iface);dhcp_stops++;}
int net_mgmt(int request,struct net_if *i,void *value,size_t n){
 if(request==NET_REQUEST_WIFI_DISCONNECT){
  assert(i==&iface&&!value&&!n);disconnect_calls++;
  if(disconnect_error)return disconnect_error;
  if(!cleanup_missing){struct wifi_status result={disconnect_status};struct net_mgmt_event_callback cb={&result};network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,i);}
  return 0;
 }
 assert(request==NET_REQUEST_WIFI_CONNECT&&i==&iface&&n==sizeof(struct wifi_connect_req_params));
 struct wifi_connect_req_params *p=value;assert(p->ssid==credential.ssid&&p->psk==credential.password);
 assert(p->ssid_length==8&&p->psk_length==16&&p->security==WIFI_SECURITY_TYPE_PSK);
 assert(connect_calls<5);attempt_times[connect_calls]=now_ms;connect_calls++;
 if(!connect_error&&!association_error){struct wifi_status result={association_status};struct net_mgmt_event_callback cb={&result};network_event(&cb,NET_EVENT_WIFI_CONNECT_RESULT,i);}
 return connect_error;
}
const struct in_addr *net_if_ipv4_get_global_addr(struct net_if *i,int state){static struct in_addr ip;assert(i==&iface&&state==NET_ADDR_PREFERRED);return has_address?&ip:NULL;}
const char *net_addr_ntop(int family,const void *ip,char *out,size_t n){assert(family==AF_INET&&ip);snprintf(out,n,"192.0.2.55");return out;}
int flash_area_open(int id,const struct flash_area **area){static const struct flash_area a={(void*)1,0x1fe0000,0x20000};assert(id==0);*area=&a;return storage_error;}
int flash_get_page_info_by_offs(void *d,size_t off,struct flash_pages_info *p){assert(d&&(off==0x1fe0000));p->size=4096;return 0;}
int nvs_mount(struct nvs_fs *s){assert(s->sector_count==8);return 0;}
int nvs_read(struct nvs_fs *s,int id,void *out,size_t n){
 (void)s;assert(id==0x42&&n==sizeof(struct credentials));settings_reads++;
 if(!has_key)return -ENOENT;
 struct credentials fake={.magic=0x5354424d,.version=1,.sn=8,.pn=16,.security=1};
 if(bad_key)fake.version=2;
 memcpy(fake.ssid,"TESTONLY",8);memcpy(fake.password,"SYNTHETICKEYONLY",16);memcpy(out,&fake,n);return n;
}
int nvs_write(struct nvs_fs *s,int id,const void *p,size_t n){(void)s;(void)id;(void)p;(void)n;storage_writes++;assert(!"No credential write authorized in boot tests");return -EPERM;}
int p4_assets_check(void){return asset_error;}
bool p4_transport_ready(void){return queue_ready;}
int p4_server_start(void){service_calls++;return service_error;}
const char *p4_transport_owner(void){return "USB";}
bool p4_transport_is_usb(void){return usb_owner;}
void p4_transport_network_lost(void){transport_losses++;}
void p4_http_diag_json(char *out,size_t n){snprintf(out,n,"{}");}
static uint8_t last_reply[518];static size_t last_reply_size;
void waitAndSendMessage(int type,int index,int n,char *p){assert(type==214&&!index&&n>0&&n<=518);memcpy(last_reply,p,n);last_reply_size=n;}
int p4_wifi_compat_probe(unsigned *step,int *id,int *status){probe_calls++;*step=284;*id=probe_id;*status=probe_status;return probe_error;}
static void run(void){if(!setjmp(done))network_worker(NULL,NULL,NULL);}
static void safe_status(void){
 char buffer[512];memset(buffer,0,sizeof(buffer));p4_network_status(buffer,sizeof(buffer));
 size_t n=strlen(buffer);CHECK(n>2&&n<sizeof(buffer)-1&&buffer[n-1]=='}');
 CHECK(!strstr(buffer,"TESTONLY")&&!strstr(buffer,"SYNTHETICKEYONLY"));if(n>max_status)max_status=n;
}
static void reset(void){
 memset(&credential,0,sizeof(credential));memset(&storage,0,sizeof(storage));
 storage_ready=key_present=assets_ready=connected=server_started=working=false;
 address[0]=0;phase="initializing";last_error=connect_result=0;
 compat_checked=compat_passed=compat_saved_attempted=false;
 compat_step=0;compat_error=compat_reply_id=compat_reply_status=0;
 network_work.value=association.value=dhcp.value=0;
 probe_calls=settings_reads=connect_calls=service_calls=storage_writes=0;
 probe_error=storage_error=asset_error=connect_error=association_error=association_status=dhcp_error=service_error=0;
 probe_id=540;probe_status=0;has_key=driver_ready=queue_ready=has_interface=has_address=true;
 bad_key=false;
 now_ms=0;advance_clock=cleanup_missing=fail_first_recovery_dhcp=drop_first_recovery_dhcp=early_dhcp_only=false;
 usb_owner=true;disconnect_error=disconnect_status=0;disconnect_calls=dhcp_stops=transport_losses=0;memset(attempt_times,0,sizeof(attempt_times));
#if CONFIG_P4_WIFI_LOSS_RETRY
 memset(&recovery,0,sizeof(recovery));link_epoch=loss_events=0;link_associated=cleanup_waiting=false;cleanup_result=0;disconnected.value=0;
#if CONFIG_P4_WIFI_LOSS_TEST
 loss_test_requested=loss_test_used=false;
#endif
#endif
}
int main(void){
 reset();p4_network_init();CHECK(network_work.value==1&&!settings_reads);run();
 CHECK(probe_calls==1&&compat_checked&&compat_passed&&!working);
 if(CONFIG_P4_WIFI_SAVED_BOOT){
  CHECK(connected&&connect_calls==1&&service_calls==1&&settings_reads==1&&compat_saved_attempted);
  k_sem_give(&network_work);run();CHECK(connect_calls==1&&probe_calls==1&&!network_work.value);
 }else{
  CHECK(!connected&&!connect_calls&&!settings_reads&&!compat_saved_attempted);
  char command[10]={'P','4','S','T',2,1,1,0,0,0};p4_network_message(214,10,command);
  CHECK(last_reply_size==6&&!last_reply[4]);run();CHECK(connected&&connect_calls==1&&settings_reads==1);
 }
 safe_status();CHECK(!storage_writes);
 if(CONFIG_P4_WIFI_SAVED_BOOT)for(unsigned mode=0;mode<13;mode++){
  reset();
  if(mode==0)probe_error=-EREMOTE;
  if(mode==1)probe_id=539;
  if(mode==2)probe_status=1;
  if(mode==3)storage_error=-EIO;
  if(mode==4)has_key=false;
  if(mode==5)asset_error=-EBADMSG;
  if(mode==6)queue_ready=false;
  if(mode==7)driver_ready=false;
  if(mode==8)has_interface=false;
  if(mode==9)connect_error=-EIO;
  if(mode==10)association_error=-EAGAIN;
  if(mode==11)association_status=7;
  if(mode==12)dhcp_error=-EAGAIN;
  p4_network_init();run();CHECK(!connected&&!working&&!storage_writes&&probe_calls==1);
  CHECK(connect_calls==(mode>=9?1u:0u));CHECK(!service_calls);
  if(mode<=2)CHECK(!settings_reads&&!compat_saved_attempted);else CHECK(compat_saved_attempted);
  safe_status();unsigned before=connect_calls;k_sem_give(&network_work);run();CHECK(connect_calls==before&&probe_calls==1);
  char command[10]={'P','4','S','T',2,1,1,0,0,0};p4_network_message(214,10,command);
  CHECK(last_reply_size==6&&last_reply[4]==5&&!network_work.value);
 }
 if(CONFIG_P4_WIFI_SAVED_BOOT){
  reset();bad_key=true;p4_network_init();run();CHECK(!connected&&!working&&!key_present&&!connect_calls);safe_status();
  reset();has_address=false;p4_network_init();run();CHECK(!connected&&!working&&last_error==-EADDRNOTAVAIL&&!service_calls);safe_status();
  reset();service_error=-ENOMEM;p4_network_init();run();CHECK(!connected&&!working&&last_error==-ENOMEM&&service_calls==1);safe_status();
  reset();p4_network_init();run();CHECK(connected);network_event(NULL,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);
  CHECK(!connected);
  if(CONFIG_P4_WIFI_LOSS_RETRY)CHECK(network_work.value);else{CHECK(!network_work.value);CHECK(strstr(phase,"restart"));}safe_status();
 }
#if CONFIG_P4_WIFI_LOSS_RETRY
 /* Global budget survives successes and duplicate events never move a due time. */
 reset();p4_network_init();run();now_ms=100;
 struct wifi_status loss={0};struct net_mgmt_event_callback cb={&loss};
 network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);CHECK(!connected&&!address[0]&&recovery.pending&&recovery.due==5100&&loss_events==1&&transport_losses==1);
 now_ms=200;network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);CHECK(recovery.due==5100&&loss_events==1&&transport_losses==1);run();CHECK(connect_calls==1);
 now_ms=5099;k_sem_give(&network_work);run();CHECK(connect_calls==1&&recovery.used==0);
 now_ms=5100;k_sem_give(&network_work);run();CHECK(connected&&recovery.used==1&&!recovery.active&&connect_calls==2&&service_calls==1&&settings_reads==1&&dhcp_stops==1);
 network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);CHECK(recovery.due==20100);advance_clock=true;run();CHECK(connected&&recovery.used==2&&now_ms==20100);
 network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);CHECK(recovery.due==65100);run();CHECK(connected&&recovery.used==3&&now_ms==65100);
 network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);CHECK(!connected&&!recovery.pending&&!recovery.active);k_sem_give(&network_work);run();CHECK(connect_calls==4&&recovery.used==3);safe_status();
 /* Rejected associations are cleaned up before each subsequent attempt. */
 reset();p4_network_init();run();association_status=7;advance_clock=true;
 network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);run();
 CHECK(connect_calls==4&&disconnect_calls==3&&dhcp_stops==6&&recovery.used==3&&!recovery.pending&&!working&&!connected);
 CHECK(attempt_times[1]==5000&&attempt_times[2]==20000&&attempt_times[3]==65000&&service_calls==1&&settings_reads==1&&!storage_writes);safe_status();
 /* Unknown RPC outcome/missing or rejected cleanup cannot trigger another association. */
 for(unsigned mode=0;mode<3;mode++){
  reset();p4_network_init();run();association_error=-EAGAIN;advance_clock=true;
  if(mode==0)disconnect_error=-EIO;if(mode==1)cleanup_missing=true;if(mode==2)disconnect_status=9;
  network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);run();
  CHECK(connect_calls==2&&disconnect_calls==1&&recovery.used==1&&!recovery.active&&!recovery.pending&&!working&&!connected);
  CHECK(strstr(phase,"unconfirmed"));k_sem_give(&network_work);run();CHECK(connect_calls==2);safe_status();
 }
 reset();p4_network_init();run();asset_error=-EBADMSG;advance_clock=true;network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);run();
 CHECK(connect_calls==1&&!disconnect_calls&&!recovery.active&&!working&&last_error==-EBADMSG);safe_status();
 /* DHCP timeout, link loss during DHCP and a pre-association stale DHCP event. */
 for(unsigned mode=0;mode<3;mode++){
  reset();p4_network_init();run();advance_clock=true;
  if(mode==0)fail_first_recovery_dhcp=true;if(mode==1)drop_first_recovery_dhcp=true;if(mode==2)early_dhcp_only=true;
  network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);run();
  if(mode<2)CHECK(connected&&connect_calls==3&&recovery.used==2&&disconnect_calls==1&&service_calls==1);
  else CHECK(!connected&&connect_calls==4&&recovery.used==3&&disconnect_calls==3);
  CHECK(!storage_writes&&!working);safe_status();
 }
 /* A signed 64-bit uptime beyond the 32-bit wrap preserves the delay. */
 reset();p4_network_init();run();now_ms=INT64_C(4294967290);network_event(&cb,NET_EVENT_WIFI_DISCONNECT_RESULT,&iface);advance_clock=true;run();CHECK(connected&&now_ms==INT64_C(4294972290)&&recovery.used==1);
 /* Diagnostic link-loss trigger is USB-only and at most once per boot. */
 reset();p4_network_init();run();char test[10]={'P','4','S','T',6,1,1,0,0,0};
 usb_owner=false;p4_network_message(214,10,test);CHECK(last_reply[4]!=0&&!network_work.value&&!disconnect_calls);
 memcpy(test,"P4ST",4);test[4]=6;test[5]=1;usb_owner=true;p4_network_message(214,10,test);
 if(CONFIG_P4_WIFI_LOSS_TEST){CHECK(!last_reply[4]&&network_work.value);run();CHECK(disconnect_calls==1&&!connected&&recovery.pending&&!recovery.used);
  memcpy(test,"P4ST",4);test[4]=6;test[5]=1;p4_network_message(214,10,test);CHECK(last_reply[4]==5);advance_clock=true;run();CHECK(connected&&recovery.used==1&&disconnect_calls==1);
 }else CHECK(last_reply[4]!=0&&!network_work.value&&!disconnect_calls);
 char status_command[10]={'P','4','S','T',7,1,1,0,0,0};p4_network_message(214,10,status_command);CHECK(!last_reply[4]&&strstr((char*)last_reply+6,"retry_remaining"));
#endif
 printf("{\"result\":\"PASS\",\"saved_boot_enabled\":%s,\"loss_retry_enabled\":%s,\"loss_test_enabled\":%s,\"checks\":%u,\"largest_status_bytes\":%u,\"credential_writes\":%u,\"physical_tested\":false}\n",CONFIG_P4_WIFI_SAVED_BOOT?"true":"false",CONFIG_P4_WIFI_LOSS_RETRY?"true":"false",CONFIG_P4_WIFI_LOSS_TEST?"true":"false",checks,max_status,storage_writes);
}
''')
reports=[]
for enabled,retry,loss_test in [(0,0,0),(1,0,0),(1,1,0),(1,1,1)]:
 binary=out/('saved-boot-'+str(enabled)+'-retry-'+str(retry)+'-test-'+str(loss_test))
 flags=['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
  '-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all',
  '-DCONFIG_P4_WIFI_COMPAT_DIAGNOSTIC=1','-DCONFIG_P4_WIFI_SAVED_BOOT='+str(enabled),
  '-DCONFIG_P4_WIFI_LOSS_RETRY='+str(retry),'-DCONFIG_P4_WIFI_LOSS_TEST='+str(loss_test),
  '-I'+str(inc),'-I'+str(repo/'boards/waveshare_esp32p4_wifi6/zephyr/src')]
 subprocess.run(flags+[str(source),'-o',str(binary)],check=True)
 run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=20,
  env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
 if run.returncode:print(run.stderr)
 run.check_returncode();reports.append(json.loads(run.stdout))
report={'result':'PASS','scope':'actual network_backend worker; synthetic settings/radio only',
 'sanitizers':['address','undefined'],'physical_tested':False,'modes':reports}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
