/*
 * Copyright (c) 2022-2023 Circuit Valley
 * Copyright (c) 2024-2025 tinyVision.ai Inc.
 * Copyright (c) 2025 Espressif Systems (Shanghai) CO LTD
 * SPDX-License-Identifier: Apache-2.0
 *
 * IMX219 initialization from tested private source fc60acb, itself adapted
 * from Zephyr imx219.c bc5d59d1. Native Zephyr I2C/video adapter and manual
 * 1280x720 crop. OV5647 table retains its Espressif notice in ov5647_mode.h.
 * No FreeRTOS, sensor GPIO, autofocus, auto exposure or test pattern.
 */
#include "p4_video.h"
#include <zephyr/drivers/i2c.h>
#include "video_common.h"
#include <errno.h>

static const struct device *const bus = DEVICE_DT_GET(DT_NODELABEL(i2c0));
struct sensor_data { unsigned id, address, bits; struct video_format fmt;
    struct video_format_cap caps[2]; bool configured, streaming; };
static struct sensor_data sensor;
#define TRY(expr) do { int e_ = (expr); if (e_) return e_; } while (0)
static int rd16(unsigned addr, unsigned reg, unsigned *value)
{
    uint8_t r[2] = {reg >> 8, reg}, v[2];
    if (!device_is_ready(bus)) return -ENODEV;
    int e = i2c_write_read(bus, addr, r, 2, v, 2);
    if (!e) *value = (unsigned)v[0] << 8 | v[1];
    return e;
}
int p4_sensor_ids(unsigned *imx, unsigned *ov)
{
    *imx = *ov = 0;
    int a = rd16(0x10, 0, imx), b = rd16(0x36, 0x300a, ov);
    return a && b ? -ENODEV : 0;
}
unsigned p4_sensor_bits(void) { return sensor.bits; }
static int wr8(unsigned reg, unsigned value)
{
    uint8_t p[3] = {reg >> 8, reg, value};
    return i2c_write(bus, p, 3, sensor.address);
}
static int wr16(unsigned reg, unsigned value)
{ TRY(wr8(reg, value >> 8)); return wr8(reg + 1, value); }
static int configure_imx(void)
{
    TRY(wr8(0x0103, 1)); k_sleep(K_MSEC(10)); TRY(wr8(0x0100, 0));
    const uint16_t vendor[][2] = {
        {0x30eb,0x05},{0x30eb,0x0c},{0x300a,0xff},{0x300b,0xff},
        {0x30eb,0x05},{0x30eb,0x09},{0x455e,0x00},{0x471e,0x4b},
        {0x4767,0x0f},{0x4750,0x14},{0x4540,0x00},{0x47b4,0x14},
        {0x4713,0x30},{0x478b,0x10},{0x478f,0x10},{0x4793,0x10},
        {0x4797,0x0e},{0x479b,0x0e}};
    for (unsigned i=0; i<ARRAY_SIZE(vendor); i++) TRY(wr8(vendor[i][0],vendor[i][1]));
    TRY(wr8(0x0114,1)); TRY(wr8(0x0128,0)); TRY(wr16(0x012a,24<<8));
    TRY(wr8(0x0304,3)); TRY(wr8(0x0305,3)); TRY(wr8(0x0301,4));
    TRY(wr8(0x0303,1)); TRY(wr8(0x0309,10)); TRY(wr8(0x030b,1));
    TRY(wr16(0x0306,30)); TRY(wr16(0x030c,50));
    TRY(wr16(0x0162,3448)); TRY(wr16(0x0160,1160));
    TRY(wr8(0x0170,1)); TRY(wr8(0x0171,1)); TRY(wr8(0x0174,0));
    TRY(wr8(0x0175,0)); TRY(wr8(0x0172,0));
    TRY(wr16(0x0164,1000)); TRY(wr16(0x0166,2279));
    TRY(wr16(0x0168,872)); TRY(wr16(0x016a,1591));
    TRY(wr16(0x016c,1280)); TRY(wr16(0x016e,720));
    TRY(wr16(0x018c,0x0a0a)); TRY(wr16(0x0624,1280)); TRY(wr16(0x0626,720));
    TRY(wr16(0x0600,0)); /* real imaging, pattern OFF */
    TRY(wr16(0x0158,256)); TRY(wr8(0x0157,128)); return wr16(0x015a,800);
}
#include "ov5647_mode.h"
static int configure_ov(void)
{
    TRY(wr8(0x0100,0)); TRY(wr8(0x0103,1)); k_sleep(K_MSEC(10));
    TRY(wr8(0x4800,0x25));
    for(unsigned i=0; i<ARRAY_SIZE(ov_mode); i++) TRY(wr8(ov_mode[i][0],ov_mode[i][1]));
    TRY(wr8(0x5000,0x06)); /* tested source: no lens-shading table */
    return wr8(0x503d,0); /* test pattern OFF */
}
static int get_fmt(const struct device *dev, struct video_format *fmt)
{ ARG_UNUSED(dev); if(fmt->type!=VIDEO_BUF_TYPE_OUTPUT)return -ENOTSUP; *fmt=sensor.fmt; return 0; }
static int set_fmt(const struct device *dev, struct video_format *fmt)
{
    ARG_UNUSED(dev);
    if(sensor.streaming)return -EBUSY;
    if(fmt->type!=VIDEO_BUF_TYPE_OUTPUT || fmt->width!=sensor.fmt.width ||
       fmt->height!=sensor.fmt.height || fmt->pixelformat!=sensor.fmt.pixelformat)return -ENOTSUP;
    unsigned id=0;
    TRY(rd16(sensor.address,sensor.id==0x0219?0:0x300a,&id));
    if(id!=sensor.id)return -ENODEV; /* identify before ANY sensor write */
    sensor.configured=false;
    TRY(sensor.id==0x0219?configure_imx():configure_ov());
    sensor.configured=true; *fmt=sensor.fmt; return 0;
}
static int stream(const struct device *dev, bool enable, enum video_buf_type type)
{
    ARG_UNUSED(dev); if(type!=VIDEO_BUF_TYPE_OUTPUT)return -ENOTSUP;
    if(enable && !sensor.configured)return -EPIPE;
    if(sensor.id==0x5647)TRY(wr8(0x4800,enable?0x24:0x25));
    TRY(wr8(0x0100,enable?1:0)); sensor.streaming=enable; return 0;
}
static int caps(const struct device *dev,struct video_caps *c)
{ ARG_UNUSED(dev); if(c->type!=VIDEO_BUF_TYPE_OUTPUT)return -ENOTSUP;
  c->format_caps=sensor.caps; c->min_vbuf_count=0; c->buf_align=1; return 0; }
static int init(const struct device *dev)
{
    ARG_UNUSED(dev); unsigned imx,ov; TRY(p4_sensor_ids(&imx,&ov));
    if(imx==0x0219){sensor.id=imx;sensor.address=0x10;sensor.bits=10;
        sensor.fmt=(struct video_format){.width=1280,.height=720,.pixelformat=VIDEO_PIX_FMT_SRGGB10P};}
    else if(ov==0x5647){sensor.id=ov;sensor.address=0x36;sensor.bits=8;
        sensor.fmt=(struct video_format){.width=800,.height=640,.pixelformat=VIDEO_PIX_FMT_SGBRG8};}
    else return -ENODEV;
    sensor.fmt.type=VIDEO_BUF_TYPE_OUTPUT;
    sensor.fmt.pitch=sensor.fmt.width*sensor.bits/8;
    sensor.fmt.size=sensor.fmt.pitch*sensor.fmt.height;
    sensor.caps[0]=(struct video_format_cap){.pixelformat=sensor.fmt.pixelformat,
        .width_min=sensor.fmt.width,.width_max=sensor.fmt.width,
        .height_min=sensor.fmt.height,.height_max=sensor.fmt.height};
    return 0;
}
static DEVICE_API(video, api)={.set_format=set_fmt,.get_format=get_fmt,.get_caps=caps,.set_stream=stream};
DEVICE_DEFINE(p4_sensor,"P4 camera sensor",init,NULL,&sensor,NULL,POST_KERNEL,60,&api);
VIDEO_DEVICE_DEFINE(p4_sensor_video,DEVICE_GET(p4_sensor),NULL);
const struct device *p4_sensor_device(void){return DEVICE_GET(p4_sensor);}
