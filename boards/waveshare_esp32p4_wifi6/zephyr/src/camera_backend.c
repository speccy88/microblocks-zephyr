/* SPDX-License-Identifier: MIT */
#include <zephyr/kernel.h>
#include <zephyr/cache.h>
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <zephyr/sys/atomic.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "camera_backend.h"
#include "p4_video.h"
void *image_alloc(size_t n){return shared_multi_heap_aligned_alloc(SMH_REG_ATTR_EXTERNAL,64,n);}
void image_free(void *p){if(p)shared_multi_heap_free(p);}
K_SEM_DEFINE(requested,0,1);
K_MUTEX_DEFINE(state_mutex);
static atomic_t cancelled;
enum { IDLE, CAPTURING, READY, ERROR, QUARANTINED };
static int state;
static image_view frame;
static const char *capture_stage="idle"; /* worker only; copied at completion */
static char message[192]="native Zephyr: idle; sensor/CSI capture available for test";
bool p4_capture_cancelled(void){return atomic_get(&cancelled)!=0;}
int camera_available(void){return device_is_ready(p4_csi_device());}

/* Runs on the dedicated Zephyr camera thread. Contains no SmallVM objects.
 * Store adoption is deferred to camera_result() on the VM thread. */
int p4_video_capture(image_view *out)
{
    capture_stage="format";
    const struct device *dev=p4_csi_device();
    if(!device_is_ready(dev))return -ENODEV;
    struct video_format fmt={.type=VIDEO_BUF_TYPE_OUTPUT};
    int error=video_get_format(dev,&fmt);
    if(error)return error;
    if(fmt.width>IMAGE_MAX_WIDTH || fmt.height>IMAGE_MAX_HEIGHT ||
       fmt.pixelformat!=VIDEO_PIX_FMT_RGB565 || fmt.size!=fmt.width*fmt.height*2 ||
       (fmt.size&63))return -EINVAL;
    uint8_t *pixels=image_alloc(fmt.size+64);if(!pixels)return -ENOMEM;
    memset(pixels,0,fmt.size);memset(pixels+fmt.size,0xa5,64);
    /* Flush the guard too: invalidating a dirty, never-flushed guard would
     * discard our marker and falsely report DMA overflow. */
    error=sys_cache_data_flush_range(pixels,fmt.size+64);
    /* Public video_enqueue resolves by registered pool index. Import external
     * storage instead of passing an unregistered stack video_buffer. */
    struct video_buffer *b=video_import_buffer(pixels,fmt.size);
    if(!b){image_free(pixels);return -ENOMEM;}
    b->type=VIDEO_BUF_TYPE_OUTPUT;
    struct video_buffer *done=NULL;
    if(!error)error=video_set_format(dev,&fmt);
    if(!error){capture_stage="enqueue";error=video_enqueue(dev,b);}
    if(!error){capture_stage="start";error=video_stream_start(dev,VIDEO_BUF_TYPE_OUTPUT);}
    if(!error){capture_stage="frame";error=video_dequeue(dev,&done,K_SECONDS(3));}
    int stopped=video_stream_stop(dev,VIDEO_BUF_TYPE_OUTPUT);
    if(stopped==-EBUSY){
        /* Never free memory that an unquiesced DMA might still write. */
        *out=(image_view){fmt.width,fmt.height,fmt.pitch,IMAGE_RGB565,fmt.size,pixels};
        return -EBUSY;
    }
    video_driver_flush(dev,true);
    if(!error)error=stopped;
    if(!error && (done!=b || b->bytesused!=fmt.size))error=-EIO;
    video_buffer_release(b); /* external storage remains owned by us */
    int cache_error=sys_cache_data_invd_range(pixels,fmt.size+64);
    if(!error)error=cache_error;
    for(unsigned i=0;i<64;i++)if(pixels[fmt.size+i]!=0xa5){capture_stage="guard";error=-EOVERFLOW;}
    if(!error && p4_capture_cancelled())error=-ECANCELED;
    if(error){image_free(pixels);return error;}
    *out=(image_view){fmt.width,fmt.height,fmt.pitch,IMAGE_RGB565,fmt.size,pixels};
    return 0;
}
static void worker(void *a,void *b,void *c)
{
    ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);
    for(;;){
        k_sem_take(&requested,K_FOREVER);
        image_view result={0};int error=p4_video_capture(&result);
        k_mutex_lock(&state_mutex,K_FOREVER);
        if(error==-EBUSY && result.pixels){frame=result;state=QUARANTINED;
            snprintf(message,sizeof(message),"DMA shutdown failed; buffer retained; reset required");}
        else if(p4_capture_cancelled()){
            if(result.pixels)image_free(result.pixels);
            state=IDLE;
            snprintf(message,sizeof(message),"native Zephyr: cancelled; sensor stopped");
        }else if(error){state=ERROR;
            snprintf(message,sizeof(message),"capture error %d at %s; %s; sensor stopped",error,capture_stage,p4_video_diagnostic());}
        else{frame=result;state=READY;
            snprintf(message,sizeof(message),"native Zephyr: %ux%u RGB565 ready; sensor stopped",result.width,result.height);}
        k_mutex_unlock(&state_mutex);
    }
}
K_THREAD_DEFINE(camera_thread,8192,worker,NULL,NULL,NULL,6,0,0);
int camera_request(void)
{
    k_mutex_lock(&state_mutex,K_FOREVER);
    if(state==CAPTURING || state==READY || state==QUARANTINED){k_mutex_unlock(&state_mutex);return 0;}
    if(!device_is_ready(p4_csi_device()) || image_count()==IMAGE_SLOTS ||
       image_bytes_used()+IMAGE_MAX_WIDTH*IMAGE_MAX_HEIGHT*2>IMAGE_BUDGET){
        snprintf(message,sizeof(message),"camera unavailable or image capacity exhausted");
        k_mutex_unlock(&state_mutex);return 0;
    }
    atomic_clear(&cancelled);state=CAPTURING;
    snprintf(message,sizeof(message),"native Zephyr: capturing");
    k_sem_give(&requested);k_mutex_unlock(&state_mutex);return 1;
}
int camera_busy(void)
{ k_mutex_lock(&state_mutex,K_FOREVER);int busy=state==CAPTURING;k_mutex_unlock(&state_mutex);return busy; }
int camera_result(void)
{
    k_mutex_lock(&state_mutex,K_FOREVER);int handle=0;
    if(state==READY){handle=image_adopt(frame.width,frame.height,frame.format,frame.pixels,frame.bytes);
        if(!handle){image_free(frame.pixels);snprintf(message,sizeof(message),"image capacity exhausted; capture released");}
        memset(&frame,0,sizeof(frame));state=IDLE;}
    else if(state==ERROR)state=IDLE;
    k_mutex_unlock(&state_mutex);return handle;
}
void camera_discard(void)
{
    k_mutex_lock(&state_mutex,K_FOREVER);atomic_set(&cancelled,1);
    if(state==READY){image_free(frame.pixels);memset(&frame,0,sizeof(frame));state=IDLE;}
    if(state==ERROR)state=IDLE;
    k_mutex_unlock(&state_mutex);
}
const char *camera_status(void)
{
    static char snapshot[sizeof(message)];
    k_mutex_lock(&state_mutex,K_FOREVER);memcpy(snapshot,message,sizeof(message));k_mutex_unlock(&state_mutex);
    return snapshot;
}
