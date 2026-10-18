/* SPDX-FileCopyrightText: Copyright (c) 2019 ladyada for Adafruit Industries
 * SPDX-License-Identifier: MIT
 * Bounded C adaptation of Adafruit ESP32SPI command/reply framing, revision
 * 64f4695cc4457df0718e1a6460082381359c3562. See dependencies and licenses. */
#include "nina_protocol.h"
#include <errno.h>
#include <string.h>

int fj_nina_query_frame(uint8_t command, uint8_t *dst, size_t size)
{
    if (command != 0x37 && command != 0x20 && command != 0x22) return -ENOTSUP;
    unsigned count = command == 0x22 ? 8 : 4;
    if (!dst || size < count) return -ENOSPC;
    memset(dst, 0, count);
    dst[0] = 0xe0; dst[1] = command;
    if (command == 0x22) {
        dst[2] = 1; dst[3] = 1; dst[4] = 0xff; dst[5] = 0xee;
    } else dst[3] = 0xee;
    return count;
}

int fj_nina_read_reply(const struct fj_nina_reader *io, uint8_t command,
                      uint8_t *dst, size_t capacity, size_t *length)
{
    if (!io || !io->byte || !dst || !length) return -EINVAL;
    *length = 0;
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
    if (value != 1) return -EPROTO;
    if ((err = io->byte(io->context, &value))) return err;
    size_t count = value;
    if (count > capacity) return -EMSGSIZE;
    for (size_t i = 0; i < count; ++i)
        if ((err = io->byte(io->context, &dst[i]))) return err;
    if ((err = io->byte(io->context, &value))) return err;
    if (value != 0xee) return -EPROTO;
    *length = count;
    return 0;
}
