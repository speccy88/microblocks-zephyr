/* SPDX-License-Identifier: MIT */
#include "image_store.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail_alloc;
void *__real_malloc(size_t);
void *__wrap_malloc(size_t n){return fail_alloc?NULL:__real_malloc(n);}
int main(void){
 assert(!image_create(0,1,2));assert(!image_create(1281,1,2));assert(!image_create(1,721,2));assert(!image_create(1,1,4));
 assert(!image_get(-1));assert(!image_get(0));assert(!image_get(2147483647));
 int h=image_create(2,2,IMAGE_RGB565);assert(h);
 const uint8_t pixels[]={0,248,224,7,31,0,255,255};memcpy(image_get(h)->pixels,pixels,8);
 int gray=image_grayscale(h);assert(gray);
 const uint8_t expected[]={77,149,29,255};assert(!memcmp(image_get(gray)->pixels,expected,4));
 int rgb=image_resize(h,1,1,IMAGE_RGB888);assert(rgb);assert(!memcmp(image_get(rgb)->pixels,"\xff\x00\x00",3));
 int small=image_resize(gray,1,1,IMAGE_GRAY8);assert(small && image_get(small)->pixels[0]==77);
 assert(!image_create(1,1,1));assert(image_count()==4);
 uint8_t out[8];assert(image_read(h,0,out,8)&&!memcmp(out,pixels,8));
 assert(!image_read(h,9,out,1));assert(!image_read(h,0,out,9));assert(!image_read(h,(size_t)-1,out,1));
 assert(image_read(h,8,out,0));assert(!image_read(h,0,NULL,1));
 assert(image_release(h));assert(!image_release(h));assert(!image_get(h));
 int replacement=image_create(2,2,2);assert(replacement && replacement!=h);assert(!image_get(h));
 image_release_all();assert(!image_count()&&!image_bytes_used());
 fail_alloc=1;assert(!image_create(2,2,2));fail_alloc=0;assert(!image_count());
 for(unsigned i=0;i<10000;i++){int next=image_create(1,1,1);assert(next);assert(!image_get(replacement));assert(image_release(next));assert(!image_get(next));}
 int large[4];for(unsigned i=0;i<3;i++){large[i]=image_create(1280,720,3);assert(large[i]);}
 assert(!image_create(1280,720,3));assert(image_bytes_used()==8294400);image_release_all();
 uint8_t *native=image_alloc(6);assert(!image_adopt(2,2,2,native,6));image_free(native);
 assert(!image_count()&&!image_bytes_used());
 puts("{\"result\":\"PASS\",\"reuse_cycles\":10000,\"pixel_formats\":3,\"bounds_capacity_allocation_failure\":true}");
 return 0;
}
