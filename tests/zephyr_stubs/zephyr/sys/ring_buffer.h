/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <string.h>
struct ring_buf { uint8_t *data;unsigned capacity,head,used; };
#define RING_BUF_DECLARE(name,size) static uint8_t name##_storage[size]; struct ring_buf name={name##_storage,size,0,0}
static inline unsigned ring_buf_space_get(struct ring_buf *r) { return r->capacity-r->used; }
static inline bool ring_buf_is_empty(struct ring_buf *r) { return !r->used; }
static inline void ring_buf_reset(struct ring_buf *r) { r->head=r->used=0; }
static inline unsigned ring_buf_put(struct ring_buf *r,const uint8_t *p,unsigned n)
{ if(n>r->capacity-r->used)n=r->capacity-r->used;for(unsigned i=0;i<n;++i)r->data[(r->head+r->used+i)%r->capacity]=p[i];r->used+=n;return n; }
static inline unsigned ring_buf_peek(struct ring_buf *r,uint8_t *p,unsigned n)
{ if(n>r->used)n=r->used;for(unsigned i=0;i<n;++i)p[i]=r->data[(r->head+i)%r->capacity];return n; }
static inline unsigned ring_buf_get(struct ring_buf *r,uint8_t *p,unsigned n)
{ n=ring_buf_peek(r,p,n);r->head=(r->head+n)%r->capacity;r->used-=n;return n; }
static inline unsigned ring_buf_get_claim(struct ring_buf *r,uint8_t **p,unsigned n)
{ if(n>r->used)n=r->used;if(n>r->capacity-r->head)n=r->capacity-r->head;*p=r->data+r->head;return n; }
static inline int ring_buf_get_finish(struct ring_buf *r,unsigned n)
{ if(n>r->used)return -1;r->head=(r->head+n)%r->capacity;r->used-=n;return 0; }
