/* SPDX-License-Identifier: MIT
 * Actual Zephyr backend under synthetic flash geometry and NOR semantics.
 * Does not access a board. Existing journal tests cover power-cut contents. */
#include "zephyr_network_store.h"
#include <zephyr/drivers/flash.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../boards/sparkfun_xrp_rp2350/arduino/pin_policy.h"

static unsigned checks,erases,writes;
#define CHECK(v) do { ++checks;if(!(v)){fprintf(stderr,"check failed line %d\n",__LINE__);exit(1);} } while(0)
static struct device dev={true};
static struct flash_area area={&dev,128,256};
static struct flash_parameters params={1,0xff};
static uint8_t memory[256];
static size_t page_size=128;
static bool misaligned;
int flash_area_open(unsigned id,const struct flash_area **out)
{ if(id!=7)return -ENOENT;*out=&area;return 0; }
void flash_area_close(const struct flash_area *a) { (void)a; }
const struct flash_parameters *flash_get_parameters(const struct device *d) { (void)d;return &params; }
int flash_get_page_info_by_offs(const struct device *d,size_t off,struct flash_pages_info *out)
{
    (void)d;out->start_offset=off-(misaligned?1:0);out->size=page_size;return 0;
}
int flash_area_read(const struct flash_area *a,size_t off,void *dst,size_t n)
{ if(off>a->fa_size || n>a->fa_size-off)return -EINVAL;memcpy(dst,memory+off,n);return 0; }
int flash_area_erase(const struct flash_area *a,size_t off,size_t n)
{
    CHECK(off%page_size==0);CHECK(n==page_size);CHECK(off+n<=a->fa_size);
    ++erases;memset(memory+off,0xff,n);return 0;
}
int flash_area_write(const struct flash_area *a,size_t off,const void *src,size_t n)
{
    CHECK(off+n<=a->fa_size);CHECK(off%params.write_block_size==0);CHECK(n%params.write_block_size==0);
    const uint8_t *p=src;
    for(size_t i=0;i<n;++i)if((memory[off+i]&p[i])!=p[i])return -EIO;
    for(size_t i=0;i<n;++i)memory[off+i]&=p[i];
    ++writes;return 0;
}
int main(void)
{
    static const unsigned reserved[]={4,5,6,7,8,9,10,11,20,21,26,27,28,29,32,33,34,35,37,38,39,47,48,255,0xffffffff};
    static const unsigned input_only[]={1,2,3,22,23,24,25,30,31,36,40,41,42,43,44,45,46};
    for(unsigned i=0;i<sizeof(reserved)/sizeof(reserved[0]);++i){
        CHECK(!xrp_pin_readable(reserved[i]));CHECK(!xrp_pin_writable(reserved[i]));
    }
    for(unsigned i=0;i<sizeof(input_only)/sizeof(input_only[0]);++i){
        CHECK(xrp_pin_readable(input_only[i]));CHECK(!xrp_pin_writable(input_only[i]));
    }
    CHECK(xrp_pin_writable(0));
    for(unsigned p=12;p<=19;++p){CHECK(xrp_pin_readable(p));CHECK(xrp_pin_writable(p));}
    struct mbnw_flash_store s;struct mbnw_credentials out;
    CHECK(mbnw_flash_store_open(NULL,7)==-EINVAL);
    CHECK(mbnw_flash_store_open(&s,99)==-ENOENT);
    dev.ready=false;CHECK(mbnw_flash_store_open(&s,7)==-ENODEV);dev.ready=true;
    for(size_t block=8;block<=32;block*=2){params.write_block_size=block;CHECK(mbnw_flash_store_open(&s,7)==-ENOTSUP);}
    params.write_block_size=0;CHECK(mbnw_flash_store_open(&s,7)==-ENOTSUP);
    params.write_block_size=1;params.erase_value=0;CHECK(mbnw_flash_store_open(&s,7)==-ENOTSUP);params.erase_value=0xff;
    misaligned=true;CHECK(mbnw_flash_store_open(&s,7)==-EINVAL);misaligned=false;
    page_size=64;CHECK(mbnw_flash_store_open(&s,7)==-EINVAL);page_size=128;
    area.fa_size=255;CHECK(mbnw_flash_store_open(&s,7)==-EINVAL);area.fa_size=256;
    CHECK(erases==0 && writes==0);
    for(size_t block=1;block<=4;block*=2){
        params.write_block_size=block;memset(memory,0xff,sizeof(memory));
        CHECK(mbnw_flash_store_open(&s,7)==0);
        CHECK(s.offsets[0]==0 && s.offsets[1]==128);
        CHECK(mbnw_store_load(&s.io,&out,NULL)==MBNW_EMPTY);
        CHECK(mbnw_store_save(&s.io,(const uint8_t *)"public-fixture-A",16,(const uint8_t *)"test-only-key",13)==0);
        unsigned slot=9;CHECK(mbnw_store_load(&s.io,&out,&slot)==0 && slot==0 && out.generation==1);
        CHECK(mbnw_store_save(&s.io,(const uint8_t *)"public-fixture-B",16,(const uint8_t *)"test-only-key",13)==0);
        CHECK(mbnw_store_load(&s.io,&out,&slot)==0 && slot==1 && out.generation==2);
        unsigned before=erases;CHECK(s.io.erase(s.io.context,2)==-EINVAL);CHECK(erases==before);
        uint8_t b[8]={0};before=writes;
        CHECK(s.io.write(s.io.context,2,0,b,4)==-EINVAL);
        CHECK(s.io.write(s.io.context,0,115,b,4)==-EINVAL);
        CHECK(s.io.read(s.io.context,0,117,b,0)==-EINVAL);
        CHECK(s.io.read(s.io.context,0,115,b,4)==-EINVAL);
        if(block>1)CHECK(s.io.write(s.io.context,0,1,b,4)==-EINVAL);
        CHECK(writes==before);
        mbnw_clear(&out,sizeof(out));
    }
    printf("{\"passed\":true,\"checks\":%u,\"erase_calls\":%u,\"write_calls\":%u}\n",checks,erases,writes);
    return 0;
}
