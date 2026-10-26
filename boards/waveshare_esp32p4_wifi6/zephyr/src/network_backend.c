/* SPDX-License-Identifier: MPL-2.0 */
#include "network_backend.h"
#include "hosted_server.h"
#include "vm/interp.h"
#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/dhcpv4_server.h>
#include <zephyr/net/socket.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/kvss/nvs.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/sys/byteorder.h>
#include <string.h>
#include <stdio.h>
static const char ssid[]="MicroBlocks-P4";
struct credentials {uint32_t magic;uint8_t version;char password[17];};
static struct credentials credential;
static struct nvs_fs storage;
static bool storage_ready,key_present,assets_ready,ap_running;
static const char *phase="initializing";
static int last_error;
K_MUTEX_DEFINE(state_lock);
K_SEM_DEFINE(network_work,0,1);
static void wipe(void *p,size_t n){volatile unsigned char *b=p;while(n--)*b++=0;}
static void state(const char *text,int error){k_mutex_lock(&state_lock,K_FOREVER);phase=text;last_error=error;k_mutex_unlock(&state_lock);}
static bool password_valid(const char *s)
{
 for(unsigned i=0;i<16;i++){char c=s[i];if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-'||c=='_'))return false;}
 return s[16]==0;
}
static int storage_init(void)
{
 const struct flash_area *area;int err=flash_area_open(FIXED_PARTITION_ID(p4_settings),&area);if(err)return err;
 struct flash_pages_info page;err=flash_get_page_info_by_offs(area->fa_dev,area->fa_off,&page);if(err)return err;
 storage.flash_device=area->fa_dev;storage.offset=area->fa_off;storage.sector_size=page.size;
 storage.sector_count=MIN(area->fa_size/page.size,8);if(storage.sector_count<2)return -ENOSPC;
 err=nvs_mount(&storage);if(err)return err;
 storage_ready=true;struct credentials saved={0};
 err=nvs_read(&storage,0x41,&saved,sizeof(saved));
 if(err==(int)sizeof(saved)&&saved.magic==0x5034424d && saved.version==1 && password_valid(saved.password)){credential=saved;key_present=true;}
 wipe(&saved,sizeof(saved));return 0;
}
static void network_worker(void *a,void *b,void *c)
{
 (void)a;(void)b;(void)c;
 for(;;){
  k_sem_take(&network_work,K_FOREVER);if(ap_running)continue;
  state("checking editor assets",0);int err=p4_assets_check();
  k_mutex_lock(&state_lock,K_FOREVER);assets_ready=err==0;k_mutex_unlock(&state_lock);
  if(err){state("editor assets missing or invalid",err);continue;}
  if(!p4_transport_ready()){state("WebSocket queue allocation failed",-ENOMEM);continue;}
  if(!device_is_ready(DEVICE_DT_GET(DT_NODELABEL(p4_wifi)))){state("Wi-Fi driver unavailable",-(int)DEVICE_DT_GET(DT_NODELABEL(p4_wifi))->state->init_res);continue;}
  char password[17]={0};k_mutex_lock(&state_lock,K_FOREVER);bool have=key_present;if(have)memcpy(password,credential.password,sizeof(password));k_mutex_unlock(&state_lock);
  if(!have){state("awaiting approved USB credential provisioning",0);continue;}
  struct net_if *iface=net_if_get_wifi_sap();if(!iface){wipe(password,sizeof(password));state("AP interface unavailable",-ENODEV);continue;}
  struct in_addr address,mask,pool;
  net_addr_pton(AF_INET,"192.168.4.1",&address);net_addr_pton(AF_INET,"255.255.255.0",&mask);net_addr_pton(AF_INET,"192.168.4.10",&pool);
  if(!net_if_ipv4_addr_add(iface,&address,NET_ADDR_MANUAL,0)){wipe(password,sizeof(password));state("AP address allocation failed",-ENOMEM);continue;}
  if(!net_if_ipv4_set_netmask_by_addr(iface,&address,&mask)){wipe(password,sizeof(password));state("AP netmask allocation failed",-ENOMEM);continue;}
  err=net_if_up(iface);
  if(err && err!=-EALREADY){wipe(password,sizeof(password));state("AP interface start failed",err);continue;}
  struct wifi_connect_req_params params={0};params.ssid=(const uint8_t *)ssid;params.ssid_length=sizeof(ssid)-1;
  params.psk=(const uint8_t *)password;params.psk_length=16;params.channel=6;params.band=WIFI_FREQ_BAND_2_4_GHZ;params.security=WIFI_SECURITY_TYPE_PSK;
  state("starting approved WPA2 AP",0);err=net_mgmt(NET_REQUEST_WIFI_AP_ENABLE,iface,&params,sizeof(params));wipe(password,sizeof(password));
  if(err){state("AP configuration failed",err);continue;}
  err=net_dhcpv4_server_start(iface,&pool);
  if(!err)err=p4_server_start();
  if(err){net_dhcpv4_server_stop(iface);net_mgmt(NET_REQUEST_WIFI_AP_DISABLE,iface,NULL,0);state("local service start failed",err);continue;}
  k_mutex_lock(&state_lock,K_FOREVER);ap_running=true;phase="ready";last_error=0;k_mutex_unlock(&state_lock);
 }
}
K_THREAD_DEFINE(p4_ap_worker,12288,network_worker,NULL,NULL,NULL,8,0,0);
void p4_network_init(void)
{
 int err=storage_init();if(err){state("AP settings storage unavailable",err);return;}
 k_sem_give(&network_work);
}
void p4_network_status(char *out,size_t n)
{
 k_mutex_lock(&state_lock,K_FOREVER);
 snprintf(out,n,"{\"target\":\"native Zephyr board-hosted\",\"phase\":\"%s\",\"error\":%d,\"wifi_driver_ready\":%s,\"assets_valid\":%s,\"credentials_saved\":%s,\"ap_running\":%s,\"ssid\":\"MicroBlocks-P4\",\"address\":\"192.168.4.1\",\"channel\":6,\"security\":\"WPA2-PSK\",\"max_clients\":2,\"controller\":\"%s\",\"station_association\":false,\"internet_sharing\":false}",
  phase,last_error,device_is_ready(DEVICE_DT_GET(DT_NODELABEL(p4_wifi)))?"true":"false",assets_ready?"true":"false",key_present?"true":"false",ap_running?"true":"false",p4_transport_owner());
 k_mutex_unlock(&state_lock);
}
void p4_network_message(int type,int bytes,char *body)
{
 if(type!=214 || bytes<10 || memcmp(body,"P4AP",4))return;
 uint8_t *p=(uint8_t *)body;uint32_t request=sys_get_le32(p+6);uint8_t operation=p[4],reply[6];sys_put_le32(request,reply);reply[4]=1;reply[5]=operation;
 char password[17]={0};
 if(operation==1 && bytes==27 && p[5]==0 && p[10]==16 && p4_transport_is_usb()){
  memcpy(password,p+11,16);
  if(password_valid(password)){
   k_mutex_lock(&state_lock,K_FOREVER);
   if(!storage_ready)reply[4]=2;
   else if(!assets_ready)reply[4]=4;
   else if(key_present && memcmp(password,credential.password,17))reply[4]=3;
   else {
    if(!key_present){
     struct credentials saved={0};saved.magic=0x5034424d;saved.version=1;memcpy(saved.password,password,17);
     int err=nvs_write(&storage,0x41,&saved,sizeof(saved));
     if(err==(int)sizeof(saved)){credential=saved;key_present=true;reply[4]=0;}else reply[4]=2;
     wipe(&saved,sizeof(saved));
    }else reply[4]=0;
   }
   bool start=reply[4]==0&&!ap_running;k_mutex_unlock(&state_lock);if(start)k_sem_give(&network_work);
  }
 }
 wipe(password,sizeof(password));wipe(body,bytes);
 waitAndSendMessage(214,0,sizeof(reply),(char *)reply);
}
