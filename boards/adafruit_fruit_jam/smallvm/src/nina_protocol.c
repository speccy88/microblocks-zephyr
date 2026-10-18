/* SPDX-FileCopyrightText: Copyright (c) 2019 ladyada for Adafruit Industries
 * SPDX-License-Identifier: MIT
 * Bounded C adaptation of Adafruit ESP32SPI command/reply framing, revision
 * 64f4695cc4457df0718e1a6460082381359c3562. See dependencies and licenses. */
#include "nina_protocol.h"
#include "wifi_control.h"
#include <errno.h>
#include <string.h>

int fj_nina_query_frame(uint8_t command, uint8_t *dst, size_t size)
{
    if (command != 0x37 && command != 0x20 && command != 0x22 && command != 0x21 && command != 0x1f) return -ENOTSUP;
    unsigned count = (command == 0x22 || command == 0x21) ? 8 : 4;
    if (!dst || size < count) return -ENOSPC;
    memset(dst, 0, count);
    dst[0] = 0xe0; dst[1] = command;
    if (command == 0x22 || command == 0x21) {
        dst[2] = 1; dst[3] = 1; dst[4] = 0xff; dst[5] = 0xee;
    } else dst[3] = 0xee;
    return count;
}

int fj_nina_connect_frame(const uint8_t *ssid, size_t sn, const uint8_t *key,
                          size_t kn, uint8_t *dst, size_t size)
{
    int err=fj_wifi_credentials_valid(ssid,sn,key,kn);
    if (err) return err;
    size_t count=(6+sn+kn+3)&~(size_t)3;
    if (!dst || size<count) return -ENOSPC;
    memset(dst,0,count);
    dst[0]=0xe0;dst[1]=0x11;dst[2]=2;dst[3]=sn;
    memcpy(dst+4,ssid,sn);dst[4+sn]=kn;memcpy(dst+5+sn,key,kn);dst[5+sn+kn]=0xee;
    return count;
}

int fj_nina_read_reply(const struct fj_nina_reader *io, uint8_t command,
                      uint8_t *dst, size_t capacity, size_t *length)
{
    uint8_t *destinations[]={dst};
    return fj_nina_read_reply_params(io,command,destinations,&capacity,length,1);
}
int fj_nina_read_reply_params(const struct fj_nina_reader *io, uint8_t command,
                             uint8_t **dst, const size_t *capacity,
                             size_t *length, unsigned parameters)
{
    if (!io || !io->byte || !dst || !capacity || !length || parameters<1 || parameters>3) return -EINVAL;
    for (unsigned i=0;i<parameters;++i) { if (!dst[i]) return -EINVAL; length[i]=0; }
    uint8_t value = 0;
    int err;
    for (unsigned attempt = 0; attempt < 10; ++attempt) {
        if ((err = io->byte(io->context, &value))) return err;
        if (value == 0xef) return -EIO;
        if (value == 0xe0) break;
        if (io->retry_pause) io->retry_pause(io->context);
    }
    if (value != 0xe0) return -ETIMEDOUT;
    if ((err = io->byte(io->context, &value))) return err;
    if (value != (command | 0x80)) return -EPROTO;
    if ((err = io->byte(io->context, &value))) return err;
    if (value != parameters) return -EPROTO;
    size_t counts[3]={0};
    for (unsigned param=0;param<parameters;++param) {
        if ((err=io->byte(io->context,&value))) return err;
        counts[param]=value;
        if (counts[param]>capacity[param]) return -EMSGSIZE;
        for (size_t i=0;i<counts[param];++i)
            if ((err=io->byte(io->context,&dst[param][i]))) return err;
    }
    if ((err = io->byte(io->context, &value))) return err;
    if (value != 0xee) return -EPROTO;
    for (unsigned i=0;i<parameters;++i) length[i]=counts[i];
    return 0;
}
