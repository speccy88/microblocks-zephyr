/* SPDX-License-Identifier: MIT
 * Bounded AirLift identification and explicitly submitted WPA/DHCP setup.
 * No boot-time access, scanning, credential logging, UART or firmware upload.
 * Framing reference and notices: nina_protocol.c and LICENSES.md. */
#include "airlift.h"
#include "fruit_jam.h"
#include "nina_protocol.h"
#include "wifi_control.h"
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/kernel.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

#define AIRLIFT DT_PATH(zephyr_user)
static const struct device *const bus=DEVICE_DT_GET(DT_NODELABEL(spi1));
static const struct gpio_dt_spec cs=GPIO_DT_SPEC_GET(AIRLIFT,airlift_cs_gpios);
static const struct gpio_dt_spec busy=GPIO_DT_SPEC_GET(AIRLIFT,airlift_busy_gpios);
static const struct gpio_dt_spec reset=GPIO_DT_SPEC_GET(AIRLIFT,airlift_reset_gpios);
static const struct gpio_dt_spec boot=GPIO_DT_SPEC_GET(AIRLIFT,airlift_boot_gpios);
static const struct spi_config config={
    .frequency=1000000,.operation=SPI_OP_MODE_MASTER|SPI_WORD_SET(8)|SPI_TRANSFER_MSB,.slave=0,
};
K_MUTEX_DEFINE(state_lock);
K_MUTEX_DEFINE(spi_lock);
K_SEM_DEFINE(request_sem,0,1);
static struct {
    unsigned state,generation,queries,operation;
    int error,stage,busy_level,connection,disconnect_reason,reason_error;
    bool reset_requested;
    char version[32],mac[18];
    uint8_t ip[4],netmask[4],gateway[4];
} report;
static unsigned stale_error_recoveries;
static volatile uint32_t first_socket_failure;
uint32_t fj_airlift_socket_failure(void){return first_socket_failure;}
static struct { uint8_t ssid[32],key[64]; size_t sn,kn; } pending;

static int wait_busy_for(int level,unsigned timeout_ms)
{
    int64_t deadline=k_uptime_get()+timeout_ms;
    do {
        int actual=gpio_pin_get_dt(&busy);
        if(actual<0)return actual;
        if(actual==level)return 0;
        k_sleep(K_MSEC(1));
    }while(k_uptime_get()<deadline);
    return -ETIMEDOUT;
}
static int select_device_for(unsigned timeout_ms)
{
    int err=wait_busy_for(0,timeout_ms);
    if(err)return err;
    if((err=gpio_pin_set_dt(&cs,1)))return err;
    err=wait_busy_for(1,1000);
    if(err)gpio_pin_set_dt(&cs,0);
    return err;
}
static int select_device(void){return select_device_for(1000);}
static int read_byte(void *unused,uint8_t *value)
{
    (void)unused;
    uint8_t dummy=0;
    const struct spi_buf tx={.buf=&dummy,.len=1};
    struct spi_buf rx={.buf=value,.len=1};
    const struct spi_buf_set txs={.buffers=&tx,.count=1},rxs={.buffers=&rx,.count=1};
    return spi_transceive(bus,&config,&txs,&rxs);
}
static void retry_pause(void *unused){(void)unused;k_sleep(K_MSEC(10));}
static int read_bytes(void *unused,uint8_t *dst,size_t size)
{
    (void)unused;if(!size)return 0;
    struct spi_buf buffer={.buf=dst,.len=size};
    const struct spi_buf_set buffers={.buffers=&buffer,.count=1};
    return spi_read(bus,&config,&buffers);
}
static int exchange_unlocked(uint8_t command,uint8_t *frame,size_t count,
                    uint8_t **dst,const size_t *capacity,size_t *length,unsigned parameters)
{
    int err=select_device();
    if(!err){
        const struct spi_buf buffer={.buf=frame,.len=count};
        const struct spi_buf_set buffers={.buffers=&buffer,.count=1};
        uint8_t observed[4]={0};
        bool version_probe=command==0x37&&count==4;
        if(version_probe){
            struct spi_buf receive={.buf=observed,.len=sizeof(observed)};
            const struct spi_buf_set receives={.buffers=&receive,.count=1};
            err=spi_transceive(bus,&config,&buffers,&receives);
        }else err=spi_write(bus,&config,&buffers);
        int released=gpio_pin_set_dt(&cs,0);
        if(!err)err=released;
        /* Only a read-only version probe may recover an exact stale error
         * reply consumed during its request. No write or join is replayed. */
        if(!err&&version_probe&&!memcmp(observed,(uint8_t[]){0xef,0,0xee,0},4)){
            ++stale_error_recoveries;
            err=select_device();
            if(!err){
                err=spi_write(bus,&config,&buffers);
                released=gpio_pin_set_dt(&cs,0);if(!err)err=released;
            }
        }
    }
    /* A connect frame never survives the write or any error. */
    fj_secure_clear(frame,count);
    if(err)return err;
    if((err=select_device()))return err;
    const struct fj_nina_reader io={.byte=read_byte,.retry_pause=retry_pause};
    err=fj_nina_read_reply_params(&io,command,dst,capacity,length,parameters);
    int released=gpio_pin_set_dt(&cs,0);
    return err?err:released;
}
static int exchange(uint8_t command,uint8_t *frame,size_t count,
                    uint8_t **dst,const size_t *capacity,size_t *length,unsigned parameters)
{
    k_mutex_lock(&spi_lock,K_FOREVER);
    int err=exchange_unlocked(command,frame,count,dst,capacity,length,parameters);
    k_mutex_unlock(&spi_lock);return err;
}
int fj_airlift_socket_command(uint8_t command,const struct fj_nina_parameter *params,
                              unsigned count,uint8_t *dst,size_t capacity,size_t *length)
{
    uint8_t frame[2060];int n=fj_nina_socket_frame(command,params,count,frame,sizeof(frame));
    if(n<0)return n;
    k_mutex_lock(&spi_lock,K_FOREVER);
    unsigned phase=1;int err=select_device();
    if(!err){
        phase=2;
        const struct spi_buf buffer={.buf=frame,.len=n};
        const struct spi_buf_set buffers={.buffers=&buffer,.count=1};
        err=spi_write(bus,&config,&buffers);
        int released=gpio_pin_set_dt(&cs,0);if(!err)err=released;
    }
    if(!err){phase=3;err=select_device_for(command==0x44?10000:1000);}
    if(!err){
        phase=4;
        const struct fj_nina_reader io={.byte=read_byte,.bytes=read_bytes,.retry_pause=retry_pause};
        err=fj_nina_socket_reply(&io,command,dst,capacity,length);
        int released=gpio_pin_set_dt(&cs,0);
        if(!err&&released){phase=5;err=released;}
    }
    if(err){
        if(!first_socket_failure)first_socket_failure=((uint32_t)(-err&255)<<16)|((uint32_t)command<<8)|phase;
        /* Restore framing with read-only probes, never replay a write/read
         * whose effects may already have occurred on the remote socket. */
        for(unsigned attempt=0;attempt<2;++attempt){
            uint8_t probe[]={0xe0,0x37,0,0xee},version[31];
            uint8_t *dest[]={version};const size_t cap[]={sizeof(version)};size_t got=0;
            if(!exchange_unlocked(0x37,probe,sizeof(probe),dest,cap,&got,1))break;
        }
    }
    k_mutex_unlock(&spi_lock);return err;
}
static int query(uint8_t command,uint8_t *dst,size_t capacity,size_t *length)
{
    uint8_t frame[8];int n=fj_nina_query_frame(command,frame,sizeof(frame));
    if(n<0)return n;
    uint8_t *destinations[]={dst};
    return exchange(command,frame,n,destinations,&capacity,length,1);
}
static int query_ip(uint8_t ip[4],uint8_t netmask[4],uint8_t gateway[4])
{
    uint8_t frame[8];int n=fj_nina_query_frame(0x21,frame,sizeof(frame));
    if(n<0)return n;
    uint8_t *dst[]={ip,netmask,gateway};const size_t capacity[]={4,4,4};size_t lengths[3]={0};
    int err=exchange(0x21,frame,n,dst,capacity,lengths,3);
    if(!err&&(lengths[0]!=4||lengths[1]!=4||lengths[2]!=4))err=-EPROTO;
    return err;
}
static bool valid_ip(const uint8_t ip[4])
{
    return ip[0]>0&&ip[0]<224&&ip[0]!=127&&!(ip[0]==169&&ip[1]==254);
}
static int prepare(bool reset_first)
{
    if(!device_is_ready(bus)||!gpio_is_ready_dt(&cs)||!gpio_is_ready_dt(&busy))return -ENODEV;
    int err=gpio_pin_configure_dt(&cs,GPIO_OUTPUT_INACTIVE);
    if(err)return err;
    if((err=gpio_pin_configure_dt(&busy,GPIO_INPUT)))return err;
    if(!reset_first)return 0;
    if(!gpio_is_ready_dt(&reset)||!gpio_is_ready_dt(&boot))return -ENODEV;
    /* C6 BOOT9 is GPIO23, shared with codec GPIO1: input only.
     * GPIO0 is RP2350 USBBOOT. Shared reset requires an idle codec. */
    if((err=gpio_pin_configure_dt(&boot,GPIO_INPUT|GPIO_PULL_UP)))return err;
    if((err=gpio_pin_configure_dt(&reset,GPIO_OUTPUT_INACTIVE)))return err;
    if((err=gpio_pin_set_dt(&reset,1)))return err;
    k_sleep(K_MSEC(10));
    if((err=gpio_pin_set_dt(&reset,0)))return err;
    k_sleep(K_MSEC(750));return 0;
}
static void publish_progress(int stage,int connection,unsigned queries)
{
    k_mutex_lock(&state_lock,K_FOREVER);
    report.stage=stage;report.connection=connection;report.queries=queries;
    k_mutex_unlock(&state_lock);
}
static void diagnostic_worker(void *a,void *b,void *c)
{
    (void)a;(void)b;(void)c;
    for(;;){
        k_sem_take(&request_sem,K_FOREVER);
        uint8_t ssid[32]={0},key[64]={0};size_t sn=0,kn=0;
        k_mutex_lock(&state_lock,K_FOREVER);
        bool reset_first=report.reset_requested,join=report.operation==1;
        if(join){sn=pending.sn;kn=pending.kn;memcpy(ssid,pending.ssid,sn);memcpy(key,pending.key,kn);}
        fj_secure_clear(&pending,sizeof(pending));report.state=2;
        k_mutex_unlock(&state_lock);
        uint8_t data[31]={0},ip[4]={0},netmask[4]={0},gateway[4]={0};size_t count=0;
        if(!join&&!reset_first){
            k_mutex_lock(&state_lock,K_FOREVER);
            memcpy(ip,report.ip,4);memcpy(netmask,report.netmask,4);memcpy(gateway,report.gateway,4);
            k_mutex_unlock(&state_lock);
        }
        char version[32]={0},mac[18]={0};
        int stage=1,connection=-1,reason=-1,reason_error=0;unsigned queries=0;
        k_mutex_lock(&spi_lock,K_FOREVER);
        int err=prepare(reset_first);
        k_mutex_unlock(&spi_lock);
        if(!err){stage=2;err=query(0x37,data,sizeof(data),&count);}
        if(!err){
            ++queries;unsigned out=0;
            for(size_t i=0;i<count;++i){
                if(!data[i])continue;
                if(data[i]<32||data[i]>126||data[i]=='"'||data[i]=='\\'){err=-EPROTO;break;}
                version[out++]=data[i];
            }
            if(!out)err=-EPROTO;
        }
        if(!err){stage=3;err=query(0x22,data,6,&count);}
        if(!err&&count!=6)err=-EPROTO;
        if(!err){
            ++queries;
            /* NINA 3.3.0 copies canonical-order MAC bytes directly. */
            snprintf(mac,sizeof(mac),"%02x:%02x:%02x:%02x:%02x:%02x",data[0],data[1],data[2],data[3],data[4],data[5]);
            stage=4;err=query(0x20,data,1,&count);
        }
        if(!err&&count!=1)err=-EPROTO;
        if(!err){++queries;connection=data[0];}
        if(!err){
            reason_error=query(0x1f,data,1,&count);
            if(!reason_error&&count!=1)reason_error=-EPROTO;
            if(!reason_error){reason=data[0];++queries;}
        }
        if(!join&&!err&&connection==3){stage=7;err=query_ip(ip,netmask,gateway);++queries;}
        if(join&&!err){
            stage=5;publish_progress(stage,connection,queries);
            uint8_t frame[104]={0};
            int n=fj_nina_connect_frame(ssid,sn,key,kn,frame,sizeof(frame));
            fj_secure_clear(ssid,sizeof(ssid));fj_secure_clear(key,sizeof(key));sn=kn=0;
            if(n<0)err=n;
            else{
                uint8_t *dst[]={data};const size_t capacity[]={1};size_t length=0;
                err=exchange(0x11,frame,n,dst,capacity,&length,1);
                if(!err&&(length!=1||data[0]!=1))err=-EACCES;
            }
            fj_secure_clear(frame,sizeof(frame));
            int64_t deadline=k_uptime_get()+45000;
            while(!err&&k_uptime_get()<deadline){
                stage=6;err=query(0x20,data,1,&count);
                if(!err&&count!=1)err=-EPROTO;
                if(err)break;
                ++queries;connection=data[0];publish_progress(stage,connection,queries);
                if(connection==4){
                    reason_error=query(0x1f,data,1,&count);
                    if(!reason_error&&count!=1)reason_error=-EPROTO;
                    if(!reason_error){reason=data[0];++queries;}
                    err=-EACCES;break;
                }
                if(connection==3){
                    stage=7;err=query_ip(ip,netmask,gateway);++queries;
                    if(err||valid_ip(ip))break;
                }
                k_sleep(K_MSEC(250));
            }
            if(!err&&(connection!=3||!valid_ip(ip)))err=-ETIMEDOUT;
        }
        fj_secure_clear(ssid,sizeof(ssid));fj_secure_clear(key,sizeof(key));
        if(connection!=3){memset(ip,0,4);memset(netmask,0,4);memset(gateway,0,4);}
        k_mutex_lock(&spi_lock,K_FOREVER);
        if(gpio_is_ready_dt(&cs))gpio_pin_set_dt(&cs,0);
        int level=gpio_is_ready_dt(&busy)?gpio_pin_get_dt(&busy):-1;
        k_mutex_unlock(&spi_lock);
        k_mutex_lock(&state_lock,K_FOREVER);
        report.error=err;report.stage=stage;report.queries=queries;report.connection=connection;report.busy_level=level;
        report.disconnect_reason=reason;report.reason_error=reason_error;
        memcpy(report.version,version,sizeof(version));memcpy(report.mac,mac,sizeof(mac));
        memcpy(report.ip,ip,4);memcpy(report.netmask,netmask,4);memcpy(report.gateway,gateway,4);
        report.state=err?4:3;k_mutex_unlock(&state_lock);
    }
}
K_THREAD_DEFINE(airlift_diagnostic_thread,3072,diagnostic_worker,NULL,NULL,NULL,7,0,0);
int fj_airlift_request(bool reset_first)
{
    k_mutex_lock(&state_lock,K_FOREVER);
    if(report.state==1||report.state==2){k_mutex_unlock(&state_lock);return -EBUSY;}
    ++report.generation;report.state=1;report.error=0;report.stage=0;report.operation=0;
    report.reset_requested=reset_first;k_mutex_unlock(&state_lock);k_sem_give(&request_sem);return 0;
}
int fj_airlift_join(const uint8_t *ssid,size_t sn,const uint8_t *key,size_t kn)
{
    int err=fj_wifi_credentials_valid(ssid,sn,key,kn);if(err)return err;
    k_mutex_lock(&state_lock,K_FOREVER);
    if(report.state==1||report.state==2){k_mutex_unlock(&state_lock);return -EBUSY;}
    fj_secure_clear(&pending,sizeof(pending));memcpy(pending.ssid,ssid,sn);memcpy(pending.key,key,kn);pending.sn=sn;pending.kn=kn;
    ++report.generation;report.state=1;report.error=0;report.stage=0;report.operation=1;report.reset_requested=false;
    memset(report.ip,0,4);memset(report.netmask,0,4);memset(report.gateway,0,4);
    k_mutex_unlock(&state_lock);k_sem_give(&request_sem);return 0;
}
int fj_airlift_status(char *dst,unsigned size)
{
    k_mutex_lock(&state_lock,K_FOREVER);
    int n=snprintf(dst,size,
      "{\"setup_protocol\":1,\"state\":%u,\"generation\":%u,\"operation\":%u,\"error\":%d,\"stage\":%d,\"queries\":%u,"
      "\"version\":\"%s\",\"mac\":\"%s\",\"connection\":%d,\"disconnect_reason\":%d,\"reason_error\":%d,\"spi_resync\":%u,\"busy\":%d,\"reset_requested\":%s,\"spi_hz\":1000000,\"coprocessor_flashed\":false,"
      "\"network_ready\":%s,\"ip\":\"%u.%u.%u.%u\",\"netmask\":\"%u.%u.%u.%u\",\"gateway\":\"%u.%u.%u.%u\"}",
      report.state,report.generation,report.operation,report.error,report.stage,report.queries,report.version,report.mac,
      report.connection,report.disconnect_reason,report.reason_error,stale_error_recoveries,report.busy_level,report.reset_requested?"true":"false",
      report.state==3&&report.connection==3&&valid_ip(report.ip)?"true":"false",
      report.ip[0],report.ip[1],report.ip[2],report.ip[3],report.netmask[0],report.netmask[1],report.netmask[2],report.netmask[3],
      report.gateway[0],report.gateway[1],report.gateway[2],report.gateway[3]);
    k_mutex_unlock(&state_lock);return n<0||(unsigned)n>=size?-ENOSPC:0;
}
bool fj_airlift_network_ready(char *ip,unsigned size)
{
    k_mutex_lock(&state_lock,K_FOREVER);
    bool ready=report.state==3&&report.connection==3&&valid_ip(report.ip);
    if(ip&&size)snprintf(ip,size,"%u.%u.%u.%u",report.ip[0],report.ip[1],report.ip[2],report.ip[3]);
    k_mutex_unlock(&state_lock);return ready;
}
