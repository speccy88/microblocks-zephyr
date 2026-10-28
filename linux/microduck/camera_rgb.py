"""BT.601 limited-range pixel interpretation matching the pinned Pollen sampler."""
# SPDX-License-Identifier: Apache-2.0
# Adapted arithmetic from pollen-robotics/microduck uyvy/src/lib.rs,
# commit 96b89d8613f06722c1d64ce75ab0d7124fed9d8f. See camera-rgb-NOTICE.txt.

def rgb24(y,u,v):
    if any(type(n) is not int or not 0 <= n <= 255 for n in (y,u,v)):
        raise ValueError('Raw UYVY components must be bytes')
    luma,u,v=y-16,u-128,v-128
    clamp=lambda n:max(0,min(255,n>>8))
    r=clamp(298*luma+409*v+128)
    g=clamp(298*luma-100*u-208*v+128)
    b=clamp(298*luma+516*u+128)
    return (r<<16)|(g<<8)|b
