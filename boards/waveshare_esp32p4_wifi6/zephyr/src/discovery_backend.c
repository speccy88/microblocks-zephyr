/* SPDX-License-Identifier: MIT */
#include "discovery_backend.h"
#include "camera_backend.h"
#include "audio_backend.h"
#include <zephyr/kernel.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/sys/atomic.h>
#include <stdio.h>
#include <string.h>
static const struct device *const bus=DEVICE_DT_GET(DT_NODELABEL(i2c0));
static struct {K_KERNEL_STACK_MEMBER(stack,4096);} memory __attribute__((section(".ext_ram.bss.discovery_stack")));
static struct k_thread thread;
K_MUTEX_DEFINE(discovery_lock);
K_SEM_DEFINE(discovery_work,0,1);
static atomic_t busy,cancelled;
static discovery_results results;
static discovery_device reading_device;
static discovery_reading reading={0,1,"",DISC_NOT_READY};
static uint32_t generation;
static int job;
static bool identify,initialized,expired;
static int64_t deadline;
static char measurement[32],message[96]="Scan a configured I2C bus to begin";
static int probe(void *ctx,uint8_t address)
{
 ARG_UNUSED(ctx);uint8_t dummy=0;
 struct i2c_msg msg={.buf=&dummy,.len=0,.flags=I2C_MSG_WRITE|I2C_MSG_STOP};
 return i2c_transfer(bus,&msg,1,address);
}
static int read_reg(void *ctx,uint8_t address,uint16_t reg,unsigned width,uint8_t *data,unsigned count)
{
 ARG_UNUSED(ctx);uint8_t pointer[2]={(uint8_t)(reg>>8),(uint8_t)reg};
 if((width!=1 && width!=2)||!count||count>2)return -EINVAL;
 return i2c_write_read(bus,address,pointer+(width==1),width,data,count);
}
static bool stop(void *ctx)
{ARG_UNUSED(ctx);expired=k_uptime_get()>=deadline;return atomic_get(&cancelled)||expired;}
static const discovery_bus port={NULL,probe,read_reg,stop};
static void worker(void *a,void *b,void *c)
{
 ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);
 for(;;){
  k_sem_take(&discovery_work,K_FOREVER);
  discovery_results next={0};discovery_reading value={0,1,"",DISC_NOT_READY};
  if(job==1)discovery_scan(&port,identify,&next);
  else value=discovery_read(&port,&reading_device,measurement);
  bool cancelled_now=atomic_get(&cancelled)!=0;
  k_mutex_lock(&discovery_lock,K_FOREVER);
  if(job==1){
   results=next;if(expired)results.error=DISC_TIMEOUT;else if(cancelled_now)results.error=DISC_CANCELLED;
   if(results.error)snprintf(message,sizeof(message),"%s; %u devices found",discovery_error_name(results.error),results.count);
   else snprintf(message,sizeof(message),"Scan complete: %u devices; bus 0",results.count);
  }else{
   reading=value;if(expired)reading.error=DISC_TIMEOUT;else if(cancelled_now)reading.error=DISC_CANCELLED;
   snprintf(message,sizeof(message),"%s",discovery_error_name(reading.error));
  }
  job=0;atomic_clear(&busy);k_mutex_unlock(&discovery_lock);
 }
}
void p4_discovery_init(void)
{
 if(initialized)return;initialized=true;
 k_thread_create(&thread,memory.stack,K_KERNEL_STACK_SIZEOF(memory.stack),worker,NULL,NULL,NULL,8,0,K_NO_WAIT);
 k_thread_name_set(&thread,"i2c_discovery");
}
bool p4_discovery_busy(void){return atomic_get(&busy)!=0;}
static bool start(void)
{
 /* All start primitives execute on the VM thread. Workers never start a
  * capture, and camera/audio request paths reject busy discovery. */
 if(!initialized||p4_discovery_busy()||camera_busy()||p4_audio_busy()){
  snprintf(message,sizeof(message),"Bus busy; wait for camera, audio or I2C job");return false;
 }
 if(!device_is_ready(bus)){snprintf(message,sizeof(message),"Bus 0 is unavailable");return false;}
 atomic_clear(&cancelled);expired=false;deadline=k_uptime_get()+2000;atomic_set(&busy,1);return true;
}
bool p4_discovery_scan(int selected_bus,bool with_ids)
{
 k_mutex_lock(&discovery_lock,K_FOREVER);
 if(selected_bus!=0){snprintf(message,sizeof(message),"Only bus 0 is configured on this board");k_mutex_unlock(&discovery_lock);return false;}
 if(!start()){k_mutex_unlock(&discovery_lock);return false;}
 generation=generation>=0x3fffffff?1:generation+1;memset(&results,0,sizeof(results));
 reading=(discovery_reading){0,1,"",DISC_NOT_READY};identify=with_ids;job=1;
 snprintf(message,sizeof(message),with_ids?"Scanning bus 0 with documented ID reads":"Scanning bus 0; addresses only");
 k_sem_give(&discovery_work);k_mutex_unlock(&discovery_lock);return true;
}
void p4_discovery_cancel(void){atomic_set(&cancelled,1);}
unsigned p4_discovery_count(void)
{k_mutex_lock(&discovery_lock,K_FOREVER);unsigned n=p4_discovery_busy()?0:results.count;k_mutex_unlock(&discovery_lock);return n;}
void p4_discovery_ref(int index,char *out,size_t n)
{
 k_mutex_lock(&discovery_lock,K_FOREVER);out[0]=0;
 if(!p4_discovery_busy()&&index>=1&&(unsigned)index<=results.count)snprintf(out,n,"I2C:%08x:%02x",generation,results.devices[index-1].address);
 k_mutex_unlock(&discovery_lock);
}
static bool lookup(const char *ref,discovery_device *out)
{
 unsigned g,a;int used=0;
 if(strlen(ref)!=15 || sscanf(ref,"I2C:%8x:%2x%n",&g,&a,&used)!=2 || used!=15 || g!=generation || p4_discovery_busy())return false;
 for(unsigned i=0;i<results.count;i++)if(results.devices[i].address==a){*out=results.devices[i];return true;}
 return false;
}
bool p4_discovery_device(const char *ref,discovery_device *out)
{k_mutex_lock(&discovery_lock,K_FOREVER);bool ok=lookup(ref,out);k_mutex_unlock(&discovery_lock);return ok;}
bool p4_discovery_read(const char *ref,const char *name)
{
 k_mutex_lock(&discovery_lock,K_FOREVER);discovery_device d;
 if(!lookup(ref,&d)){snprintf(message,sizeof(message),"Sensor reference expired, invalid or busy; scan again");reading.error=DISC_REPLACED;k_mutex_unlock(&discovery_lock);return false;}
 bool supported=false;for(unsigned i=0;i<discovery_measurement_count(&d);i++)if(!strcmp(name,discovery_measurement(&d,i)))supported=true;
 if(!supported){snprintf(message,sizeof(message),"Measurement unsupported; inspect this sensor's measurements");reading.error=DISC_UNSUPPORTED;k_mutex_unlock(&discovery_lock);return false;}
 if(!start()){k_mutex_unlock(&discovery_lock);return false;}
 reading_device=d;snprintf(measurement,sizeof(measurement),"%s",name);reading=(discovery_reading){0,1,"",DISC_NOT_READY};job=2;
 snprintf(message,sizeof(message),"Reading %s",name);k_sem_give(&discovery_work);k_mutex_unlock(&discovery_lock);return true;
}
discovery_reading p4_discovery_reading(void)
{k_mutex_lock(&discovery_lock,K_FOREVER);discovery_reading v=reading;if(p4_discovery_busy())v.error=DISC_NOT_READY;k_mutex_unlock(&discovery_lock);return v;}
void p4_discovery_status(char *out,size_t n)
{k_mutex_lock(&discovery_lock,K_FOREVER);snprintf(out,n,"%s",message);k_mutex_unlock(&discovery_lock);}
void p4_discovery_read_text(char *out,size_t n)
{
 discovery_reading v=p4_discovery_reading();
 if(v.error){snprintf(out,n,"Error: %s",discovery_error_name(v.error));return;}
 if(v.scale==1000){int32_t a=v.value<0?-v.value:v.value;snprintf(out,n,"%s%d.%03d degrees C",v.value<0?"-":"",(int)(a/1000),(int)(a%1000));}
 else snprintf(out,n,"%d %s",(int)v.value,v.unit);
}
