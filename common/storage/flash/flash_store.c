/* SPDX-License-Identifier: MIT */
#include "flash_store.h"
#include <errno.h>
#include <string.h>

static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void put32(uint8_t *p, uint32_t n) {
    for (unsigned i=0;i<4;i++) p[i]=(uint8_t)(n>>(8*i));
}
static uint32_t crc(const uint8_t *p, size_t n) {
    uint32_t c=UINT32_MAX;
    for (size_t i=0;i<n;i++) {
        c^=p[i];
        for (unsigned bit=0;bit<8;bit++) c=(c>>1)^(UINT32_C(0xedb88320)&(0-(c&1)));
    }
    return ~c;
}
static bool first(unsigned char c) {
    return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_';
}
bool mb_flash_path(const char *p, size_t n) {
    if (!p || n<8 || n>=MB_FLASH_PATH || memcmp(p,"/Flash/",7)) return false;
    unsigned components=1; bool start=true;
    for(size_t i=7;i<n;i++) {
        unsigned char c=(unsigned char)p[i];
        if(c=='/') { if(start || ++components>4)return false; start=true; }
        else { if(!first(c)&&(start||(c!='-'&&c!='.')))return false; start=false; }
    }
    return !start;
}
static int enter(mb_flash *s) {
    if(s->busy)return -EBUSY;
    if(!s->ready)return -ENODEV;
    s->busy=true;return 0;
}
static int leave(mb_flash *s,int e) { s->busy=false; return e; }
static int failed(mb_flash *s,int e) { s->ready=false;return leave(s,e); }
static int find(mb_flash *s,const char *p,size_t n) {
    for(unsigned i=0;i<MB_FLASH_FILES;i++)
        if(s->files[i].revision&&strlen(s->files[i].path)==n&&!memcmp(s->files[i].path,p,n))return (int)i;
    return -1;
}
static int decode(mb_flash *s,size_t n,mb_flash_file *f) {
    const uint8_t *b=s->scratch;
    if(n<84||memcmp(b,"MBFILE01",8))return -EILSEQ;
    uint32_t rev=get32(b+8),length=get32(b+12);
    if(!rev||rev>MB_FLASH_REV_MAX||length>MB_FLASH_BYTES||n!=84+length||crc(b,n-4)!=get32(b+n-4))return -EILSEQ;
    size_t len=0;while(len<MB_FLASH_PATH&&b[16+len])len++;
    if(!mb_flash_path((const char *)b+16,len))return -EILSEQ;
    for(size_t i=len;i<MB_FLASH_PATH;i++)if(b[16+i])return -EILSEQ;
    memset(f,0,sizeof(*f));memcpy(f->path,b+16,len);f->revision=rev;f->bytes=length;
    return 0;
}
void mb_flash_init(mb_flash *s,const mb_flash_port *port,void *context) {
    memset(s,0,sizeof(*s));s->port=port;s->context=context;
}
int mb_flash_mount(mb_flash *s) {
    if(s->busy||s->mounted)return -EBUSY;
    if(!s->port||!s->port->mount||!s->port->unmount||!s->port->read||
       !s->port->replace||!s->port->remove||!s->port->space)return -EINVAL;
    s->busy=true;s->ready=false;s->sequence=0;memset(s->files,0,sizeof(s->files));
    int e=s->port->mount(s->context);if(e)return leave(s,e);
    s->mounted=true;size_t n=0;
    e=s->port->read(s->context,0,s->scratch,sizeof(s->scratch),&n);
    if(e==-ENOENT)e=0;
    else if(!e) {
        if(n!=16||memcmp(s->scratch,"MBSEQ001",8)||crc(s->scratch,12)!=get32(s->scratch+12))e=-EILSEQ;
        else { s->sequence=get32(s->scratch+8);if(!s->sequence||s->sequence>MB_FLASH_REV_MAX)e=-EILSEQ; }
    }
    for(unsigned i=0;!e&&i<MB_FLASH_FILES;i++) {
        e=s->port->read(s->context,i+1,s->scratch,sizeof(s->scratch),&n);
        if(e==-ENOENT) {e=0;continue;}
        if(e)break;
        e=decode(s,n,&s->files[i]);if(e)break;
        if(s->files[i].revision>s->sequence){e=-EILSEQ;break;}
        for(unsigned j=0;j<i;j++)
            if(s->files[j].revision&&(s->files[j].revision==s->files[i].revision||
               !strcmp(s->files[j].path,s->files[i].path))){e=-EILSEQ;break;}
    }
    memset(s->scratch,0,sizeof(s->scratch));
    if(e) {
        int u=s->port->unmount(s->context);if(!u)s->mounted=false;
        return failed(s,e);
    }
    s->ready=true;return leave(s,0);
}
int mb_flash_unmount(mb_flash *s) {
    if(s->busy)return -EBUSY;
    s->ready=false;
    if(!s->mounted)return 0;
    s->busy=true;int e=s->port->unmount(s->context);
    if(!e){s->mounted=false;memset(s->files,0,sizeof(s->files));memset(s->scratch,0,sizeof(s->scratch));}
    return leave(s,e);
}
int mb_flash_stat(mb_flash *s,const char *p,size_t n,mb_flash_file *out) {
    if(!out||!mb_flash_path(p,n))return -EINVAL;
    int e=enter(s);if(e)return e;int i=find(s,p,n);
    if(i<0)return leave(s,-ENOENT);
    *out=s->files[i];return leave(s,0);
}
int mb_flash_list(mb_flash *s,mb_flash_file *out,size_t capacity,size_t *count) {
    if(!count||(!out&&capacity)||capacity>MB_FLASH_FILES)return -EINVAL;
    int e=enter(s);if(e)return e;size_t n=0;
    for(unsigned i=0;i<MB_FLASH_FILES;i++)if(s->files[i].revision)n++;
    if(capacity<n)return leave(s,-ENOBUFS);
    *count=0;
    for(unsigned i=0;i<MB_FLASH_FILES;i++)if(s->files[i].revision)out[(*count)++]=s->files[i];
    return leave(s,0);
}
int mb_flash_read(mb_flash *s,const char *p,size_t n,uint32_t rev,size_t off,uint8_t *out,size_t count) {
    if(!mb_flash_path(p,n)||(!out&&count)||count>1024)return -EINVAL;
    int e=enter(s);if(e)return e;int i=find(s,p,n);
    if(i<0)return leave(s,-ENOENT);
    if(!rev||s->files[i].revision!=rev)return leave(s,-ESTALE);
    if(off>s->files[i].bytes||count>s->files[i].bytes-off)return leave(s,-EINVAL);
    size_t length;mb_flash_file f;
    e=s->port->read(s->context,(unsigned)i+1,s->scratch,sizeof(s->scratch),&length);
    if(!e)e=decode(s,length,&f);
    if(!e&&memcmp(&f,&s->files[i],sizeof(f)))e=-ESTALE;
    if(e){memset(s->scratch,0,sizeof(s->scratch));return failed(s,e);}
    if(count)memcpy(out,s->scratch+80+off,count);
    memset(s->scratch,0,sizeof(s->scratch));return leave(s,0);
}
int mb_flash_put(mb_flash *s,const char *p,size_t n,uint32_t expected,const uint8_t *data,size_t count,uint32_t *revision) {
    if(!revision||!mb_flash_path(p,n)||(!data&&count))return -EINVAL;
    if(count>MB_FLASH_BYTES)return -EFBIG;
    int e=enter(s);if(e)return e;int slot=find(s,p,n);
    if(expected&&(slot<0||s->files[slot].revision!=expected))return leave(s,-ESTALE);
    if(!expected&&slot>=0)return leave(s,-EEXIST);
    if(slot<0)for(unsigned i=0;i<MB_FLASH_FILES;i++)if(!s->files[i].revision){slot=(int)i;break;}
    if(slot<0)return leave(s,-ENOSPC);
    if(s->sequence==MB_FLASH_REV_MAX)return leave(s,-EOVERFLOW);
    uint32_t next=s->sequence+1;
    uint8_t seq[16];memcpy(seq,"MBSEQ001",8);put32(seq+8,next);put32(seq+12,crc(seq,12));
    e=s->port->replace(s->context,0,seq,sizeof(seq));if(e)return failed(s,e);
    s->sequence=next;
    uint8_t *b=s->scratch;memset(b,0,80);memcpy(b,"MBFILE01",8);
    put32(b+8,next);put32(b+12,(uint32_t)count);memcpy(b+16,p,n);
    if(count)memcpy(b+80,data,count);
    put32(b+80+count,crc(b,80+count));
    e=s->port->replace(s->context,(unsigned)slot+1,b,84+count);
    memset(b,0,sizeof(s->scratch));if(e)return failed(s,e);
    mb_flash_file *f=&s->files[slot];memset(f,0,sizeof(*f));
    memcpy(f->path,p,n);f->revision=next;f->bytes=(uint32_t)count;*revision=next;
    return leave(s,0);
}
int mb_flash_delete(mb_flash *s,const char *p,size_t n,uint32_t expected) {
    if(!mb_flash_path(p,n))return -EINVAL;
    int e=enter(s);if(e)return e;int i=find(s,p,n);
    if(i<0)return leave(s,-ENOENT);
    if(!expected||s->files[i].revision!=expected)return leave(s,-ESTALE);
    e=s->port->remove(s->context,(unsigned)i+1);if(e)return failed(s,e);
    memset(&s->files[i],0,sizeof(s->files[i]));return leave(s,0);
}
int mb_flash_capacity(mb_flash *s,uint32_t *used,unsigned *slots,uint64_t *total,uint64_t *free) {
    if(!used||!slots||!total||!free)return -EINVAL;
    int e=enter(s);if(e)return e;*used=0;*slots=MB_FLASH_FILES;
    for(unsigned i=0;i<MB_FLASH_FILES;i++)if(s->files[i].revision){*used+=s->files[i].bytes;(*slots)--;}
    e=s->port->space(s->context,total,free);return leave(s,e);
}
