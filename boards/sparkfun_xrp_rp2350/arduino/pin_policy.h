/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
/* Production XRP raw GPIO. Radio/I2C/PSRAM/RGB and all actuators are absent.
 * Encoder, USER and ADC pins may be read but never driven by user code. */
static inline bool xrp_pin_readable(unsigned p)
{
    return p<=3 || (p>=12 && p<=19) || (p>=22 && p<=25) ||
        p==30 || p==31 || p==36 || (p>=40 && p<=46);
}
static inline bool xrp_pin_writable(unsigned p)
{ return p==0 || (p>=12 && p<=19); }
