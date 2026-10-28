/* SPDX-License-Identifier: MPL-2.0 */
/* Station-only target; AP authorization was revoked on 2026-10-26. */
#include "network_backend.h"
#include "hosted_server.h"
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
#include "c6_trace.h"
#endif
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
#include "http_diagnostics.h"
#endif
#include "vm/interp.h"
#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/dhcpv4.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/kvss/nvs.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/sys/byteorder.h>
#include <string.h>
#include <stdio.h>
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
#include "wifi_retry.h"
static struct p4_wifi_retry recovery;
static uint32_t link_epoch;
static unsigned loss_events;
static bool link_associated,cleanup_waiting;
static int cleanup_result;
K_SEM_DEFINE(disconnected,0,1);
#if defined(CONFIG_P4_WIFI_LOSS_TEST) && CONFIG_P4_WIFI_LOSS_TEST
static bool loss_test_requested,loss_test_used;
#endif
#endif
struct credentials {uint32_t magic;uint8_t version,sn,pn,security;uint8_t ssid[32],password[64];};
static struct credentials credential;
static struct nvs_fs storage;
static bool storage_ready,key_present,assets_ready,connected,server_started,working;
static char address[NET_IPV4_ADDR_LEN];
static const char *phase="initializing";
static int last_error,connect_result;
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
extern int p4_wifi_compat_probe(unsigned *,int *,int *);
static bool compat_checked,compat_passed,compat_saved_attempted;
static unsigned compat_step;
static int compat_error,compat_reply_id,compat_reply_status;
#endif
static struct net_mgmt_event_callback events,dhcp_events;
K_MUTEX_DEFINE(state_lock);
K_SEM_DEFINE(network_work,0,1);
K_SEM_DEFINE(association,0,1);
K_SEM_DEFINE(dhcp,0,1);
#if defined(CONFIG_P4_WIFI_LOW_LATENCY)
#include "wifi_latency_policy.h"
static struct p4_latency_policy latency_policy;
static int latency_read_ps(void *context,int *enabled,int *mode)
{
 struct wifi_ps_config config={0};
 int error=net_mgmt(NET_REQUEST_WIFI_PS_CONFIG,context,&config,sizeof(config));
 if(!error){*enabled=config.ps_params.enabled==WIFI_PS_ENABLED;*mode=config.ps_params.mode;}
 return error;
}
static int latency_disable_ps(void *context)
{
 struct wifi_ps_params parameters={.type=WIFI_PS_PARAM_STATE,.enabled=WIFI_PS_DISABLED,.mode=WIFI_PS_MODE_LEGACY};
 return net_mgmt(NET_REQUEST_WIFI_PS,context,&parameters,sizeof(parameters));
}
static void apply_latency_policy(struct net_if *iface)
{
 k_mutex_lock(&state_lock,K_FOREVER);
 bool run=!latency_policy.attempted;
 if(run)latency_policy.attempted=true;
 k_mutex_unlock(&state_lock);
 if(!run)return;
 struct p4_latency_policy result={0};
 (void)p4_latency_policy_run(&result,iface,latency_read_ps,latency_disable_ps);
 k_mutex_lock(&state_lock,K_FOREVER);latency_policy=result;k_mutex_unlock(&state_lock);
}
#endif
static void wipe(void *p,size_t n){volatile unsigned char *b=p;while(n--)*b++=0;}
static void state(const char *s,int e){k_mutex_lock(&state_lock,K_FOREVER);phase=s;last_error=e;k_mutex_unlock(&state_lock);}
static bool valid(const struct credentials *c)
{
 if(c->magic!=0x5354424d||c->version!=1||c->security!=1||!c->sn||c->sn>32||c->pn<8||c->pn>64)return false;
 if(memchr(c->ssid,0,c->sn)||memchr(c->password,0,c->pn))return false;
 if(c->pn==64)for(unsigned i=0;i<64;i++){unsigned char v=c->password[i];if(!((v>='0'&&v<='9')||(v>='a'&&v<='f')||(v>='A'&&v<='F')))return false;}
 return true;
}
static int storage_init(void)
{
 const struct flash_area *area;int e=flash_area_open(FIXED_PARTITION_ID(p4_settings),&area);if(e)return e;
 struct flash_pages_info page;e=flash_get_page_info_by_offs(area->fa_dev,area->fa_off,&page);if(e)return e;
 storage.flash_device=area->fa_dev;storage.offset=area->fa_off;storage.sector_size=page.size;storage.sector_count=MIN(area->fa_size/page.size,8);
 if(storage.sector_count<2)return -ENOSPC;e=nvs_mount(&storage);if(e)return e;storage_ready=true;
 struct credentials saved={0};e=nvs_read(&storage,0x42,&saved,sizeof(saved));
 if(e==(int)sizeof(saved)&&valid(&saved)){credential=saved;key_present=true;}
 wipe(&saved,sizeof(saved));return 0;
}
static void network_event(struct net_mgmt_event_callback *cb,uint64_t event,struct net_if *iface)
{
 (void)iface;
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
 if(iface!=net_if_get_wifi_sta())return;
 bool wake=false,lost=false;
 k_mutex_lock(&state_lock,K_FOREVER);
 if(event==NET_EVENT_WIFI_CONNECT_RESULT){
  connect_result=cb&&cb->info?((const struct wifi_status *)cb->info)->status:-EIO;
  link_associated=connect_result==0&&!cleanup_waiting;
  if(cleanup_waiting&&cb&&cb->info&&connect_result){cleanup_result=0;k_sem_give(&disconnected);}
  k_sem_give(&association);
 }
 if(event==NET_EVENT_IPV4_DHCP_BOUND&&working&&link_associated&&!cleanup_waiting)k_sem_give(&dhcp);
 if(event==NET_EVENT_WIFI_DISCONNECT_RESULT){
  lost=connected;connected=false;link_associated=false;address[0]=0;link_epoch++;
  if(cleanup_waiting){cleanup_result=cb&&cb->info?((const struct wifi_status *)cb->info)->status:-EIO;k_sem_give(&disconnected);}
  else if(lost){
   loss_events++;
   bool queued=recovery.pending||p4_retry_schedule(&recovery,k_uptime_get());
   phase=queued?"link lost; retry backoff":"retry budget exhausted; restart required";
   last_error=0;wake=queued;
  }
  if(working&&!cleanup_waiting){connect_result=-ENETDOWN;k_sem_give(&association);k_sem_give(&dhcp);}
 }
 k_mutex_unlock(&state_lock);
 if(lost)p4_transport_network_lost();
 if(wake)k_sem_give(&network_work);
#else
 if(event==NET_EVENT_WIFI_CONNECT_RESULT){connect_result=cb->info?((const struct wifi_status *)cb->info)->status:-EIO;k_sem_give(&association);}
 if(event==NET_EVENT_IPV4_DHCP_BOUND)k_sem_give(&dhcp);
 if(event==NET_EVENT_WIFI_DISCONNECT_RESULT){k_mutex_lock(&state_lock,K_FOREVER);connected=false;address[0]=0;phase=IS_ENABLED(CONFIG_P4_WIFI_SAVED_BOOT)?"station disconnected; saved boot needs a restart":"station disconnected; explicit retry available";k_mutex_unlock(&state_lock);}
#endif
}
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
static k_timeout_t retry_wait(void)
{
 k_mutex_lock(&state_lock,K_FOREVER);
 int64_t left=recovery.pending?MAX(0,recovery.due-k_uptime_get()):-1;
 k_mutex_unlock(&state_lock);return left<0?K_FOREVER:K_MSEC(left);
}
static int retry_quiesce(struct net_if *iface)
{
 /* An RPC acknowledgement alone is not evidence of link quiescence. Do not
  * repeat association unless a disconnect/failure event confirms cleanup. */
 net_dhcpv4_stop(iface);k_sem_reset(&disconnected);
 k_mutex_lock(&state_lock,K_FOREVER);cleanup_waiting=true;cleanup_result=-EINPROGRESS;link_associated=false;link_epoch++;k_mutex_unlock(&state_lock);
 int e=net_mgmt(NET_REQUEST_WIFI_DISCONNECT,iface,NULL,0);
 if(!e){if(k_sem_take(&disconnected,K_SECONDS(10)))e=-ETIMEDOUT;
  else {k_mutex_lock(&state_lock,K_FOREVER);e=cleanup_result;k_mutex_unlock(&state_lock);}}
 k_mutex_lock(&state_lock,K_FOREVER);cleanup_waiting=false;k_mutex_unlock(&state_lock);return e;
}
#endif
static void network_worker(void *a,void *b,void *c)
{
 (void)a;(void)b;(void)c;
 for(;;){
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
  k_sem_take(&network_work,retry_wait());
  struct net_if *retry_iface=NULL;
  bool attempt_succeeded=false,retryable=false;
  k_mutex_lock(&state_lock,K_FOREVER);
#if defined(CONFIG_P4_WIFI_LOSS_TEST) && CONFIG_P4_WIFI_LOSS_TEST
  bool test_loss=loss_test_requested;loss_test_requested=false;
  if(test_loss){
   working=true;phase="USB one-shot link-loss test";k_mutex_unlock(&state_lock);
   struct net_if *iface=net_if_get_wifi_sta();
   int e=iface?net_mgmt(NET_REQUEST_WIFI_DISCONNECT,iface,NULL,0):-ENODEV;
   if(e)state("test disconnect failed; no repeat",e);
   k_mutex_lock(&state_lock,K_FOREVER);working=false;k_mutex_unlock(&state_lock);continue;
  }
#endif
  bool recovering=p4_retry_claim(&recovery,k_uptime_get());
  k_mutex_unlock(&state_lock);
#else
  k_sem_take(&network_work,K_FOREVER);
#endif
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
  bool saved_boot=false;
  if(!compat_checked){
   k_mutex_lock(&state_lock,K_FOREVER);working=true;k_mutex_unlock(&state_lock);state("synthetic RAM-only C6 diagnostic; no association",0);
   unsigned step=0;int reply=0,status=-1;
   int e=p4_wifi_compat_probe(&step,&reply,&status);
   k_mutex_lock(&state_lock,K_FOREVER);
   compat_step=step;compat_error=e;compat_reply_id=reply;compat_reply_status=status;
   compat_passed=e==0 && reply==540 && status==0;compat_checked=true;
   saved_boot=IS_ENABLED(CONFIG_P4_WIFI_SAVED_BOOT)&&compat_passed;
   compat_saved_attempted=saved_boot;working=saved_boot;
   phase=!compat_passed?"synthetic diagnostic failed; association blocked":saved_boot?
    "synthetic response540 passed; saved boot starting":"synthetic response540 passed; explicit saved connection available";
   last_error=e;k_mutex_unlock(&state_lock);if(!saved_boot)continue;
  }
  /* Automatic mode owns exactly this first wake, including failure paths.
   * Manual diagnostic mode still consumes its explicit operation-2 wake. */
  if(!compat_passed||(IS_ENABLED(CONFIG_P4_WIFI_SAVED_BOOT)&&!saved_boot
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
   &&!recovering
#endif
  ))continue;
  if(!storage_ready){int e=storage_init();if(e){state("saved settings unavailable",e);goto done;}}
#endif
  k_mutex_lock(&state_lock,K_FOREVER);bool ready=key_present&&!connected;working=ready;k_mutex_unlock(&state_lock);
  if(!ready){if(!key_present)state("no saved station credentials; USB recovery available",0);continue;}
  state("checking editor assets",0);int e=p4_assets_check();k_mutex_lock(&state_lock,K_FOREVER);assets_ready=e==0;k_mutex_unlock(&state_lock);
  if(e){state("editor assets missing or invalid",e);goto done;}
  if(!p4_transport_ready()){state("WebSocket queue allocation failed",-ENOMEM);goto done;}
  if(!device_is_ready(DEVICE_DT_GET(DT_NODELABEL(p4_wifi)))){state("Wi-Fi driver unavailable",-ENODEV);goto done;}
  struct net_if *iface=net_if_get_wifi_sta();if(!iface){state("station interface unavailable",-ENODEV);goto done;}
  k_sem_reset(&association);k_sem_reset(&dhcp);connect_result=-EINPROGRESS;
  e=net_if_up(iface);if(e&&e!=-EALREADY){state("station interface start failed",e);goto done;}
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
  retry_iface=iface;retryable=true;
  if(recovering)net_dhcpv4_stop(iface);
  k_mutex_lock(&state_lock,K_FOREVER);uint32_t attempt_epoch=link_epoch;link_associated=false;k_mutex_unlock(&state_lock);
#endif
  net_dhcpv4_start(iface);
  struct wifi_connect_req_params params={0};
  /* Native owned buffers remain valid through asynchronous association. */
  params.ssid=credential.ssid;params.ssid_length=credential.sn;params.psk=credential.password;params.psk_length=credential.pn;
  params.channel=WIFI_CHANNEL_ANY;params.band=WIFI_FREQ_BAND_2_4_GHZ;params.security=WIFI_SECURITY_TYPE_PSK;
  state("connecting approved station network",0);e=net_mgmt(NET_REQUEST_WIFI_CONNECT,iface,&params,sizeof(params));
  if(e){state("station configuration/start failed",e);goto done;}
  if(k_sem_take(&association,K_SECONDS(30))){state("station association timed out",-ETIMEDOUT);goto done;}
  if(connect_result){state("station association rejected",connect_result);goto done;}
  state("awaiting station DHCP",0);
  if(k_sem_take(&dhcp,K_SECONDS(30))){state("station DHCP timed out",-ETIMEDOUT);goto done;}
  const struct in_addr *ip=net_if_ipv4_get_global_addr(iface,NET_ADDR_PREFERRED);
  if(!ip){state("station address unavailable",-EADDRNOTAVAIL);goto done;}
  char next_address[NET_IPV4_ADDR_LEN];net_addr_ntop(AF_INET,ip,next_address,sizeof(next_address));
  if(!server_started){e=p4_server_start();if(e){state("local editor service failed",e);goto done;}server_started=true;}
  k_mutex_lock(&state_lock,K_FOREVER);
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
  if(attempt_epoch!=link_epoch||!link_associated){address[0]=0;phase="link changed during connection";last_error=-ENETDOWN;k_mutex_unlock(&state_lock);goto done;}
  attempt_succeeded=true;p4_retry_halt(&recovery);
#endif
  memcpy(address,next_address,sizeof(address));connected=true;phase="ready";last_error=0;k_mutex_unlock(&state_lock);
#if defined(CONFIG_P4_WIFI_LOW_LATENCY)
  apply_latency_policy(iface);
#endif
 done:
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
  if(recovering&&!attempt_succeeded&&retryable){
   int cleanup=retry_quiesce(retry_iface);
   k_mutex_lock(&state_lock,K_FOREVER);
   if(!cleanup){
    bool queued=p4_retry_schedule(&recovery,k_uptime_get());
    phase=queued?"recovery failed; retry backoff":"retry budget exhausted; restart required";
   }else{p4_retry_halt(&recovery);phase="retry cleanup unconfirmed; restart required";last_error=cleanup;}
   k_mutex_unlock(&state_lock);
  }
  else if(recovering&&!attempt_succeeded){k_mutex_lock(&state_lock,K_FOREVER);p4_retry_halt(&recovery);k_mutex_unlock(&state_lock);}
#endif
  k_mutex_lock(&state_lock,K_FOREVER);working=false;k_mutex_unlock(&state_lock);
 }
}
K_THREAD_DEFINE(p4_station_worker,12288,network_worker,NULL,NULL,NULL,8,0,0);
void p4_network_init(void)
{
 /* Different event layers/codes require distinct callbacks in Zephyr. */
 net_mgmt_init_event_callback(&events,network_event,NET_EVENT_WIFI_CONNECT_RESULT|NET_EVENT_WIFI_DISCONNECT_RESULT);
 net_mgmt_add_event_callback(&events);
 net_mgmt_init_event_callback(&dhcp_events,network_event,NET_EVENT_IPV4_DHCP_BOUND);
 net_mgmt_add_event_callback(&dhcp_events);
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
 state("starting one synthetic C6 diagnostic",0);k_sem_give(&network_work);return;
#endif
 int e=storage_init();if(e){state("station settings storage unavailable",e);return;}
 state(key_present?"saved station credentials available":"awaiting approved USB station provisioning",0);
 if(key_present)k_sem_give(&network_work);
}
void p4_network_address(char *out,size_t n){k_mutex_lock(&state_lock,K_FOREVER);snprintf(out,n,"%s",address);k_mutex_unlock(&state_lock);}
void p4_network_status(char *out,size_t n)
{
 k_mutex_lock(&state_lock,K_FOREVER);
 snprintf(out,n,"{\"target\":\"native Zephyr station-hosted\",\"station_protocol\":1,\"phase\":\"%s\",\"error\":%d,\"wifi_driver_ready\":%s,\"assets_valid\":%s,\"credentials_saved\":%s,\"station_connected\":%s,\"address\":\"%s\",\"ap_running\":false,\"internet_sharing\":false,\"controller\":\"%s\"}",phase,last_error,device_is_ready(DEVICE_DT_GET(DT_NODELABEL(p4_wifi)))?"true":"false",assets_ready?"true":"false",key_present?"true":"false",connected?"true":"false",address,p4_transport_owner());
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
 size_t used=strlen(out);
 if(used && out[used-1]=='}')snprintf(out+used-1,n-used+1,",\"compat_checked\":%s,\"compat_passed\":%s,\"compat_step\":%u,\"compat_error\":%d,\"synthetic_reply_id\":%d,\"synthetic_reply_status\":%d}",compat_checked?"true":"false",compat_passed?"true":"false",compat_step,compat_error,compat_reply_id,compat_reply_status);
#endif
 k_mutex_unlock(&state_lock);
}
void p4_network_message(int type,int bytes,char *body)
{
 if(type!=214||bytes<10||memcmp(body,"P4ST",4))return;
 uint8_t *p=(uint8_t *)body;unsigned op=p[4];uint8_t reply[518]={0};sys_put_le32(sys_get_le32(p+6),reply);reply[4]=1;reply[5]=op;unsigned n=6;
#if defined(CONFIG_P4_WIFI_LOSS_TEST) && CONFIG_P4_WIFI_LOSS_TEST
 bool wake_loss_test=false;
#endif
 if(op==0&&bytes==10&&p[5]==1){p4_network_status((char *)reply+6,sizeof(reply)-6);n+=strlen((char *)reply+6);reply[4]=0;}
#if defined(CONFIG_P4_WIFI_LOW_LATENCY)
 else if(op==11&&bytes==10&&p[5]==1){
  k_mutex_lock(&state_lock,K_FOREVER);struct p4_latency_policy copy=latency_policy;k_mutex_unlock(&state_lock);
  snprintf((char*)reply+6,sizeof(reply)-6,"{\"attempted\":%s,\"complete\":%s,\"set_requested\":%s,\"confirmed\":%s,\"before_enabled\":%d,\"before_mode\":%d,\"set_error\":%d,\"after_enabled\":%d,\"after_mode\":%d,\"error\":%d}",copy.attempted?"true":"false",copy.complete?"true":"false",copy.set_requested?"true":"false",copy.confirmed?"true":"false",copy.before_enabled,copy.before_mode,copy.set_error,copy.after_enabled,copy.after_mode,copy.error);
  n+=strlen((char*)reply+6);reply[4]=0;
 }
#endif
#if defined(CONFIG_P4_WIFI_LATENCY_DIAGNOSTIC)
 else if(op==12&&bytes==10&&p[5]==1&&p4_transport_is_usb()){
  p4_asset_timing_json((char*)reply+6,sizeof(reply)-6);n+=strlen((char*)reply+6);reply[4]=0;
 }
 else if(op==8&&bytes==10&&p[5]==1){
  p4_transport_latency_json((char*)reply+6,sizeof(reply)-6);n+=strlen((char*)reply+6);reply[4]=0;
 }
 else if(op==10&&bytes==10&&p[5]==1&&p4_transport_is_usb()){
  p4_c6_trace_json(-1,(char*)reply+6,sizeof(reply)-6);n+=strlen((char*)reply+6);reply[4]=0;
 }
 else if(op==9&&bytes==10&&p[5]==1&&p4_transport_is_usb()){
  static unsigned reads;
  if(reads<3){
   reads++;struct wifi_ps_config config={0};struct net_if *iface=net_if_get_wifi_sta();
   uint32_t began=k_uptime_get_32();
   int error=iface?net_mgmt(NET_REQUEST_WIFI_PS_CONFIG,iface,&config,sizeof(config)):-ENODEV;
   snprintf((char*)reply+6,sizeof(reply)-6,"{\"read_only\":true,\"query_count\":%u,\"error\":%d,\"enabled\":%d,\"mode\":%d,\"query_ms\":%u}",reads,error,error?-1:(int)config.ps_params.enabled,error?-1:(int)config.ps_params.mode,k_uptime_get_32()-began);
   n+=strlen((char*)reply+6);reply[4]=0;
  }else reply[4]=5;
 }
#endif
#if defined(CONFIG_P4_WIFI_LOSS_RETRY) && CONFIG_P4_WIFI_LOSS_RETRY
 else if(op==7&&bytes==10&&p[5]==1){
  k_mutex_lock(&state_lock,K_FOREVER);
  snprintf((char*)reply+6,sizeof(reply)-6,"{\"retry_used\":%u,\"retry_remaining\":%u,\"retry_active\":%s,\"retry_pending\":%s,\"wait_ms\":%u,\"loss_events\":%u,\"test_enabled\":%s}",recovery.used,3-recovery.used,recovery.active?"true":"false",recovery.pending?"true":"false",(unsigned)(recovery.pending?MAX(0,recovery.due-k_uptime_get()):0),loss_events,IS_ENABLED(CONFIG_P4_WIFI_LOSS_TEST)?"true":"false");
  k_mutex_unlock(&state_lock);n+=strlen((char*)reply+6);reply[4]=0;
 }
#if defined(CONFIG_P4_WIFI_LOSS_TEST) && CONFIG_P4_WIFI_LOSS_TEST
 else if(op==6&&bytes==10&&p[5]==1&&p4_transport_is_usb()){
  k_mutex_lock(&state_lock,K_FOREVER);
  bool allowed=connected&&!working&&!recovery.active&&!loss_test_used;
  if(allowed){loss_test_used=wake_loss_test=true;reply[4]=0;}
  else reply[4]=5;
  k_mutex_unlock(&state_lock);
  /* The worker runs only after this acknowledgement has been sent below. */
 }
#endif
#endif
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
 else if(op==5&&bytes==10&&p[5]==1){p4_http_diag_json((char*)reply+6,sizeof(reply)-6);n+=strlen((char*)reply+6);reply[4]=0;}
 else if(op==4&&bytes==10&&p[5]==1){
  extern const k_tid_t http_server_tid;
  size_t system_free=0,station_free=0,http_free=0;
  int se=k_thread_stack_space_get(&k_sys_work_q.thread,&system_free);
  int ne=k_thread_stack_space_get(p4_station_worker,&station_free);
  int he=k_thread_stack_space_get(http_server_tid,&http_free);
  char ip[NET_IPV4_ADDR_LEN]="";struct net_if *iface=net_if_get_wifi_sta();
  const struct in_addr *addr=iface?net_if_ipv4_get_global_addr(iface,NET_ADDR_PREFERRED):NULL;
  if(addr)net_addr_ntop(AF_INET,addr,ip,sizeof(ip));
  snprintf((char*)reply+6,sizeof(reply)-6,"{\"system_work_unused\":%u,\"system_work_measure_error\":%d,\"station_work_unused\":%u,\"station_work_measure_error\":%d,\"http_work_unused\":%u,\"http_work_measure_error\":%d,\"dhcp_address\":\"%s\"}",(unsigned)system_free,se,(unsigned)station_free,ne,(unsigned)http_free,he,ip);
  n+=strlen((char*)reply+6);reply[4]=0;
 }
#endif
 else if(op==1&&IS_ENABLED(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)){reply[4]=4;}
 else if(op==1&&bytes>=14&&p[5]==1&&p4_transport_is_usb()){
  struct credentials next={0},check={0};unsigned sn=p[10],pn=p[11];next.magic=0x5354424d;next.version=1;next.security=1;next.sn=sn;next.pn=pn;
  if(sn<=32&&pn<=64&&bytes==(int)(14+sn+pn)&&p[12]==1&&p[13]==1){
   memcpy(next.ssid,p+14,sn);memcpy(next.password,p+14+sn,pn);
   if(valid(&next)){
    k_mutex_lock(&state_lock,K_FOREVER);
    if(working||connected)reply[4]=5;
    else if(!storage_ready)reply[4]=2;
    else if(key_present&&memcmp(&next,&credential,sizeof(next)))reply[4]=3;
    else {
     int e=nvs_write(&storage,0x42,&next,sizeof(next));
     if(e==(int)sizeof(next)&&nvs_read(&storage,0x42,&check,sizeof(check))==(int)sizeof(check)&&!memcmp(&next,&check,sizeof(next))){credential=next;key_present=true;reply[4]=0;}else reply[4]=2;
    }
    k_mutex_unlock(&state_lock);
   }
  }
  wipe(&next,sizeof(next));wipe(&check,sizeof(check));if(!reply[4])k_sem_give(&network_work);
 }else if(op==2&&bytes==10&&p[5]==1&&p4_transport_is_usb()){
  k_mutex_lock(&state_lock,K_FOREVER);bool retry=key_present&&!working&&!connected;
#if defined(CONFIG_P4_WIFI_COMPAT_DIAGNOSTIC)
   retry=compat_checked&&compat_passed&&!compat_saved_attempted&&!working&&!connected;
   if(retry)compat_saved_attempted=true;
#endif
k_mutex_unlock(&state_lock);if(retry){k_sem_give(&network_work);reply[4]=0;}else reply[4]=5;
 }
 wipe(body,bytes);waitAndSendMessage(214,0,n,(char *)reply);wipe(reply,sizeof(reply));
#if defined(CONFIG_P4_WIFI_LOSS_TEST) && CONFIG_P4_WIFI_LOSS_TEST
 if(wake_loss_test){k_mutex_lock(&state_lock,K_FOREVER);loss_test_requested=true;k_mutex_unlock(&state_lock);k_sem_give(&network_work);}
#endif
}
