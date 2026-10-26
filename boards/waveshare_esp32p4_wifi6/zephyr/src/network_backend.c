/* SPDX-License-Identifier: MPL-2.0 */
/* Station-only target; AP authorization was revoked on 2026-10-26. */
#include "network_backend.h"
#include "hosted_server.h"
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
struct credentials {uint32_t magic;uint8_t version,sn,pn,security;uint8_t ssid[32],password[64];};
static struct credentials credential;
static struct nvs_fs storage;
static bool storage_ready,key_present,assets_ready,connected,server_started,working;
static char address[NET_IPV4_ADDR_LEN];
static const char *phase="initializing";
static int last_error,connect_result;
static struct net_mgmt_event_callback events;
K_MUTEX_DEFINE(state_lock);
K_SEM_DEFINE(network_work,0,1);
K_SEM_DEFINE(association,0,1);
K_SEM_DEFINE(dhcp,0,1);
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
 if(event==NET_EVENT_WIFI_CONNECT_RESULT){connect_result=cb->info?((const struct wifi_status *)cb->info)->status:-EIO;k_sem_give(&association);}
 if(event==NET_EVENT_IPV4_DHCP_BOUND)k_sem_give(&dhcp);
 if(event==NET_EVENT_WIFI_DISCONNECT_RESULT){k_mutex_lock(&state_lock,K_FOREVER);connected=false;address[0]=0;phase="station disconnected; explicit retry available";k_mutex_unlock(&state_lock);}
}
static void network_worker(void *a,void *b,void *c)
{
 (void)a;(void)b;(void)c;
 for(;;){
  k_sem_take(&network_work,K_FOREVER);k_mutex_lock(&state_lock,K_FOREVER);bool ready=key_present&&!connected;working=ready;k_mutex_unlock(&state_lock);if(!ready)continue;
  state("checking editor assets",0);int e=p4_assets_check();k_mutex_lock(&state_lock,K_FOREVER);assets_ready=e==0;k_mutex_unlock(&state_lock);
  if(e){state("editor assets missing or invalid",e);goto done;}
  if(!p4_transport_ready()){state("WebSocket queue allocation failed",-ENOMEM);goto done;}
  if(!device_is_ready(DEVICE_DT_GET(DT_NODELABEL(p4_wifi)))){state("Wi-Fi driver unavailable",-ENODEV);goto done;}
  struct net_if *iface=net_if_get_wifi_sta();if(!iface){state("station interface unavailable",-ENODEV);goto done;}
  k_sem_reset(&association);k_sem_reset(&dhcp);connect_result=-EINPROGRESS;
  e=net_if_up(iface);if(e&&e!=-EALREADY){state("station interface start failed",e);goto done;}
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
  k_mutex_lock(&state_lock,K_FOREVER);net_addr_ntop(AF_INET,ip,address,sizeof(address));k_mutex_unlock(&state_lock);
  if(!server_started){e=p4_server_start();if(e){state("local editor service failed",e);goto done;}server_started=true;}
  k_mutex_lock(&state_lock,K_FOREVER);connected=true;phase="ready";last_error=0;k_mutex_unlock(&state_lock);
 done:
  k_mutex_lock(&state_lock,K_FOREVER);working=false;k_mutex_unlock(&state_lock);
 }
}
K_THREAD_DEFINE(p4_station_worker,12288,network_worker,NULL,NULL,NULL,8,0,0);
void p4_network_init(void)
{
 net_mgmt_init_event_callback(&events,network_event,NET_EVENT_WIFI_CONNECT_RESULT|NET_EVENT_WIFI_DISCONNECT_RESULT|NET_EVENT_IPV4_DHCP_BOUND);net_mgmt_add_event_callback(&events);
 int e=storage_init();if(e){state("station settings storage unavailable",e);return;}
 state(key_present?"saved station credentials available":"awaiting approved USB station provisioning",0);
 if(key_present)k_sem_give(&network_work);
}
void p4_network_address(char *out,size_t n){k_mutex_lock(&state_lock,K_FOREVER);snprintf(out,n,"%s",address);k_mutex_unlock(&state_lock);}
void p4_network_status(char *out,size_t n)
{
 k_mutex_lock(&state_lock,K_FOREVER);
 snprintf(out,n,"{\"target\":\"native Zephyr station-hosted\",\"station_protocol\":1,\"phase\":\"%s\",\"error\":%d,\"wifi_driver_ready\":%s,\"assets_valid\":%s,\"credentials_saved\":%s,\"station_connected\":%s,\"address\":\"%s\",\"ap_running\":false,\"internet_sharing\":false,\"controller\":\"%s\"}",phase,last_error,device_is_ready(DEVICE_DT_GET(DT_NODELABEL(p4_wifi)))?"true":"false",assets_ready?"true":"false",key_present?"true":"false",connected?"true":"false",address,p4_transport_owner());
 k_mutex_unlock(&state_lock);
}
void p4_network_message(int type,int bytes,char *body)
{
 if(type!=214||bytes<10||memcmp(body,"P4ST",4))return;
 uint8_t *p=(uint8_t *)body;unsigned op=p[4];uint8_t reply[518]={0};sys_put_le32(sys_get_le32(p+6),reply);reply[4]=1;reply[5]=op;unsigned n=6;
 if(op==0&&bytes==10&&p[5]==1){p4_network_status((char *)reply+6,sizeof(reply)-6);n+=strlen((char *)reply+6);reply[4]=0;}
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
  k_mutex_lock(&state_lock,K_FOREVER);bool retry=key_present&&!working&&!connected;k_mutex_unlock(&state_lock);if(retry){k_sem_give(&network_work);reply[4]=0;}else reply[4]=5;
 }
 wipe(body,bytes);waitAndSendMessage(214,0,n,(char *)reply);wipe(reply,sizeof(reply));
}
