/* SPDX-FileCopyrightText: Copyright (c) 2019 ladyada for Adafruit Industries
 * SPDX-License-Identifier: MIT
 * Bounded protocol adaptation from the pinned ESP32SPI MIT reference.
 * NINA 3.3.0 CommandHandler.cpp confirms 16-bit socket byte counts and the
 * explicit accept parameter. This code implements framing, not firmware. */
#include "nina_socket_protocol.h"
#include <errno.h>
#include <string.h>

int fj_nina_socket_frame(uint8_t cmd,const struct fj_nina_parameter *p,
                         unsigned n,uint8_t *dst,size_t cap)
{
    bool wide=cmd==0x44||cmd==0x45;
    bool valid=(cmd==0x3f&&n==0)||(cmd==0x28&&n==3)||
      (cmd==0x2b&&(n==1||n==2))||((cmd==0x29||cmd==0x2f||cmd==0x2e||cmd==0x2a)&&n==1)||
      ((cmd==0x44||cmd==0x45)&&n==2);
    if(!valid)return -ENOTSUP;
    if((n&&!p)||!dst)return -EINVAL;
    size_t total=4;
    for(unsigned i=0;i<n;++i){
        if(!p[i].data||!p[i].size||p[i].size>(wide?2048:255))return -EINVAL;
        total+=(wide?2:1)+p[i].size;
    }
    if(cmd==0x28&&(p[0].size!=2||p[1].size!=1||p[2].size!=1||p[2].data[0]!=0))return -EINVAL;
    if(n&&cmd!=0x28&&p[0].size!=1)return -EINVAL;
    if(cmd==0x45&&p[1].size!=2)return -EINVAL;
    if(cmd==0x2b&&n==2&&(p[1].size!=1||p[1].data[0]!=1))return -EINVAL;
    total=(total+3)&~(size_t)3;
    if(total>2060||total>cap)return -ENOSPC;
    memset(dst,0,total);dst[0]=0xe0;dst[1]=cmd;dst[2]=n;
    size_t pos=3;
    for(unsigned i=0;i<n;++i){
        if(wide)dst[pos++]=p[i].size>>8;
        dst[pos++]=p[i].size;memcpy(dst+pos,p[i].data,p[i].size);pos+=p[i].size;
    }
    dst[pos]=0xee;return total;
}
int fj_nina_socket_reply(const struct fj_nina_reader *io,uint8_t cmd,
                         uint8_t *dst,size_t cap,size_t *length)
{
    if(!io||!io->byte||!dst||!length||cap>2048)return -EINVAL;
    *length=0;uint8_t b=0;int err;
    for(unsigned i=0;i<10;++i){
        if((err=io->byte(io->context,&b)))return err;
        if(b==0xef)return -EIO;
        if(b==0xe0)break;
        if(io->retry_pause)io->retry_pause(io->context);
    }
    if(b!=0xe0)return -ETIMEDOUT;
    if((err=io->byte(io->context,&b)))return err;
    if(b!=(cmd|0x80))return -EPROTO;
    if((err=io->byte(io->context,&b)))return err;
    if(b!=1)return -EPROTO;
    if((err=io->byte(io->context,&b)))return err;
    size_t n=b;
    if(cmd==0x45){if((err=io->byte(io->context,&b)))return err;n=(n<<8)|b;}
    if(n>cap)return -EMSGSIZE;
    if(io->bytes){if((err=io->bytes(io->context,dst,n)))return err;}
    else for(size_t i=0;i<n;++i)if((err=io->byte(io->context,dst+i)))return err;
    if((err=io->byte(io->context,&b)))return err;
    if(b!=0xee)return -EPROTO;
    *length=n;return 0;
}
