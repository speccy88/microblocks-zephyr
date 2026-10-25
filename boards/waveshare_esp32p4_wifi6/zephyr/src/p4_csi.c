/*
 * SPDX-FileCopyrightText: 2023-2025 Espressif Systems (Shanghai) CO LTD
 * SPDX-License-Identifier: Apache-2.0
 *
 * Native Zephyr P4 CSI/ISP one-frame receiver. Register setup follows the
 * Apache-2.0 esp_cam_ctlr_csi.c, dw_gdma.c and isp_core.c in ESP-IDF 5.5.5,
 * using the HAL bundled with pinned Zephyr. Scheduling, buffers, timeout,
 * power and video interfaces are Zephyr; no vendor RTOS driver is linked.
 * Owns the dedicated DW-GDMA controller exclusively (not AHB/AXI GDMA).
 */
#include "p4_video.h"
#include "video_common.h"
#include <zephyr/cache.h>
#include <zephyr/drivers/regulator.h>
#include <hal/mipi_csi_hal.h>
#include <hal/mipi_csi_ll.h>
#include <hal/mipi_csi_brg_ll.h>
#include <hal/dw_gdma_hal.h>
#include <hal/dw_gdma_ll.h>
#include <hal/isp_ll.h>
#include <esp_private/esp_clk_tree_common.h>
#include <soc/clk_tree_defs.h>
#include <soc/soc.h>
#include <stdio.h>
#include <errno.h>

static const struct device *const supply=DEVICE_DT_GET(DT_NODELABEL(ldo3));
static const struct device *source;
DEVICE_DECLARE(p4_csi);
VIDEO_DEVICE_DEFINE(p4_csi_video,DEVICE_GET(p4_csi),NULL);
static struct k_spinlock rcc_lock;
static struct {
    mipi_csi_hal_context_t csi;
    dw_gdma_hal_context_t dma;
    struct video_format fmt;
    struct video_format_cap caps[2];
    struct video_buffer *buffer;
    bool streaming, powered, clocks;
    uint32_t events, transferred, isp_events;
    char diagnostic[128];
} rx;

const char *p4_video_diagnostic(void) { return rx.diagnostic; } /* worker only */
static int hw_init(void)
{
    if(esp_clk_tree_enable_src(MIPI_CSI_PHY_CLK_SRC_DEFAULT,true) ||
       esp_clk_tree_enable_src(ISP_CLK_SRC_DEFAULT,true)) return -EIO;
    k_spinlock_key_t key=k_spin_lock(&rcc_lock);
    mipi_csi_ll_enable_host_bus_clock(0,false);
    mipi_csi_ll_enable_host_bus_clock(0,true);
    mipi_csi_ll_reset_host_clock(0);
    mipi_csi_ll_enable_brg_module_clock(0,true);
    mipi_csi_ll_reset_brg_module_clock(0);
    mipi_csi_ll_set_phy_clock_source(0,MIPI_CSI_PHY_CLK_SRC_DEFAULT);
    mipi_csi_ll_enable_phy_config_clock(0,false);
    mipi_csi_ll_enable_phy_config_clock(0,true);
    isp_ll_enable_module_clock(true); isp_ll_reset_module_clock();
    isp_ll_select_clk_source(ISP_CLK_SRC_DEFAULT);
    hal_utils_clk_div_t div={.integer=1}; /* same 240 MHz as tested source */
    isp_ll_set_clock_div(&div);
    dw_gdma_ll_enable_bus_clock(0,true); dw_gdma_ll_reset_register(0);
    k_spin_unlock(&rcc_lock,key);
    rx.clocks=true;
    rx.dma.dev=DW_GDMA_LL_GET_HW(0);
    mipi_csi_hal_config_t cfg={.frame_height=rx.fmt.width,.frame_width=rx.fmt.height,
        .lanes_num=2,.lane_bit_rate_mbps=400,.byte_swap_en=false};
    mipi_csi_hal_init(&rx.csi,&cfg);
    mipi_csi_brg_ll_enable_clock(rx.csi.bridge_dev,true);
    mipi_csi_brg_ll_enable(rx.csi.bridge_dev,false);
    mipi_csi_brg_ll_set_burst_len(rx.csi.bridge_dev,512);

    isp_dev_t *isp=ISP_LL_GET_HW(0);
    isp_ll_init(isp);
    if(!isp_ll_set_input_data_color_format(isp,p4_sensor_bits()==10?ISP_COLOR_RAW10:ISP_COLOR_RAW8) ||
       !isp_ll_set_output_data_color_format(isp,ISP_COLOR_RGB565))return -ENOTSUP;
    isp_ll_clk_enable(isp,true);
    isp_ll_set_input_data_source(isp,ISP_INPUT_DATA_SOURCE_CSI);
    isp_ll_enable_line_start_packet_exist(isp,false);
    isp_ll_enable_line_end_packet_exist(isp,false);
    isp_ll_set_intput_data_h_pixel_num(isp,rx.fmt.width);
    isp_ll_set_intput_data_v_row_num(isp,rx.fmt.height);
    isp_ll_set_bayer_mode(isp,p4_sensor_bits()==10?COLOR_RAW_ELEMENT_ORDER_RGGB:COLOR_RAW_ELEMENT_ORDER_GBRG);
    isp_ll_yuv_set_std(isp,ISP_YUV_CONV_STD_BT601);
    isp_ll_yuv_set_range(isp,ISP_COLOR_RANGE_FULL);
    isp_ll_shadow_set_mode(isp,ISP_SHADOW_MODE_UPDATE_ONLY_NEXT_VSYNC);
    isp_ll_enable(isp,true);

    dw_gdma_hal_config_t dc={}; dw_gdma_hal_init(&rx.dma,&dc);
    dw_gdma_dev_t *d=rx.dma.dev;
    dw_gdma_ll_channel_set_trans_flow(d,0,DW_GDMA_ROLE_PERIPH_CSI,DW_GDMA_ROLE_MEM,DW_GDMA_FLOW_CTRL_SRC);
    dw_gdma_ll_channel_set_src_multi_block_type(d,0,DW_GDMA_BLOCK_TRANSFER_CONTIGUOUS);
    dw_gdma_ll_channel_set_dst_multi_block_type(d,0,DW_GDMA_BLOCK_TRANSFER_CONTIGUOUS);
    dw_gdma_ll_channel_set_src_handshake_interface(d,0,DW_GDMA_HANDSHAKE_HW);
    dw_gdma_ll_channel_set_dst_handshake_interface(d,0,DW_GDMA_HANDSHAKE_HW);
    dw_gdma_ll_channel_set_src_handshake_periph(d,0,DW_GDMA_ROLE_PERIPH_CSI);
    dw_gdma_ll_channel_set_priority(d,0,1);
    dw_gdma_ll_channel_set_src_outstanding_limit(d,0,5);
    dw_gdma_ll_channel_set_dst_outstanding_limit(d,0,5);
    dw_gdma_ll_channel_set_src_periph_status_addr(d,0,MIPI_CSI_BRG_MEM_BASE);
    dw_gdma_ll_channel_set_dst_periph_status_addr(d,0,0);
    dw_gdma_ll_channel_enable_intr_generation(d,0,UINT32_MAX,true);
    dw_gdma_ll_channel_enable_intr_propagation(d,0,UINT32_MAX,false); /* worker polls */
    dw_gdma_ll_channel_clear_intr(d,0,UINT32_MAX);
    uintptr_t dst=(uintptr_t)rx.buffer->buffer;
    dw_gdma_ll_channel_set_src_addr(d,0,MIPI_CSI_BRG_MEM_BASE);
    dw_gdma_ll_channel_set_dst_addr(d,0,dst);
    dw_gdma_ll_channel_set_trans_block_size(d,0,rx.fmt.size/8);
    dw_gdma_ll_channel_set_src_master_port(d,0,MIPI_CSI_BRG_MEM_BASE);
    dw_gdma_ll_channel_set_dst_master_port(d,0,dst);
    dw_gdma_ll_channel_set_src_trans_width(d,0,DW_GDMA_TRANS_WIDTH_64);
    dw_gdma_ll_channel_set_dst_trans_width(d,0,DW_GDMA_TRANS_WIDTH_64);
    dw_gdma_ll_channel_set_src_burst_items(d,0,DW_GDMA_BURST_ITEMS_512);
    dw_gdma_ll_channel_set_dst_burst_items(d,0,DW_GDMA_BURST_ITEMS_512);
    dw_gdma_ll_channel_set_src_burst_mode(d,0,DW_GDMA_BURST_MODE_FIXED);
    dw_gdma_ll_channel_set_dst_burst_mode(d,0,DW_GDMA_BURST_MODE_INCREMENT);
    dw_gdma_ll_channel_set_src_burst_len(d,0,16);
    dw_gdma_ll_channel_set_dst_burst_len(d,0,16);
    dw_gdma_ll_channel_enable_src_periph_status_write_back(d,0,false);
    dw_gdma_ll_channel_enable_dst_periph_status_write_back(d,0,false);
    return 0;
}

static int stop(const struct device *dev)
{
    ARG_UNUSED(dev); int error=0;
    if(rx.clocks) {
        mipi_csi_brg_ll_enable(rx.csi.bridge_dev,false);
        dw_gdma_ll_channel_abort(rx.dma.dev,0);
        dw_gdma_ll_channel_enable(rx.dma.dev,0,false);
        int64_t until=k_uptime_get()+100;
        while((rx.dma.dev->chen0.val&1) && k_uptime_get()<until)k_sleep(K_MSEC(1));
        /* A bounded bus reset also quiesces an aborted peripheral transfer.
         * No other DW-DMA client is compiled/enabled in this target. */
        k_spinlock_key_t key=k_spin_lock(&rcc_lock);
        dw_gdma_ll_reset_register(0);
        k_spin_unlock(&rcc_lock,key);
        if(rx.dma.dev->chen0.val&1)return -EBUSY; /* caller MUST retain buffer */
        isp_ll_enable(ISP_LL_GET_HW(0),false);
        isp_ll_clk_enable(ISP_LL_GET_HW(0),false);
        mipi_csi_brg_ll_enable_clock(rx.csi.bridge_dev,false);
        key=k_spin_lock(&rcc_lock);
        mipi_csi_ll_enable_phy_config_clock(0,false);
        mipi_csi_ll_enable_host_bus_clock(0,false);
        mipi_csi_ll_enable_brg_module_clock(0,false);
        isp_ll_enable_module_clock(false);
        dw_gdma_ll_enable_bus_clock(0,false);
        k_spin_unlock(&rcc_lock,key);
        rx.clocks=false;
        esp_clk_tree_enable_src(MIPI_CSI_PHY_CLK_SRC_DEFAULT,false);
        esp_clk_tree_enable_src(ISP_CLK_SRC_DEFAULT,false);
    }
    error=video_driver_set_stream(source,false,VIDEO_BUF_TYPE_OUTPUT);
    if(rx.powered){int e=regulator_disable(supply); if(!error)error=e; rx.powered=false;}
    rx.streaming=false;
    return error;
}
static int stream(const struct device *dev,bool enable,enum video_buf_type type)
{
    if(type!=VIDEO_BUF_TYPE_OUTPUT)return -ENOTSUP;
    if(!enable)return stop(dev);
    if(rx.streaming || !rx.buffer)return -EBUSY;
    rx.events=rx.transferred=rx.isp_events=0;
    struct video_format raw={.type=VIDEO_BUF_TYPE_OUTPUT};
    int e=video_driver_get_format(source,&raw);
    if(!e)e=video_driver_set_format(source,&raw);
    if(!e)e=regulator_enable(supply);
    if(e)return e;
    rx.powered=true;
    e=sys_cache_data_flush_and_invd_range(rx.buffer->buffer,rx.fmt.size);
    if(!e)e=hw_init();
    if(e){stop(dev);return e;}
    rx.streaming=true;
    dw_gdma_ll_channel_enable(rx.dma.dev,0,true);
    mipi_csi_brg_ll_enable(rx.csi.bridge_dev,true);
    e=video_driver_set_stream(source,true,VIDEO_BUF_TYPE_OUTPUT);
    if(e)stop(dev);
    return e;
}
static int enqueue(const struct device *dev,struct video_buffer *b)
{
    ARG_UNUSED(dev);
    if(rx.buffer || rx.streaming)return -EBUSY;
    if(!b || b->type!=VIDEO_BUF_TYPE_OUTPUT || b->memory!=VIDEO_MEMORY_EXTERNAL ||
       !b->buffer || ((uintptr_t)b->buffer&63) || b->size<rx.fmt.size)return -EINVAL;
    b->bytesused=0;rx.buffer=b; return 0;
}
static int dequeue(const struct device *dev,struct video_buffer **b,k_timeout_t timeout)
{
    ARG_UNUSED(dev);
    if(!rx.streaming || !rx.buffer)return -EPIPE;
    k_timepoint_t deadline=sys_timepoint_calc(timeout);
    int error=-ETIMEDOUT;
    do {
        rx.events=dw_gdma_ll_channel_get_intr_status(rx.dma.dev,0);
        rx.transferred=dw_gdma_ll_channel_get_trans_amount(rx.dma.dev,0);
        rx.isp_events=isp_ll_get_intr_status(ISP_LL_GET_HW(0));
        if(p4_capture_cancelled()){error=-ECANCELED;break;}
        if(rx.events&0x3fe0){error=-EIO;break;}
        if(rx.events&DW_GDMA_LL_CHANNEL_EVENT_DMA_TFR_DONE){error=0;break;}
        k_sleep(K_MSEC(1));
    } while(!sys_timepoint_expired(deadline));
    snprintf(rx.diagnostic,sizeof(rx.diagnostic),"CSI %d dma=%08x count=%u isp=%08x",
        error,rx.events,rx.transferred,rx.isp_events);
    if(error)return error;
    if(rx.dma.dev->chen0.val&1)return -EIO;
    error=sys_cache_data_invd_range(rx.buffer->buffer,rx.fmt.size);
    if(error)return error;
    rx.buffer->bytesused=rx.fmt.size;rx.buffer->timestamp=k_uptime_get_32();
    *b=rx.buffer; rx.buffer=NULL; return 0;
}
static int flush(const struct device *dev,bool cancel)
{ if(!cancel)return rx.buffer?-EBUSY:0; int e=stop(dev);if(e!=-EBUSY)rx.buffer=NULL;return e; }
static int get_fmt(const struct device *dev,struct video_format *f)
{ ARG_UNUSED(dev);if(f->type!=VIDEO_BUF_TYPE_OUTPUT)return -ENOTSUP;*f=rx.fmt;return 0; }
static int set_fmt(const struct device *dev,struct video_format *f)
{
    ARG_UNUSED(dev);if(rx.streaming || rx.buffer)return -EBUSY;
    if(f->type!=VIDEO_BUF_TYPE_OUTPUT || f->pixelformat!=VIDEO_PIX_FMT_RGB565 ||
       f->width!=rx.fmt.width || f->height!=rx.fmt.height)return -ENOTSUP;
    *f=rx.fmt;return 0;
}
static int caps(const struct device *dev,struct video_caps *c)
{ ARG_UNUSED(dev);if(c->type!=VIDEO_BUF_TYPE_OUTPUT)return -ENOTSUP;
  c->format_caps=rx.caps;c->min_vbuf_count=1;c->buf_align=64;return 0; }
static int init(const struct device *dev)
{
    ARG_UNUSED(dev);source=p4_sensor_device();p4_csi_video.src_dev=source;
    if(!device_is_ready(source)||!device_is_ready(supply))return -ENODEV;
    struct video_format raw={.type=VIDEO_BUF_TYPE_OUTPUT};
    int e=video_driver_get_format(source,&raw);if(e)return e;
    rx.fmt=(struct video_format){.type=VIDEO_BUF_TYPE_OUTPUT,.pixelformat=VIDEO_PIX_FMT_RGB565,
        .width=raw.width,.height=raw.height,.pitch=raw.width*2,.size=raw.width*raw.height*2};
    rx.caps[0]=(struct video_format_cap){.pixelformat=VIDEO_PIX_FMT_RGB565,
        .width_min=raw.width,.width_max=raw.width,.height_min=raw.height,.height_max=raw.height};
    return 0;
}
static DEVICE_API(video,api)={.set_format=set_fmt,.get_format=get_fmt,.get_caps=caps,
    .set_stream=stream,.enqueue=enqueue,.dequeue=dequeue,.flush=flush};
DEVICE_DEFINE(p4_csi,"P4 CSI/ISP",init,NULL,&rx,NULL,POST_KERNEL,61,&api);
const struct device *p4_csi_device(void){return DEVICE_GET(p4_csi);}
