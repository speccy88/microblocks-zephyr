/* SPDX-License-Identifier: MIT */
#include "provisioning.h"
#include "network_setup.h"
#include "zephyr_network_store.h"
#include "network_transport.h"
#include "xrp.h"
#include "vm/interp.h"
#include <zephyr/kernel.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/dhcpv4.h>
#include <zephyr/net/http/server.h>
#include <zephyr/sys/atomic.h>
#include <stdio.h>
#include <string.h>

struct job { uint8_t ssid[32],key[64];size_t ssid_length,key_length;bool remember; };
static struct job pending;
static struct mbnw_flash_store store;
static atomic_t busy,storage_ready,join_result;
K_MUTEX_DEFINE(state_lock);
K_SEM_DEFINE(started,0,1);
K_SEM_DEFINE(job_ready,0,1);
K_SEM_DEFINE(join_done,0,1);
static const char *state="starting";
static int last_error;
static char board_ip[NET_IPV4_ADDR_LEN]="0.0.0.0";
static struct net_mgmt_event_callback wifi_events;
static bool server_started;
int mb_server_start(void);
const char *mb_network_ip(void) { return board_ip; }
static void set_state(const char *s,int error)
{ k_mutex_lock(&state_lock,K_FOREVER);state=s;last_error=error;k_mutex_unlock(&state_lock); }
static void wifi_event(struct net_mgmt_event_callback *cb,uint64_t event,struct net_if *iface)
{
    if(iface!=net_if_get_wifi_sta())return;
    if(event==NET_EVENT_WIFI_CONNECT_RESULT){
        const struct wifi_status *s=cb->info;
        atomic_set(&join_result,s?s->status:-EIO);k_sem_give(&join_done);
    }else if(event==NET_EVENT_WIFI_DISCONNECT_RESULT && !atomic_get(&busy)){
        set_state("disconnected",-ENOTCONN);
    }
}
static int join(struct job *j)
{
    struct net_if *iface=net_if_get_wifi_sta();
    if(!iface || !device_is_ready(net_if_get_device(iface)))return -ENODEV;
    if(server_started){http_server_stop();server_started=false;}
    k_mutex_lock(&state_lock,K_FOREVER);strcpy(board_ip,"0.0.0.0");k_mutex_unlock(&state_lock);
    net_dhcpv4_stop(iface);
    /* Explicit reconnect is USB initiated. Old DHCP addresses must not be
     * mistaken for completion of a new association. */
    net_mgmt(NET_REQUEST_WIFI_DISCONNECT,iface,NULL,0);
    k_sem_reset(&join_done);atomic_set(&join_result,-EINPROGRESS);
    struct wifi_connect_req_params config={
        .ssid=j->ssid,.ssid_length=j->ssid_length,.psk=j->key,.psk_length=j->key_length,
        .security=WIFI_SECURITY_TYPE_PSK,.band=WIFI_FREQ_BAND_2_4_GHZ,
        .channel=WIFI_CHANNEL_ANY,.timeout=15,
    };
    set_state("joining",0);net_if_up(iface);
    int e=net_mgmt(NET_REQUEST_WIFI_CONNECT,iface,&config,sizeof(config));
    if(!e && k_sem_take(&join_done,K_SECONDS(18)))e=-ETIMEDOUT;
    if(!e && atomic_get(&join_result))e=-ECONNREFUSED;
    if(e)goto fail;
    struct wifi_iface_status status={0};
    e=net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS,iface,&status,sizeof(status));
    if(!e && (status.ssid_len!=j->ssid_length || memcmp(status.ssid,j->ssid,j->ssid_length)))e=-ENOTCONN;
    if(e)goto fail;
    set_state("dhcp",0);net_dhcpv4_start(iface);
    for(unsigned i=0;i<100;++i){
        struct net_in_addr *addr=net_if_ipv4_get_global_addr(iface,NET_ADDR_PREFERRED);
        if(addr && addr->s_addr){
            k_mutex_lock(&state_lock,K_FOREVER);
            net_addr_ntop(NET_AF_INET,addr,board_ip,sizeof(board_ip));
            k_mutex_unlock(&state_lock);
            e=mb_server_start();if(e)return e;server_started=true;
            if(j->remember){
                e=mbnw_store_save(&store.io,j->ssid,j->ssid_length,j->key,j->key_length);
                if(e){set_state("connected-save-failed",e);return e;}
            }
            set_state("connected",0);return 0;
        }
        k_sleep(K_MSEC(200));
    }
    e=-ETIMEDOUT;
fail:
    net_dhcpv4_stop(iface);net_mgmt(NET_REQUEST_WIFI_DISCONNECT,iface,NULL,0);
    return e;
}
static void worker(void *a,void *b,void *c)
{
    (void)a;(void)b;(void)c;k_sem_take(&started,K_FOREVER);
    int e=mbnw_flash_store_open(&store,DT_MAPPED_PARTITION_ID(DT_NODELABEL(wifi_settings)));
    atomic_set(&storage_ready,e==0);
    net_mgmt_init_event_callback(&wifi_events,wifi_event,
        NET_EVENT_WIFI_CONNECT_RESULT | NET_EVENT_WIFI_DISCONNECT_RESULT);
    net_mgmt_add_event_callback(&wifi_events);
    set_state("usb-setup",e);
    struct mbnw_credentials saved={0};
    if(!e && xrp_button(0)==0 && !mbnw_store_load(&store.io,&saved,NULL)){
        struct job initial={.ssid_length=saved.ssid_length,.key_length=saved.key_length};
        memcpy(initial.ssid,saved.ssid,saved.ssid_length);memcpy(initial.key,saved.key,saved.key_length);
        mbnw_clear(&saved,sizeof(saved));
        atomic_set(&busy,1);e=join(&initial);mbnw_clear(&initial,sizeof(initial));
        if(e)set_state("join-failed",e);
        atomic_clear(&busy);
    }
    mbnw_clear(&saved,sizeof(saved));
    atomic_clear(&busy);
    for(;;){
        k_sem_take(&job_ready,K_FOREVER);
        struct job j;
        k_mutex_lock(&state_lock,K_FOREVER);j=pending;mbnw_clear(&pending,sizeof(pending));k_mutex_unlock(&state_lock);
        e=join(&j);mbnw_clear(&j,sizeof(j));
        if(e)set_state("join-failed",e);
        atomic_clear(&busy);
    }
}
K_THREAD_DEFINE(network_worker,6144,worker,NULL,NULL,NULL,8,0,0);
void xrp_provision_start(void) { atomic_set(&busy,1);k_sem_give(&started); }
int xrp_network_status(char *dst,size_t n)
{
    struct net_if *iface=net_if_get_wifi_sta();
    bool radio_ready=iface && device_is_ready(net_if_get_device(iface));
    k_mutex_lock(&state_lock,K_FOREVER);
    int count=snprintf(dst,n,"{\"board\":\"xrp-rp2350\",\"setup_protocol\":2,"
        "\"persistence_supported\":%s,\"radio_ready\":%s,\"state\":\"%s\",\"busy\":%s,\"ip\":\"%s\",\"error\":%d,\"actuators_enabled\":false}",
        atomic_get(&storage_ready)?"true":"false",radio_ready?"true":"false",state,atomic_get(&busy)?"true":"false",board_ip,last_error);
    k_mutex_unlock(&state_lock);return count<0 || (size_t)count>=n ? -ENOBUFS : 0;
}
void xrp_provision_message(char *body,unsigned size)
{
    struct mbnw_request r;
    int e=mbnw_decode((uint8_t *)body,size,&r);
    if(!e)e=mbnw_authorize(&r,xrp_wifi_setup_local(),atomic_get(&storage_ready));
    if(!e && r.operation==MBNW_CONNECT){
        if(!atomic_cas(&busy,0,1))e=-EBUSY;
        else{
            k_mutex_lock(&state_lock,K_FOREVER);
            pending=(struct job){.ssid_length=r.ssid_length,.key_length=r.key_length,.remember=(r.flags&MBNW_REMEMBER)!=0};
            memcpy(pending.ssid,r.ssid,r.ssid_length);memcpy(pending.key,r.key,r.key_length);
            k_mutex_unlock(&state_lock);k_sem_give(&job_ready);
        }
    }
    mbnw_clear(body,size);
    if(!r.id)return;
    char status[384],response[512];if(xrp_network_status(status,sizeof(status)))return;
    int n=snprintf(response,sizeof(response),"{\"request\":%u,\"accepted\":%s,\"command_error\":%d,\"status\":%s}",r.id,e?"false":"true",e,status);
    if(n>0 && (size_t)n<sizeof(response) && hasOutputSpace(n+5))waitAndSendMessage(205,0,n,response);
}
