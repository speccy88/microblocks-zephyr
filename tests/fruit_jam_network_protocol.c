/* SPDX-License-Identifier: MIT */
#include "http_protocol.h"
#include "nina_socket_protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
static unsigned checks;
#define CHECK(x) do{++checks;assert(x);}while(0)
struct stream{const uint8_t *data;size_t size,pos;};
static int byte(void *arg,uint8_t *dst){struct stream *s=arg;if(s->pos==s->size)return -EIO;*dst=s->data[s->pos++];return 0;}
static int bytes(void *arg,uint8_t *dst,size_t n){struct stream *s=arg;if(s->size-s->pos<n)return -EIO;memcpy(dst,s->data+s->pos,n);s->pos+=n;return 0;}
static int parse_http(const char *value,struct fj_http_request *out){char data[2050];size_t n=strlen(value);memcpy(data,value,n+1);return fj_http_parse(data,n,"192.168.1.7",out);}
int main(void)
{
    struct fj_http_request request;
    CHECK(!parse_http("GET / HTTP/1.1\r\nHost: 192.168.1.7\r\n\r\n",&request)&&!request.websocket&&!strcmp(request.path,"/"));
    CHECK(!parse_http("GET /a%20b?version=1 HTTP/1.1\r\nHost: 192.168.1.7:80\r\n\r\n",&request)&&!strcmp(request.path,"/a b"));
    const char *upgrade="GET /ws/vm HTTP/1.1\r\nHost: 192.168.1.7\r\nOrigin: http://192.168.1.7\r\nConnection: keep-alive, Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n";
    CHECK(!parse_http(upgrade,&request)&&request.websocket);
    char accept[29];CHECK(!fj_ws_accept(request.key,accept));CHECK(!strcmp(accept,"s3pPLMBiTxaQ9kYGzzhZRbK+xOo="));
    const char *bad[]={"GET / HTTP/1.1\r\n\r\n","GET / HTTP/1.1\r\nHost: evil.invalid\r\n\r\n","GET / HTTP/1.1\r\nHost: 192.168.1.7\r\nHost: 192.168.1.7\r\n\r\n","GET / HTTP/1.1\r\nHost : 192.168.1.7\r\n\r\n","GET /%00 HTTP/1.1\r\nHost: 192.168.1.7\r\n\r\n","GET /%xz HTTP/1.1\r\nHost: 192.168.1.7\r\n\r\n","POST / HTTP/1.1\r\nHost: 192.168.1.7\r\n\r\n","GET / HTTP/1.1\r\nHost: 192.168.1.7\r\nTransfer-Encoding: chunked\r\n\r\n","GET /ws/vm HTTP/1.1\r\nHost: 192.168.1.7\r\nOrigin: http://evil.invalid\r\n\r\n"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(*bad);++i)CHECK(parse_http(bad[i],&request)<0);
    for(size_t n=0;n<strlen(upgrade);++n){char data[2050];memcpy(data,upgrade,n);data[n]=0;CHECK(fj_http_parse(data,n,"192.168.1.7",&request)<0);}
    CHECK(fj_ws_accept("dGhlIHNhbXBsZSBub25jZR==",accept)<0);
    uint8_t guard[2070];memset(guard,0xa5,sizeof(guard));uint8_t *frame=guard+1;
    CHECK(fj_nina_socket_frame(0x3f,NULL,0,frame,2060)==4&&!memcmp(frame,(uint8_t[]){0xe0,0x3f,0,0xee},4));
    uint8_t socket=3,mode=0,port[]={0,80},yes=1,count[]={0,8};
    struct fj_nina_parameter p[]={{port,2},{&socket,1},{&mode,1}};
    CHECK(fj_nina_socket_frame(0x28,p,3,frame,2060)==12);
    CHECK(!memcmp(frame,(uint8_t[]){0xe0,0x28,3,2,0,80,1,3,1,0,0xee,0},12));
    struct fj_nina_parameter ap[]={{&socket,1},{&yes,1}};
    CHECK(fj_nina_socket_frame(0x2b,ap,2,frame,2060)==8);
    CHECK(!memcmp(frame,(uint8_t[]){0xe0,0x2b,2,1,3,1,1,0xee},8));
    struct fj_nina_parameter rp[]={{&socket,1},{count,2}};
    CHECK(fj_nina_socket_frame(0x45,rp,2,frame,2060)==12);
    CHECK(!memcmp(frame,(uint8_t[]){0xe0,0x45,2,0,1,3,0,2,0,8,0xee,0},12));
    uint8_t payload[2048];for(unsigned i=0;i<sizeof(payload);++i)payload[i]=i;
    struct fj_nina_parameter wp[]={{&socket,1},{payload,sizeof(payload)}};
    CHECK(fj_nina_socket_frame(0x44,wp,2,frame,2060)==2060);
    CHECK(!memcmp(frame,(uint8_t[]){0xe0,0x44,2,0,1,3,8,0},8)&&!memcmp(frame+8,payload,2048)&&frame[2056]==0xee&&guard[0]==0xa5&&guard[2061]==0xa5);
    CHECK(fj_nina_socket_frame(0x44,wp,2,frame,2059)==-ENOSPC);
    wp[1].size=2049;CHECK(fj_nina_socket_frame(0x44,wp,2,frame,2060)<0);
    CHECK(fj_nina_socket_frame(0x50,p,3,frame,2060)==-ENOTSUP);
    const uint8_t reply[]={0xe0,0xc4,1,2,0,8,0xee};uint8_t dst[2048];size_t length;
    for(size_t n=0;n<sizeof(reply);++n){struct stream s={reply,n,0};struct fj_nina_reader io={.byte=byte,.context=&s};CHECK(fj_nina_socket_reply(&io,0x44,dst,sizeof(dst),&length)<0&&length==0);}
    struct stream s={reply,sizeof(reply),0};struct fj_nina_reader io={.byte=byte,.bytes=bytes,.context=&s};
    CHECK(!fj_nina_socket_reply(&io,0x44,dst,2,&length)&&length==2&&dst[0]==0&&dst[1]==8);
    frame[0]=0xe0;frame[1]=0xc5;frame[2]=1;frame[3]=8;frame[4]=0;memcpy(frame+5,payload,2048);frame[2053]=0xee;
    s=(struct stream){frame,2054,0};CHECK(!fj_nina_socket_reply(&io,0x45,dst,2048,&length)&&length==2048&&!memcmp(dst,payload,2048));
    s.pos=0;CHECK(fj_nina_socket_reply(&io,0x45,dst,2047,&length)==-EMSGSIZE&&length==0);
    /* Every TCP split of a maximum-sized masked WebSocket frame. */
    uint8_t ws[2056];ws[0]=0x82;ws[1]=0xfe;ws[2]=8;ws[3]=0;memcpy(ws+4,(uint8_t[]){1,2,3,4},4);
    for(unsigned i=0;i<2048;++i)ws[i+8]=payload[i]^ws[4+i%4];
    uint8_t opcode,*decoded;bool final;size_t decoded_size;
    for(size_t n=0;n<sizeof(ws);++n)CHECK(!fj_ws_decode(ws,n,&opcode,&final,&decoded,&decoded_size));
    CHECK(fj_ws_decode(ws,sizeof(ws),&opcode,&final,&decoded,&decoded_size)==sizeof(ws)&&opcode==2&&final&&decoded_size==2048&&!memcmp(decoded,payload,2048));
    uint8_t ping[]={0x89,0x82,0,0,0,0,'h','i'};
    CHECK(fj_ws_decode(ping,sizeof(ping),&opcode,&final,&decoded,&decoded_size)==8&&opcode==9&&decoded_size==2);
    const uint8_t malformed[][4]={{0x82,0},{0xc2,0x80},{0x81,0x80},{0x09,0x80},{0x89,0xfe,0,126},{0x82,0xff},{0x82,0xfe,0,125},{0x82,0xfe,8,1},{0x88,0x81}};
    for(unsigned i=0;i<sizeof(malformed)/sizeof(*malformed);++i){uint8_t x[4];memcpy(x,malformed[i],4);CHECK(fj_ws_decode(x,4,&opcode,&final,&decoded,&decoded_size)<0);}
    uint8_t header[4];CHECK(fj_ws_header(header,2,2048)==4&&!memcmp(header,(uint8_t[]){0x82,126,8,0},4));
    CHECK(fj_ws_header(header,10,2)==2&&header[0]==0x8a&&header[1]==2);
    printf("{\"result\":\"PASS\",\"checks\":%u,\"scope\":\"Real C HTTP/WebSocket/SPI framing with simulated streams; no hardware\"}\n",checks);
    return 0;
}
