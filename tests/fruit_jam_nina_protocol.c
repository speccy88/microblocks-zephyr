/* SPDX-License-Identifier: MIT */
#include "nina_protocol.h"
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
    printf("{\"result\":\"PASS\",\"checks\":%u,\"scope\":\"Real framing C with simulated SPI bytes; no physical hardware\"}\n",checks);
    return 0;
}
