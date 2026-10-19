/* SPDX-License-Identifier: MIT */
#include "zephyr_network_store.h"
#include <zephyr/drivers/flash.h>
#include <errno.h>
#include <string.h>

static bool valid(unsigned slot, size_t offset, size_t size)
{ return slot < 2 && offset <= MBNW_RECORD_SIZE && size <= MBNW_RECORD_SIZE-offset; }
static int read_slot(void *ctx,unsigned slot,size_t off,void *dst,size_t n)
{
    struct mbnw_flash_store *s=ctx;
    return !s->area || !valid(slot,off,n) ? -EINVAL :
        flash_area_read(s->area,s->offsets[slot]+off,dst,n);
}
static int erase_slot(void *ctx,unsigned slot)
{
    struct mbnw_flash_store *s=ctx;
    return !s->area || slot>1 ? -EINVAL :
        flash_area_erase(s->area,s->offsets[slot],s->sizes[slot]);
}
static int write_slot(void *ctx,unsigned slot,size_t off,const void *src,size_t n)
{
    struct mbnw_flash_store *s=ctx;
    if(!s->area || !valid(slot,off,n) || off%s->write_block || n%s->write_block)return -EINVAL;
    return flash_area_write(s->area,s->offsets[slot]+off,src,n);
}
int mbnw_flash_store_open(struct mbnw_flash_store *s,unsigned id)
{
    if(!s)return -EINVAL;
    memset(s,0,sizeof(*s));
    const struct flash_area *area;
    int e=flash_area_open(id,&area);if(e)return e;
    if(!device_is_ready(area->fa_dev)){e=-ENODEV;goto fail;}
    const struct flash_parameters *p=flash_get_parameters(area->fa_dev);
    /* Never round the separate DONE marker into previously committed data. */
    if(!p || !p->write_block_size || 4%p->write_block_size || p->erase_value!=0xff){e=-ENOTSUP;goto fail;}
    size_t next=0;
    for(unsigned i=0;i<2;++i){
        struct flash_pages_info page;
        e=flash_get_page_info_by_offs(area->fa_dev,area->fa_off+next,&page);
        if(e)goto fail;
        if(page.start_offset!=area->fa_off+next || page.size<MBNW_RECORD_SIZE ||
           next>area->fa_size || page.size>area->fa_size-next){e=-EINVAL;goto fail;}
        s->offsets[i]=next;s->sizes[i]=page.size;next+=page.size;
    }
    s->area=area;s->write_block=p->write_block_size;
    s->io=(struct mbnw_store){s,read_slot,erase_slot,write_slot};
    return 0;
fail:
    flash_area_close(area);memset(s,0,sizeof(*s));return e;
}
