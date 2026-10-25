/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "image_store.h"
#include "camera_backend.h"
#include "audio_backend.h"
#include "audio_store.h"

#include <string.h>
#include <stdio.h>
#if defined(CONFIG_ESP_HOSTED_MCU)
#include <zephyr/device.h>
extern uint32_t esp_hosted_mcu_fw_version(void);
#endif
static int integer_args(int n,OBJ *a,int expected) {
    if(n!=expected){fail(notEnoughArguments);return 0;}
    for(int i=0;i<n;i++)if(!isInt(a[i])){fail(needsIntegerError);return 0;}
    return 1;
}
static OBJ request(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return camera_request()?trueObj:falseObj;}
static OBJ busy(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return camera_busy()?trueObj:falseObj;}
static OBJ result(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(camera_result());}
static OBJ status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);const char *s=camera_status();return newStringFromBytes(s,strlen(s));}
static OBJ valid(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;return image_get(obj2int(a[0]))?trueObj:falseObj;}
static const image_view *view(int n,OBJ *a){if(!integer_args(n,a,1))return NULL;const image_view *v=image_get(obj2int(a[0]));if(!v)fail(indexOutOfRangeError);return v;}
static OBJ width(int n,OBJ *a){const image_view *v=view(n,a);return v?int2obj(v->width):falseObj;}
static OBJ height(int n,OBJ *a){const image_view *v=view(n,a);return v?int2obj(v->height):falseObj;}
static OBJ bytes(int n,OBJ *a){const image_view *v=view(n,a);return v?int2obj(v->bytes):falseObj;}
static OBJ format(int n,OBJ *a){const image_view *v=view(n,a);if(!v)return falseObj;const char *s=v->format==1?"GRAY8":v->format==2?"RGB565":"RGB888";return newStringFromBytes(s,strlen(s));}
static OBJ resize(int n,OBJ *a){if(!integer_args(n,a,3))return falseObj;const image_view *v=image_get(obj2int(a[0]));return int2obj(v?image_resize(obj2int(a[0]),obj2int(a[1]),obj2int(a[2]),v->format):0);}
static OBJ gray(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;return int2obj(image_grayscale(obj2int(a[0])));}
/* Explicit tensor contract: uint8 HWC RGB888, no hidden normalization/letterbox. */
static OBJ rgb_tensor(int n,OBJ *a){if(!integer_args(n,a,3))return falseObj;return int2obj(image_resize(obj2int(a[0]),obj2int(a[1]),obj2int(a[2]),IMAGE_RGB888));}
static OBJ release(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;return image_release(obj2int(a[0]))?trueObj:falseObj;}
static OBJ release_all(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);camera_discard();image_release_all();return falseObj;}
static OBJ read_bytes(int n,OBJ *a){
    if(!integer_args(n,a,3))return falseObj;
    int handle=obj2int(a[0]),offset=obj2int(a[1]),count=obj2int(a[2]);
    const image_view *v=image_get(handle);
    if(!v || offset<0 || count<0 || count>512 || (size_t)offset>v->bytes || (size_t)count>v->bytes-offset)return fail(indexOutOfRangeError);
    /* Native view survives newObj/GC. Do not touch args after allocation. */
    OBJ out=newObj(ByteArrayType,(count+3)/4,zeroObj);if(out==falseObj)return out;
    setByteCountAdjust(out,count);memcpy(&FIELD(out,0),v->pixels+offset,count);return out;
}
static OBJ used(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(image_bytes_used());}
static OBJ count(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(image_count());}
static OBJ heap(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return fail(primitiveNotImplemented);}
static OBJ preview(int n,OBJ *a){
    if(!integer_args(n,a,1))return falseObj;
    int h=obj2int(a[0]);
    if(!image_get(h))return fail(indexOutOfRangeError);
    unsigned char data[4]={h,h>>8,h>>16,h>>24};
    if(!hasOutputSpace(9))return falseObj;
    waitAndSendMessage(207,0,4,(char *)data);return trueObj;
}
/* Bounded preview/export extension, serialized on the VM thread. No pointer
 * or image content is placed in the code store or browser project storage. */
void p4_image_message(int type,int n,char *body){
    if(type!=206 || n!=16 || memcmp(body,"P4IM",4))return;
    const unsigned char *p=(unsigned char *)body;
    uint32_t h=p[6]|(uint32_t)p[7]<<8|(uint32_t)p[8]<<16|(uint32_t)p[9]<<24;
    uint32_t offset=p[10]|(uint32_t)p[11]<<8|(uint32_t)p[12]<<16|(uint32_t)p[13]<<24;
    unsigned count=p[14]|(unsigned)p[15]<<8;
    unsigned char response[514]={p[4],1};unsigned length=2;
    const image_view *v=h<=0x3fffffffu?image_get(h):NULL;
    if(v && p[5]==1){
        int size=snprintf((char *)response+2,sizeof(response)-2,"{\"width\":%u,\"height\":%u,\"format\":%u,\"bytes\":%u}",v->width,v->height,v->format,(unsigned)v->bytes);
        if(size>0 && size<(int)sizeof(response)-2){response[1]=0;length+=size;}
    }else if(v && p[5]==2 && count<=512 && image_read(h,offset,response+2,count)){
        response[1]=0;length+=count;
    }
    if(hasOutputSpace(length+5))waitAndSendMessage(206,0,length,(char *)response);
}
static OBJ capabilities(int n,OBJ *a){
    (void)a;if(n)return fail(notEnoughArguments);char s[192];
    int size=snprintf(s,sizeof(s),"{\"runtime\":\"Zephyr\",\"image_store\":true,\"camera_receiver\":%s,\"wifi\":false,\"arduino_api\":false,\"persistent_code\":false}",camera_available()?"true":"false");
    return newStringFromBytes(s,size);
}
static OBJ dsp_capabilities(int n,OBJ *a){
    (void)a;if(n)return fail(notEnoughArguments);
    const char *s="{\"resize_nearest\":\"software\",\"grayscale\":\"software\",\"rgb888_hwc_u8\":\"software\",\"isp_demosaic\":\"hardware\",\"ppa_srm\":\"unsupported\",\"jpeg_encode\":\"unsupported\",\"jpeg_decode\":\"unsupported\",\"h264_encode\":\"unsupported\",\"h264_decode\":\"unsupported\",\"audio_input\":\"native_I2S_PCM_acoustics_unverified\",\"audio_output\":\"unconfigured\",\"inference\":\"unsupported\"}";
    return newStringFromBytes(s,strlen(s));
}
static OBJ ids(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);unsigned imx,ov;p4_sensor_ids(&imx,&ov);char s[64];snprintf(s,sizeof(s),"IMX219=%04x OV5647=%04x",imx,ov);return newStringFromBytes(s,strlen(s));}
static OBJ create(int n,OBJ *a){if(!integer_args(n,a,3))return falseObj;int h=image_create(obj2int(a[0]),obj2int(a[1]),obj2int(a[2]));if(h){const image_view *v=image_get(h);memset(v->pixels,0,v->bytes);}return int2obj(h);}
static OBJ audio_id(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_audio_codec_id());}
static OBJ c6_status(int n,OBJ *a){
    (void)a;if(n)return fail(notEnoughArguments);
    char s[256];
#if defined(CONFIG_ESP_HOSTED_MCU)
    uint32_t v=esp_hosted_mcu_fw_version();
    const struct device *dev=DEVICE_DT_GET(DT_NODELABEL(p4_c6));
    const struct device *slot=DEVICE_DT_GET(DT_PARENT(DT_NODELABEL(p4_c6)));
    int size=snprintf(s,sizeof(s),"{\"transport\":\"SDIO\",\"ready\":%s,\"version_raw\":%u,\"core_error\":%d,\"slot_ready\":%s,\"slot_error\":%d,\"host_wifi_requests\":false}",
        device_is_ready(dev)?"true":"false",v,-dev->state->init_res,device_is_ready(slot)?"true":"false",-slot->state->init_res);
#else
    int size=snprintf(s,sizeof(s),"{\"transport\":\"disabled in USB-only profile\",\"ready\":false}");
#endif
    return newStringFromBytes(s,size);
}
static OBJ audio_request(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;return p4_audio_request(obj2int(a[0]))?trueObj:falseObj;}
static OBJ audio_busy(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_audio_busy()?trueObj:falseObj;}
static OBJ audio_result(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_audio_result());}
static OBJ audio_status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);const char *s=p4_audio_status();return newStringFromBytes(s,strlen(s));}
static OBJ audio_valid(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;return audio_get(obj2int(a[0]))?trueObj:falseObj;}
static OBJ audio_frames(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;const audio_view *v=audio_get(obj2int(a[0]));return v?int2obj(v->frames):fail(indexOutOfRangeError);}
static OBJ audio_rate(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;const audio_view *v=audio_get(obj2int(a[0]));return v?int2obj(v->rate):fail(indexOutOfRangeError);}
static OBJ audio_peak(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;unsigned p,r;return audio_stats(obj2int(a[0]),&p,&r)?int2obj(p):fail(indexOutOfRangeError);}
static OBJ audio_rms(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;unsigned p,r;return audio_stats(obj2int(a[0]),&p,&r)?int2obj(r):fail(indexOutOfRangeError);}
static OBJ audio_release_one(int n,OBJ *a){if(!integer_args(n,a,1))return falseObj;return audio_release(obj2int(a[0]))?trueObj:falseObj;}
static OBJ audio_release_every(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);p4_audio_discard();audio_release_all();return falseObj;}
static OBJ audio_memory(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(audio_bytes_used());}
static OBJ audio_handles(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(audio_count());}
static OBJ audio_read_bytes(int n,OBJ *a){
    if(!integer_args(n,a,3))return falseObj;
    int h=obj2int(a[0]),offset=obj2int(a[1]),count=obj2int(a[2]);
    const audio_view *v=audio_get(h);
    if(!v || offset<0 || count<0 || count>512 || (size_t)offset>v->frames*2 || (size_t)count>v->frames*2-offset)return fail(indexOutOfRangeError);
    OBJ out=newObj(ByteArrayType,(count+3)/4,zeroObj);if(out==falseObj)return out;
    setByteCountAdjust(out,count);audio_read(h,offset,(uint8_t *)&FIELD(out,0),count);return out;
}
static PrimEntry entries[]={
 {"c6Status",c6_status},
 {"audioCodecID",audio_id},{"audioRequest",audio_request},{"audioBusy",audio_busy},{"audioResult",audio_result},{"audioStatus",audio_status},
 {"audioValid",audio_valid},{"audioFrames",audio_frames},{"audioRate",audio_rate},{"audioPeak",audio_peak},{"audioRMS",audio_rms},
 {"audioRelease",audio_release_one},{"audioReleaseAll",audio_release_every},{"audioRead",audio_read_bytes},{"audioMemory",audio_memory},{"audioCount",audio_handles},
 {"capabilities",capabilities},{"dspCapabilities",dsp_capabilities},{"sensorIDs",ids},{"imageCreate",create},
 {"cameraRequest",request},{"cameraBusy",busy},{"cameraResult",result},{"cameraStatus",status},
 {"imageValid",valid},{"imageWidth",width},{"imageHeight",height},{"imageBytes",bytes},{"imageFormat",format},
 {"imageResize",resize},{"imageGrayscale",gray},{"imageRGBTensor",rgb_tensor},{"imageRead",read_bytes},
 {"imageRelease",release},{"imageReleaseAll",release_all},{"imageMemory",used},{"imageCount",count},{"freePSRAM",heap},{"imagePreview",preview}};
void addIOPrims(void){addPrimitiveSet(IOPrims,"p4",sizeof(entries)/sizeof(entries[0]),entries);}
