/* SPDX-License-Identifier: MIT */
#include "image_store.h"
#include <stdlib.h>
#include <string.h>
#ifndef IMAGE_ALLOC_EXTERNAL
void *image_alloc(size_t n) { return malloc(n); }
void image_free(void *p) { free(p); }
#endif
typedef struct { image_view view; unsigned generation; } image_slot;
static image_slot slots[IMAGE_SLOTS];
static size_t used;
static int dimensions(unsigned w,unsigned h,unsigned f,size_t *size) {
    if (!w || !h || w>IMAGE_MAX_WIDTH || h>IMAGE_MAX_HEIGHT || f<1 || f>3) return 0;
    *size=(size_t)w*h*f; return 1;
}
const image_view *image_get(int handle) {
    if(handle<=0 || (unsigned)handle>=0x20000000u)return NULL; /* typed audio handles use the upper range */
    unsigned value=(unsigned)handle-1,index=value%IMAGE_SLOTS,generation=value/IMAGE_SLOTS;
    return slots[index].view.pixels && slots[index].generation==generation ? &slots[index].view : NULL;
}
int image_adopt(unsigned w,unsigned h,unsigned f,uint8_t *pixels,size_t size) {
    size_t expected;
    if(!pixels || !dimensions(w,h,f,&expected) || expected!=size || size>IMAGE_BUDGET-used)return 0;
    for(unsigned i=0;i<IMAGE_SLOTS;i++)if(!slots[i].view.pixels && slots[i].generation<0x07ffffffu) {
        slots[i].view=(image_view){w,h,w*f,f,size,pixels};used+=size;
        return (int)(slots[i].generation*IMAGE_SLOTS+i+1);
    }
    return 0;
}
int image_create(unsigned w,unsigned h,unsigned f) {
    size_t size;
    if(!dimensions(w,h,f,&size) || size>IMAGE_BUDGET-used || image_count()==IMAGE_SLOTS)return 0;
    uint8_t *p=image_alloc(size);if(!p)return 0;
    int handle=image_adopt(w,h,f,p,size);if(!handle)image_free(p);return handle;
}
int image_release(int handle) {
    const image_view *v=image_get(handle);if(!v)return 0;
    unsigned i=((unsigned)handle-1)%IMAGE_SLOTS;
    used-=v->bytes;image_free(v->pixels);memset(&slots[i].view,0,sizeof(image_view));slots[i].generation++;
    return 1;
}
void image_release_all(void) {
    for(unsigned i=0;i<IMAGE_SLOTS;i++)if(slots[i].view.pixels)
        image_release((int)(slots[i].generation*IMAGE_SLOTS+i+1));
}
size_t image_bytes_used(void) { return used; }
unsigned image_count(void) { unsigned n=0;for(unsigned i=0;i<IMAGE_SLOTS;i++)n+=slots[i].view.pixels!=NULL;return n; }
static void rgb(const image_view *v,unsigned x,unsigned y,unsigned *r,unsigned *g,unsigned *b) {
    const uint8_t *p=v->pixels+(size_t)y*v->stride+x*v->format;
    if(v->format==IMAGE_GRAY8)*r=*g=*b=p[0];
    else if(v->format==IMAGE_RGB888){*r=p[0];*g=p[1];*b=p[2];}
    else { unsigned n=p[0]|(unsigned)p[1]<<8;*r=((n>>11)&31)*255/31;*g=((n>>5)&63)*255/63;*b=(n&31)*255/31; }
}
int image_resize(int handle,unsigned w,unsigned h,unsigned f) {
    const image_view *src=image_get(handle);if(!src)return 0;
    int out=image_create(w,h,f);if(!out)return 0;
    const image_view *dst=image_get(out);
    for(unsigned y=0;y<h;y++)for(unsigned x=0;x<w;x++) {
        unsigned r,g,b;rgb(src,(uint64_t)x*src->width/w,(uint64_t)y*src->height/h,&r,&g,&b);
        uint8_t *p=dst->pixels+(size_t)y*dst->stride+x*f;
        if(f==IMAGE_GRAY8)p[0]=(77*r+150*g+29*b+128)>>8;
        else if(f==IMAGE_RGB888){p[0]=r;p[1]=g;p[2]=b;}
        else {unsigned n=(r>>3)<<11|(g>>2)<<5|(b>>3);p[0]=n;p[1]=n>>8;}
    }
    return out;
}
int image_grayscale(int handle) {
    const image_view *v=image_get(handle);return v ? image_resize(handle,v->width,v->height,IMAGE_GRAY8):0;
}
int image_read(int handle,size_t offset,uint8_t *dst,size_t count) {
    const image_view *v=image_get(handle);
    if(!v || !dst || offset>v->bytes || count>v->bytes-offset)return 0;
    memcpy(dst,v->pixels+offset,count);return 1;
}
