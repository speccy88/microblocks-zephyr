/* SPDX-License-Identifier: MIT */
#include "wire.h"
#include <string.h>
_Static_assert(MB_FILES_RESPONSE_MAX >= 22+MB_FILE_COUNT*(7+MB_FILE_PATH-1),
    "Response must fit all bounded file metadata");
_Static_assert(MB_FILES_RESPONSE_MAX >= 22+MB_FILES_CHUNK,
    "Response must fit a read chunk");
static uint16_t u16(const uint8_t *p) { return p[0]|((uint16_t)p[1]<<8); }
static uint32_t u32(const uint8_t *p) { return u16(p)|((uint32_t)u16(p+2)<<16); }
static void p16(uint8_t *p,uint16_t v) { p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8); }
static void p32(uint8_t *p,uint32_t v) { p16(p,(uint16_t)v);p16(p+2,(uint16_t)(v>>16)); }
static size_t put_meta(uint8_t *p,const mb_files_meta *m) {
    size_t n=strlen(m->path);p32(p,m->revision);p16(p+4,m->bytes);p[6]=(uint8_t)n;
    memcpy(p+7,m->path,n);return n+7;
}
bool mb_files_wire(mb_files_dispatcher *d,uint32_t owner,uint64_t now,
    const uint8_t *in,size_t n,uint8_t *out,size_t capacity,size_t *length,mb_files_wire_workspace *w) {
    if (length) *length=0;
    /* Reserve the entire bounded response before a mutation can happen. */
    if (!in||!out||!length||!w||capacity<MB_FILES_RESPONSE_MAX || n<MB_FILES_REQUEST_HEADER ||
        n>MB_FILES_REQUEST_MAX || memcmp(in,"MBFS",4) || in[4]!=1 || in[25]) return false;
    mb_files_request *r=&w->request;mb_files_reply *reply=&w->reply;
    memset(w,0,sizeof(*w));r->op=in[5];r->id=u32(in+6);r->session=u32(in+10);
    r->token=u32(in+14);r->arg=u32(in+18);r->count=u16(in+22);r->path_length=in[24];
    size_t data_length=r->op==MB_FILES_APPEND?r->count:0;
    if (r->path_length>=MB_FILE_PATH || data_length>MB_FILES_CHUNK ||
        n!=MB_FILES_REQUEST_HEADER+r->path_length+data_length) return false;
    memcpy(r->path,in+MB_FILES_REQUEST_HEADER,r->path_length);
    if (data_length) memcpy(r->data,in+MB_FILES_REQUEST_HEADER+r->path_length,data_length);
    mb_files_dispatch(d,owner,now,r,reply);
    memcpy(out,"MBFR",4);out[4]=1;out[5]=reply->op;p32(out+6,reply->id);
    p32(out+10,reply->session);out[14]=(uint8_t)reply->status;out[15]=0;size_t pos=16;
    if (!reply->status) switch(reply->op) {
    case MB_FILES_CAPS:
        out[pos++]=MB_FILE_COUNT;p16(out+pos,MB_FILE_BYTES);pos+=2;
        p16(out+pos,MB_FILES_CHUNK);pos+=2;out[pos++]=3;out[pos++]=1;break;
    case MB_FILES_LIST:
        out[pos++]=reply->file_count;out[pos++]=reply->free_slots;p32(out+pos,reply->used);pos+=4;
        for(unsigned i=0;i<reply->file_count;i++) {
            pos+=put_meta(out+pos,&reply->files[i]);
        }
        break;
    case MB_FILES_STAT: case MB_FILES_FINISH: pos+=put_meta(out+pos,&reply->files[0]);break;
    case MB_FILES_READ:
        p32(out+pos,reply->token);pos+=4;p16(out+pos,reply->count);pos+=2;
        memcpy(out+pos,reply->data,reply->count);pos+=reply->count;break;
    case MB_FILES_BEGIN:p32(out+pos,reply->token);pos+=4;break;
    case MB_FILES_APPEND:p16(out+pos,reply->count);pos+=2;break;
    case MB_FILES_CANCEL:out[pos++]=1;break;
    default:return false;
    }
    *length=pos;return true;
}
