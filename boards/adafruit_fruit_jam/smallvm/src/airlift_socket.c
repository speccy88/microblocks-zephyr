/* SPDX-License-Identifier: MIT */
#include "airlift_socket.h"
#include "airlift.h"
#include <errno.h>
#include <stdio.h>
static volatile unsigned last_command,last_count,commands;
static volatile int protocol_error;

static int scalar(uint8_t cmd,const struct fj_nina_parameter *p,unsigned n,unsigned bytes)
{
    uint8_t data[2]={0};size_t length=0;
    last_command=cmd;++commands;
    int err=fj_airlift_socket_command(cmd,p,n,data,bytes,&length);
    if(err){protocol_error=err;return err;}
    if(length!=bytes){protocol_error=-EPROTO;return -EPROTO;}
    int value=bytes==1?data[0]:data[0]|((unsigned)data[1]<<8);
    last_count=value;return value;
}
int fj_socket_awake(void)
{
    uint8_t mode=0;const struct fj_nina_parameter p={&mode,1};
    int n=scalar(0x17,&p,1,1);return n==1?0:n<0?n:-EIO;
}
int fj_socket_allocate(void){int n=scalar(0x3f,NULL,0,1);return n==255?-ENFILE:n>=6?-EPROTO:n;}
int fj_socket_listen(uint8_t socket,uint16_t port)
{
    uint8_t service[]={port>>8,port},mode=0;
    const struct fj_nina_parameter p[]={{service,2},{&socket,1},{&mode,1}};
    int n=scalar(0x28,p,3,1);return n==1?0:n<0?n:-EIO;
}
int fj_socket_accept(uint8_t listener)
{
    uint8_t accept=1;const struct fj_nina_parameter p[]={{&listener,1},{&accept,1}};
    int n=scalar(0x2b,p,2,2);return n==255||n==65535?-EAGAIN:n>=6?-EPROTO:n;
}
int fj_socket_available(uint8_t socket){const struct fj_nina_parameter p={&socket,1};return scalar(0x2b,&p,1,2);}
int fj_socket_state(uint8_t socket){const struct fj_nina_parameter p={&socket,1};return scalar(0x2f,&p,1,1);}
int fj_socket_server_state(uint8_t socket){const struct fj_nina_parameter p={&socket,1};return scalar(0x29,&p,1,1);}
int fj_socket_close(uint8_t socket){const struct fj_nina_parameter p={&socket,1};int n=scalar(0x2e,&p,1,1);return n==1?0:n<0?n:-EIO;}
int fj_socket_read(uint8_t socket,uint8_t *dst,size_t size)
{
    if(!size||size>2048)return -EINVAL;
    uint8_t count[]={size,size>>8};const struct fj_nina_parameter p[]={{&socket,1},{count,2}};
    size_t got=0;int err=fj_airlift_socket_command(0x45,p,2,dst,size,&got);
    last_command=0x45;++commands;last_count=got;if(err)protocol_error=err;
    return err?err:(int)got;
}
int fj_socket_status(char *dst,unsigned size)
{
    int n=snprintf(dst,size,"{\"commands\":%u,\"last_command\":%u,\"last_count\":%u,\"protocol_error\":%d}",commands,last_command,last_count,protocol_error);
    return n<0||(unsigned)n>=size?-ENOSPC:0;
}
int fj_socket_write(uint8_t socket,const uint8_t *src,size_t size)
{
    if(!size||size>2048)return -EINVAL;
    const struct fj_nina_parameter p[]={{&socket,1},{src,size}};
    int n=scalar(0x44,p,2,2);return n>(int)size?-EPROTO:n;
}
