/* SPDX-License-Identifier: MIT */
/* Native Zephyr PPA API. Worker owns copied pixels, never SmallVM objects. */
#include <zephyr/kernel.h>
#include <zephyr/cache.h>
#include <zephyr/sys/atomic.h>
#include "driver/ppa.h"
#include "image_store.h"
#include "ppa_backend.h"
#include <stdio.h>
#include <string.h>
#include <errno.h>

K_SEM_DEFINE(ppa_requested,0,1);
K_MUTEX_DEFINE(ppa_lock);
static atomic_t cancelled;
enum { IDLE, RUNNING, READY, ERROR, QUARANTINED };
static int state;
static image_view src,out;
static size_t src_span,out_span;
static unsigned target_w,target_h,rotation,mirrors;
static uint32_t copy_us,hardware_us;
static char message[256]="PPA idle";
static size_t span(size_t n){return ROUND_UP(n,64)+64;}
static bool guard(const image_view *v,size_t n)
{for(size_t i=n-64;i<n;i++)if(v->pixels[i]!=0xa5)return false;return true;}
static void dispose(void)
{image_free(src.pixels);image_free(out.pixels);memset(&src,0,sizeof(src));memset(&out,0,sizeof(out));}

int p4_ppa_request(int handle,int width,int height,int angle,int mirror)
{
 const image_view *v=image_get(handle);
 k_mutex_lock(&ppa_lock,K_FOREVER);
 if(state==RUNNING||state==READY||state==QUARANTINED){k_mutex_unlock(&ppa_lock);return 0;}
 const char *error=NULL;
 if(!v)error="Image handle is invalid or released";
 else if(v->format!=IMAGE_RGB565&&v->format!=IMAGE_RGB888)error="PPA needs RGB565 or RGB888; convert gray to RGB first";
 else if(width<1||height<1||width>IMAGE_MAX_WIDTH||height>IMAGE_MAX_HEIGHT)error="Image dimensions exceed the bounded store";
 else if(angle!=0&&angle!=90&&angle!=180&&angle!=270)error="Rotation must be 0, 90, 180 or 270 degrees";
 else if(mirror<0||mirror>3)error="Mirror must be 0 none, 1 horizontal, 2 vertical or 3 both";
 else if((width*16)%v->width||(height*16)%v->height||width*16<v->width||height*16<v->height||width>=v->width*256||height>=v->height*256)
  error="PPA scale ratios must be exact multiples of 1/16";
 unsigned ow=(angle==90||angle==270)?height:width,oh=(angle==90||angle==270)?width:height;
 if(!error&&(ow>IMAGE_MAX_WIDTH||oh>IMAGE_MAX_HEIGHT))error="Rotated dimensions exceed the bounded store";
 size_t bytes=error?0:(size_t)ow*oh*v->format;
 if(!error&&(image_count()==IMAGE_SLOTS||bytes>IMAGE_BUDGET-image_bytes_used()))error="Release an image before requesting a PPA result";
 if(error){state=ERROR;snprintf(message,sizeof(message),"%s",error);k_mutex_unlock(&ppa_lock);return 0;}
 uint32_t began=k_cycle_get_32();
 src=*v;out=(image_view){ow,oh,ow*v->format,v->format,bytes,NULL};
 src_span=span(v->bytes);out_span=span(bytes);
 src.pixels=image_alloc(src_span);out.pixels=image_alloc(out_span);
 if(!src.pixels||!out.pixels){dispose();state=ERROR;snprintf(message,sizeof(message),"PPA workspace allocation failed");k_mutex_unlock(&ppa_lock);return 0;}
 memcpy(src.pixels,v->pixels,v->bytes);memset(src.pixels+v->bytes,0,src_span-v->bytes);
 memset(out.pixels,0,out_span);memset(src.pixels+src_span-64,0xa5,64);memset(out.pixels+out_span-64,0xa5,64);
 target_w=width;target_h=height;rotation=angle;mirrors=mirror;
 copy_us=k_cyc_to_us_floor32(k_cycle_get_32()-began);hardware_us=0;
 atomic_clear(&cancelled);state=RUNNING;snprintf(message,sizeof(message),"PPA processing");
 k_sem_give(&ppa_requested);k_mutex_unlock(&ppa_lock);return 1;
}

static void worker(void *a,void *b,void *c)
{
 ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);
 for(;;){
  k_sem_take(&ppa_requested,K_FOREVER);
  int err=0;bool timed_out=false;ppa_client_handle_t client=NULL;
  if(!atomic_get(&cancelled)){
   ppa_client_config_t cc={.oper_type=PPA_OPERATION_SRM,.max_pending_trans_num=1,.data_burst_length=PPA_DATA_BURST_LENGTH_64};
   err=ppa_register_client(&cc,&client);
   if(!err)err=sys_cache_data_flush_range(src.pixels,src_span);
   if(!err)err=sys_cache_data_flush_range(out.pixels,out_span);
   if(!err){
    ppa_srm_oper_config_t cfg={0};
    cfg.in.buffer=src.pixels;cfg.in.pic_w=src.width;cfg.in.pic_h=src.height;
    cfg.in.block_w=src.width;cfg.in.block_h=src.height;
    cfg.in.srm_cm=src.format==IMAGE_RGB565?PPA_SRM_COLOR_MODE_RGB565:PPA_SRM_COLOR_MODE_RGB888;
    cfg.out.buffer=out.pixels;cfg.out.buffer_size=out_span-64;cfg.out.pic_w=out.width;cfg.out.pic_h=out.height;cfg.out.srm_cm=cfg.in.srm_cm;
    cfg.scale_x=(float)target_w/src.width;cfg.scale_y=(float)target_h/src.height;
    cfg.rotation_angle=rotation==90?PPA_SRM_ROTATION_ANGLE_90:rotation==180?PPA_SRM_ROTATION_ANGLE_180:rotation==270?PPA_SRM_ROTATION_ANGLE_270:PPA_SRM_ROTATION_ANGLE_0;
    cfg.mirror_x=(mirrors&1)!=0;cfg.mirror_y=(mirrors&2)!=0;cfg.mode=PPA_TRANS_MODE_BLOCKING;
    uint32_t began=k_cycle_get_32();err=ppa_do_scale_rotate_mirror(client,&cfg);
    hardware_us=k_cyc_to_us_floor32(k_cycle_get_32()-began);timed_out=err==ESP_ERR_TIMEOUT;
   }
   /* The pinned driver's timeout resets channels but does not report reset
    * acknowledgement. Retain both buffers/client permanently on timeout. */
   if(!timed_out){
    int cache=sys_cache_data_invd_range(out.pixels,out_span);if(!err)err=cache;
    cache=sys_cache_data_invd_range(src.pixels,src_span);if(!err)err=cache;
    if(!guard(&src,src_span)||!guard(&out,out_span))err=-EOVERFLOW;
    if(client){int released=ppa_unregister_client(client);if(released==ESP_ERR_INVALID_STATE)timed_out=true;if(!err)err=released;}
   }
  }
  k_mutex_lock(&ppa_lock,K_FOREVER);
  if(timed_out){state=QUARANTINED;snprintf(message,sizeof(message),"PPA completion unconfirmed; DMA buffers retained; reset required");}
  else if(atomic_get(&cancelled)){dispose();state=IDLE;snprintf(message,sizeof(message),"PPA cancelled; no result published");}
  else if(err){dispose();state=ERROR;snprintf(message,sizeof(message),"PPA failed (%d); no result published",err);}
  else{image_free(src.pixels);src.pixels=NULL;state=READY;
   snprintf(message,sizeof(message),"PPA ready: %ux%u; hardware API %u us; allocation/copy %u us",out.width,out.height,hardware_us,copy_us);}
  k_mutex_unlock(&ppa_lock);
 }
}
K_THREAD_DEFINE(ppa_thread,4096,worker,NULL,NULL,NULL,8,0,0);
int p4_ppa_busy(void){k_mutex_lock(&ppa_lock,K_FOREVER);int busy=state==RUNNING;k_mutex_unlock(&ppa_lock);return busy;}
int p4_ppa_result(void)
{
 int h=0;k_mutex_lock(&ppa_lock,K_FOREVER);
 if(state==READY){h=image_adopt(out.width,out.height,out.format,out.pixels,out.bytes);
  if(!h){image_free(out.pixels);snprintf(message,sizeof(message),"PPA result capacity exhausted; release an image");}
  memset(&out,0,sizeof(out));state=IDLE;}
 k_mutex_unlock(&ppa_lock);return h;
}
void p4_ppa_cancel(void)
{
 k_mutex_lock(&ppa_lock,K_FOREVER);atomic_set(&cancelled,1);
 if(state==READY){dispose();state=IDLE;snprintf(message,sizeof(message),"PPA result discarded");}
 if(state==ERROR)state=IDLE;
 k_mutex_unlock(&ppa_lock);
}
const char *p4_ppa_status(void)
{
 static char copy[sizeof(message)];k_mutex_lock(&ppa_lock,K_FOREVER);memcpy(copy,message,sizeof(copy));k_mutex_unlock(&ppa_lock);return copy;
}
