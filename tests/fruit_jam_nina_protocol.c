/* SPDX-License-Identifier: MIT */
#include "nina_protocol.h"
#include "wifi_control.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
static unsigned checks;
#define CHECK(expr) do { assert(expr); ++checks; } while (0)
struct stream { const uint8_t *bytes; size_t size, offset; unsigned pauses; };
static int byte(void *context, uint8_t *value)
{
    struct stream *s = context;
    if (s->offset >= s->size) return -EPIPE;
    *value = s->bytes[s->offset++]; return 0;
}
static void pause_retry(void *context) { ++((struct stream *)context)->pauses; }
static int parse(const uint8_t *raw, size_t size, uint8_t *dst, size_t capacity, size_t *length)
{
    struct stream stream = {.bytes = raw, .size = size};
    struct fj_nina_reader io = {.byte = byte, .retry_pause = pause_retry, .context = &stream};
    return fj_nina_read_reply(&io, 0x37, dst, capacity, length);
}
int main(void)
{
    uint8_t frame[8]; memset(frame, 0xa5, sizeof(frame));
    CHECK(fj_nina_query_frame(0x11, frame, sizeof(frame)) == -ENOTSUP);
    CHECK(frame[0] == 0xa5);
    CHECK(fj_nina_query_frame(0x37, frame, sizeof(frame)) == 4);
    CHECK(!memcmp(frame, (uint8_t[]){0xe0,0x37,0,0xee}, 4));
    CHECK(fj_nina_query_frame(0x20, frame, sizeof(frame)) == 4);
    CHECK(!memcmp(frame, (uint8_t[]){0xe0,0x20,0,0xee}, 4));
    CHECK(fj_nina_query_frame(0x22, frame, 7) == -ENOSPC);
    CHECK(fj_nina_query_frame(0x22, frame, sizeof(frame)) == 8);
    CHECK(!memcmp(frame, (uint8_t[]){0xe0,0x22,1,1,0xff,0xee,0,0}, 8));
    const uint8_t reply[] = {0xe0,0xb7,1,2,'A','B',0xee};
    uint8_t guarded[] = {0xa5,0,0,0x5a}; size_t length = 99;
    CHECK(parse(reply, sizeof(reply), guarded+1, 2, &length) == 0);
    CHECK(length == 2 && guarded[1] == 'A' && guarded[2] == 'B');
    CHECK(guarded[0] == 0xa5 && guarded[3] == 0x5a);
    for (size_t cut = 0; cut < sizeof(reply); ++cut) {
        length = 99;
        CHECK(parse(reply, cut, guarded+1, 2, &length) == -EPIPE);
        CHECK(length == 0 && guarded[0] == 0xa5 && guarded[3] == 0x5a);
    }
    guarded[1] = 0x33; guarded[2] = 0x44;
    CHECK(parse(reply, sizeof(reply), guarded+1, 1, &length) == -EMSGSIZE);
    CHECK(length == 0 && guarded[1] == 0x33 && guarded[2] == 0x44);
    uint8_t malformed[sizeof(reply)]; memcpy(malformed, reply, sizeof(reply));
    malformed[1] = 0xb6;
    CHECK(parse(malformed, sizeof(malformed), guarded+1, 2, &length) == -EPROTO);
    malformed[1] = 0xb7; malformed[2] = 2;
    CHECK(parse(malformed, sizeof(malformed), guarded+1, 2, &length) == -EPROTO);
    malformed[2] = 1; malformed[3] = 255;
    CHECK(parse(malformed, sizeof(malformed), guarded+1, 2, &length) == -EMSGSIZE);
    malformed[3] = 2; malformed[6] = 0;
    CHECK(parse(malformed, sizeof(malformed), guarded+1, 2, &length) == -EPROTO);
    CHECK(parse((uint8_t[]){0xef}, 1, guarded+1, 2, &length) == -EIO);
    uint8_t noise[11] = {0}; struct stream stream = {.bytes=noise,.size=sizeof(noise)};
    struct fj_nina_reader io = {.byte=byte,.retry_pause=pause_retry,.context=&stream};
    CHECK(fj_nina_read_reply(&io,0x37,guarded+1,2,&length) == -ETIMEDOUT);
    CHECK(stream.offset == 10 && stream.pauses == 10 && length == 0);
    const uint8_t delayed[] = {0,0xff,0xe0,0xb7,1,2,'A','B',0xee};
    CHECK(parse(delayed,sizeof(delayed),guarded+1,2,&length) == 0 && length == 2);
    /* Fake credentials exercise lengths/guards only; never a real network. */
    uint8_t request[108]={'F','J','N','W',1,2,1,0,0,0,4,8,'T','e','s','t','u','n','i','t','-','k','e','y'};
    struct fj_wifi_request decoded;
    CHECK(fj_wifi_decode(request,24,&decoded)==0 && decoded.operation==2 && decoded.request_id==1);
    CHECK(decoded.ssid_length==4 && decoded.key_length==8);
    for(size_t cut=0;cut<24;++cut) CHECK(fj_wifi_decode(request,cut,&decoded)<0);
    request[4]=2;CHECK(fj_wifi_decode(request,24,&decoded)==-EPROTO);request[4]=1;
    request[5]=99;CHECK(fj_wifi_decode(request,24,&decoded)==-ENOTSUP);request[5]=2;
    request[10]=33;CHECK(fj_wifi_decode(request,24,&decoded)==-EINVAL);request[10]=4;
    request[12]=0;CHECK(fj_wifi_decode(request,24,&decoded)==-EINVAL);request[12]='T';
    request[6]=0;CHECK(fj_wifi_decode(request,24,&decoded)==-EINVAL);request[6]=1;
    uint8_t probe[]={'F','J','N','W',1,1,9,0,0,0};
    CHECK(fj_wifi_decode(probe,sizeof(probe),&decoded)==0);
    CHECK(fj_wifi_decode(probe,sizeof(probe)-1,&decoded)==-EPROTO);
    uint8_t connect[108];memset(connect,0xa5,sizeof(connect));
    CHECK(fj_nina_connect_frame(request+12,4,request+16,8,connect,19)==-ENOSPC);
    CHECK(connect[0]==0xa5);
    CHECK(fj_nina_connect_frame(request+12,4,request+16,8,connect,sizeof(connect))==20);
    CHECK(!memcmp(connect,(uint8_t[]){0xe0,0x11,2,4,'T','e','s','t',8,'u','n','i','t','-','k','e','y',0xee,0,0},20));
    CHECK(connect[20]==0xa5);
    uint8_t sn32[32],kn64[64];memset(sn32,'S',32);memset(kn64,'f',64);
    CHECK(fj_nina_connect_frame(sn32,32,kn64,64,connect,104)==104);
    CHECK(connect[101]==0xee && connect[102]==0 && connect[103]==0 && connect[104]==0xa5);
    kn64[0]='x';CHECK(fj_nina_connect_frame(sn32,32,kn64,64,connect,104)==-EINVAL);
    CHECK(fj_nina_connect_frame(sn32,0,kn64,8,connect,104)==-EINVAL);
    CHECK(fj_nina_query_frame(0x21,frame,sizeof(frame))==8);
    CHECK(fj_nina_query_frame(0x1f,frame,sizeof(frame))==4);
    CHECK(!memcmp(frame,(uint8_t[]){0xe0,0x1f,0,0xee},4));
    CHECK(fj_nina_query_frame(0x21,frame,sizeof(frame))==8);
    CHECK(!memcmp(frame,(uint8_t[]){0xe0,0x21,1,1,0xff,0xee,0,0},8));
    const uint8_t network[]={0xe0,0xa1,3,4,192,168,1,42,4,255,255,255,0,4,192,168,1,1,0xee};
    uint8_t network_guard[14]={0xa5},*destinations[]={network_guard+1,network_guard+5,network_guard+9};
    network_guard[13]=0x5a;size_t caps[]={4,4,4},lengths[]={99,99,99};
    struct stream netstream={.bytes=network,.size=sizeof(network)};
    struct fj_nina_reader netio={.byte=byte,.retry_pause=pause_retry,.context=&netstream};
    CHECK(fj_nina_read_reply_params(&netio,0x21,destinations,caps,lengths,3)==0);
    CHECK(lengths[0]==4 && lengths[1]==4 && lengths[2]==4 && network_guard[0]==0xa5 && network_guard[13]==0x5a);
    CHECK(destinations[0][0]==192 && destinations[0][3]==42 && destinations[2][3]==1);
    netstream.offset=0;caps[1]=3;
    CHECK(fj_nina_read_reply_params(&netio,0x21,destinations,caps,lengths,3)==-EMSGSIZE);
    CHECK(lengths[0]==0 && lengths[1]==0 && lengths[2]==0);
    fj_secure_clear(connect,sizeof(connect));
    for(size_t i=0;i<sizeof(connect);++i) CHECK(connect[i]==0);
    printf("{\"result\":\"PASS\",\"checks\":%u,\"scope\":\"Real framing C with simulated SPI bytes; no physical hardware\"}\n",checks);
    return 0;
}
