/* SPDX-License-Identifier: MIT */
#include "http_protocol.h"
#include <errno.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>

static int copy_value(char *dst,size_t cap,char *src)
{
    while(*src==' '||*src=='\t')++src;
    size_t n=strlen(src);while(n&&(src[n-1]==' '||src[n-1]=='\t'))--n;
    if(!n||n>=cap||*dst)return -EPROTO;
    memcpy(dst,src,n);dst[n]=0;return 0;
}
static bool token(const char *value,const char *wanted)
{
    size_t n=strlen(wanted);
    while(*value){
        while(*value==' '||*value=='\t'||*value==',')++value;
        const char *end=strchr(value,',');if(!end)end=value+strlen(value);
        const char *trim=end;while(trim>value&&(trim[-1]==' '||trim[-1]=='\t'))--trim;
        if((size_t)(trim-value)==n&&!strncasecmp(value,wanted,n))return true;
        value=end;if(*value)++value;
    }
    return false;
}
static int base64_value(char c)
{
    const char *alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    const char *found=strchr(alphabet,c);return c&&found?(int)(found-alphabet):-1;
}
static bool valid_key(const char *key)
{
    if(strlen(key)!=24||key[22]!='='||key[23]!='=')return false;
    for(unsigned i=0;i<22;++i)if(base64_value(key[i])<0)return false;
    return !(base64_value(key[21])&15);
}
int fj_http_parse(char *data,size_t size,const char *ip,struct fj_http_request *out)
{
    if(!data||!out||!ip||size<4||size>2048||memcmp(data+size-4,"\r\n\r\n",4)||memchr(data,0,size))return -EPROTO;
    memset(out,0,sizeof(*out));data[size]=0;
    char *line=strstr(data,"\r\n");if(!line)return -EPROTO;*line=0;
    if(strncmp(data,"GET ",4))return -ENOTSUP;
    char *path=data+4,*space=strchr(path,' ');
    if(!space||strcmp(space," HTTP/1.1")||*path!='/')return -EPROTO;
    *space=0;char *query=strchr(path,'?');if(query)*query=0;
    if(!*path||strlen(path)>=sizeof(out->path))return -ENAMETOOLONG;
    /* Decode literal URL paths for flash-table lookup; never interpret a path
     * as a filesystem path. Reject encoded control characters. */
    size_t pos=0;
    for(size_t i=0;path[i];++i){
        unsigned c=(unsigned char)path[i];
        if(c=='%'){
            unsigned a,b;
            if(!path[i+1]||!path[i+2])return -EPROTO;
            char hex[3]={path[i+1],path[i+2],0};
            for(unsigned j=0;j<2;++j)if(!((hex[j]>='0'&&hex[j]<='9')||(hex[j]>='a'&&hex[j]<='f')||(hex[j]>='A'&&hex[j]<='F')))return -EPROTO;
            if(sscanf(hex,"%1x%1x",&a,&b)!=2)return -EPROTO;c=(a<<4)|b;i+=2;
        }
        if(c<32||c==127||c=='\\')return -EPROTO;
        out->path[pos++]=c;
    }
    out->path[pos]=0;
    char connection[128]={0},upgrade[32]={0},version[8]={0};
    for(char *p=line+2;*p;){
        char *end=strstr(p,"\r\n");if(!end)return -EPROTO;if(end==p)break;*end=0;
        char *colon=strchr(p,':');if(!colon||colon==p)return -EPROTO;*colon++=0;
        for(char *q=p;*q;++q)if(!((*q>='A'&&*q<='Z')||(*q>='a'&&*q<='z')||(*q>='0'&&*q<='9')||*q=='-'))return -EPROTO;
        for(char *q=colon;*q;++q)if(((unsigned char)*q<32&&*q!='\t')||(unsigned char)*q==127)return -EPROTO;
        int err=0;
        if(!strcasecmp(p,"Host"))err=copy_value(out->host,sizeof(out->host),colon);
        else if(!strcasecmp(p,"Origin"))err=copy_value(out->origin,sizeof(out->origin),colon);
        else if(!strcasecmp(p,"Connection"))err=copy_value(connection,sizeof(connection),colon);
        else if(!strcasecmp(p,"Upgrade"))err=copy_value(upgrade,sizeof(upgrade),colon);
        else if(!strcasecmp(p,"Sec-WebSocket-Key"))err=copy_value(out->key,sizeof(out->key),colon);
        else if(!strcasecmp(p,"Sec-WebSocket-Version"))err=copy_value(version,sizeof(version),colon);
        else if(!strcasecmp(p,"Transfer-Encoding")||!strcasecmp(p,"Content-Length"))return -EPROTO;
        if(err)return err;p=end+2;
    }
    char port_host[64];snprintf(port_host,sizeof(port_host),"%s:80",ip);
    if(strcmp(out->host,ip)&&strcmp(out->host,port_host))return -EACCES;
    out->websocket=!strcmp(out->path,"/ws/vm");
    if(out->websocket){
        char origin[96];snprintf(origin,sizeof(origin),"http://%s",out->host);
        if(strcmp(out->origin,origin)||strcasecmp(upgrade,"websocket")||!token(connection,"upgrade")||strcmp(version,"13")||!valid_key(out->key))return -EACCES;
    }else if(*upgrade||*out->key)return -EPROTO;
    return 0;
}
static uint32_t rol(uint32_t v,unsigned n){return (v<<n)|(v>>(32-n));}
int fj_ws_accept(const char key[25],char out[29])
{
    if(!valid_key(key))return -EINVAL;
    /* SHA-1 of the fixed 60-byte RFC6455 key+GUID. Two blocks, no heap. */
    uint8_t blocks[128]={0};memcpy(blocks,key,24);
    memcpy(blocks+24,"258EAFA5-E914-47DA-95CA-C5AB0DC85B11",36);blocks[60]=0x80;
    blocks[126]=1;blocks[127]=0xe0; /* 60 * 8 = 480 bits, big endian */
    uint32_t h[]={0x67452301,0xefcdab89,0x98badcfe,0x10325476,0xc3d2e1f0};
    for(unsigned block=0;block<2;++block){
        uint32_t w[80];
        for(unsigned i=0;i<16;++i){unsigned j=block*64+i*4;w[i]=((uint32_t)blocks[j]<<24)|((uint32_t)blocks[j+1]<<16)|((uint32_t)blocks[j+2]<<8)|blocks[j+3];}
        for(unsigned i=16;i<80;++i)w[i]=rol(w[i-3]^w[i-8]^w[i-14]^w[i-16],1);
        uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4];
        for(unsigned i=0;i<80;++i){
            uint32_t f,k;
            if(i<20){f=(b&c)|(~b&d);k=0x5a827999;}
            else if(i<40){f=b^c^d;k=0x6ed9eba1;}
            else if(i<60){f=(b&c)|(b&d)|(c&d);k=0x8f1bbcdc;}
            else{f=b^c^d;k=0xca62c1d6;}
            uint32_t t=rol(a,5)+f+e+k+w[i];e=d;d=c;c=rol(b,30);b=a;a=t;
        }
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;
    }
    uint8_t digest[20];for(unsigned i=0;i<20;++i)digest[i]=h[i/4]>>(24-8*(i%4));
    const char *alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";unsigned pos=0;
    for(unsigned i=0;i<20;i+=3){unsigned remain=20-i;uint32_t v=(uint32_t)digest[i]<<16;if(remain>1)v|=(uint32_t)digest[i+1]<<8;if(remain>2)v|=digest[i+2];
        out[pos++]=alphabet[(v>>18)&63];out[pos++]=alphabet[(v>>12)&63];out[pos++]=remain>1?alphabet[(v>>6)&63]:'=';out[pos++]=remain>2?alphabet[v&63]:'=';}
    out[pos]=0;return 0;
}
int fj_ws_decode(uint8_t *data,size_t size,uint8_t *opcode,bool *final,uint8_t **payload,size_t *length)
{
    if(size<2)return 0;
    unsigned op=data[0]&15;bool fin=data[0]&128;
    if((data[0]&112)||!(data[1]&128)||(op!=0&&op!=2&&op!=8&&op!=9&&op!=10))return -EPROTO;
    size_t n=data[1]&127,head=2;
    if(n==127)return -EMSGSIZE;
    if(n==126){if(size<4)return 0;n=((size_t)data[2]<<8)|data[3];head=4;if(n<126)return -EPROTO;}
    if(n>2048||(op>=8&&(!fin||n>125))||(op==8&&n==1))return -EMSGSIZE;
    if(size<head+4+n)return 0;
    for(size_t i=0;i<n;++i)data[head+4+i]^=data[head+i%4];
    *opcode=op;*final=fin;*payload=data+head+4;*length=n;return head+4+n;
}
size_t fj_ws_header(uint8_t *dst,unsigned opcode,size_t size)
{
    dst[0]=0x80|opcode;
    if(size<126){dst[1]=size;return 2;}
    dst[1]=126;dst[2]=size>>8;dst[3]=size;return 4;
}
