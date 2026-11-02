/* SPDX-License-Identifier: MPL-2.0 */
/* VM-thread-only service. Camera worker never owns a VM object or RPC buffer. */
#include "vm/interp.h"
#include "pose_camera.h"
#include "camera_backend.h"
#include "camera_wire.h"
#include <zephyr/kernel.h>
#include <stdio.h>
#include <string.h>
enum { IDLE,CAPTURING,READY,ERROR };
enum { OK,BAD,BUSY,DISABLED,NO_MEMORY,TIMED_OUT,CAPTURE_FAILED };
static bool enabled;
static uint32_t session;
static int state,thumbnail,last_error;
static int64_t deadline;
static uint64_t captured_at;
static char message[128]="Pose camera is off; enable it explicitly in your program";
void p4_pose_camera_reset(bool disable){
    if(state==CAPTURING)camera_discard_owned(CAMERA_OWNER_POSE);
    if(thumbnail)image_release(thumbnail);
    thumbnail=0;session=0;state=IDLE;last_error=OK;captured_at=0;
    if(disable)enabled=false;
    snprintf(message,sizeof(message),enabled?"Pose camera idle":"Pose camera is off");
}
void p4_pose_camera_enable(bool value){
    if(!value)p4_pose_camera_reset(true);
    else{enabled=true;snprintf(message,sizeof(message),"Pose camera enabled; waiting for local companion");}
}
static void error(int code,const char *reason){
    if(state==CAPTURING)camera_discard_owned(CAMERA_OWNER_POSE);
    if(thumbnail)image_release(thumbnail);
    thumbnail=0;state=ERROR;last_error=code;
    snprintf(message,sizeof(message),"%s",reason);
    deadline=k_uptime_get()+3000;
}
void p4_pose_camera_poll(void){
    if(!session)return;
    if(k_uptime_get()>=deadline){p4_pose_camera_reset(false);snprintf(message,sizeof(message),"Pose camera lease expired; frame released");return;}
    if(state!=CAPTURING||camera_busy())return;
    captured_at=camera_ready_time_owned(CAMERA_OWNER_POSE);
    int original=camera_result_owned(CAMERA_OWNER_POSE);
    if(!original){error(CAPTURE_FAILED,camera_status());return;}
    thumbnail=image_resize(original,192,108,IMAGE_GRAY8);image_release(original);
    if(!thumbnail){error(NO_MEMORY,"Pose thumbnail allocation failed; release other images");return;}
    state=READY;deadline=k_uptime_get()+5000;
    snprintf(message,sizeof(message),"Pose camera frame ready: 192x108, packed grayscale, 10368 bytes");
}
void p4_pose_camera_status(char *out,size_t n){snprintf(out,n,"%s",message);}
void p4_pose_camera_message(int type,int bytes,const char *body){
    if(type!=211||bytes<0)return;
    pose_camera_request r;if(!pose_camera_decode((const uint8_t *)body,bytes,&r))return;
    /* No mutating operation can happen without room for the largest reply. */
    if(!hasOutputSpace(533))return;
    p4_pose_camera_poll();
    uint8_t out[528]={0};unsigned n=16;int status=OK;
    if(r.operation==0){
        int size=snprintf((char *)out+16,sizeof(out)-16,"{\"enabled\":%s,\"width\":192,\"height\":108,\"bytes\":10368,\"format\":\"GRAY4\",\"chunk\":512}",enabled?"true":"false");
        if(size>0&&size<512)n+=size;else status=BAD;
    }else if(r.operation==1){
        if(!enabled)status=DISABLED;
        else if(session||camera_busy())status=BUSY;
        else if(!camera_request_owned(CAMERA_OWNER_POSE))status=BUSY;
        else{session=r.session;state=CAPTURING;last_error=OK;deadline=k_uptime_get()+8000;snprintf(message,sizeof(message),"Pose camera capturing");}
    }else if(r.session!=session){status=BAD;}
    else if(r.operation==2){
        status=last_error;
        unsigned age=captured_at?(unsigned)(k_uptime_get()-captured_at):0;
        int size=snprintf((char *)out+16,sizeof(out)-16,"{\"width\":192,\"height\":108,\"bytes\":10368,\"age_ms\":%u,\"error\":%d}",age,last_error);
        if(size>0&&size<512)n+=size;else status=BAD;
    }else if(r.operation==3){
        if(state!=READY||!thumbnail||!image_read_gray4(thumbnail,r.offset,out+16,r.count))status=BAD;
        else n+=r.count;
    }else if(r.operation==4){p4_pose_camera_reset(false);}
    pose_camera_reply(out,&r,status,state);
    waitAndSendMessage(211,0,n,(char *)out);
}
