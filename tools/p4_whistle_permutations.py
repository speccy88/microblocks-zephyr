"""Freeze only the pinned Whistle model's CPU lookup tables in flash.

The verified third-party source remains untouched; preparation adapts a generated
copy. Layout constants are from nd_cact.h and nd_whistle_open at the pinned commit.
"""
# SPDX-License-Identifier: MIT
import hashlib
import math
import struct

SOURCE_SHA256 = '7599be8184095236bcf02d496cd5beae84f40f81aefefc55a9abd582fec90282'
DECLARATION = 'static int32_t s_perm1[512], s_perm2[512];'
INITIALIZATION = '''        s_perm1[i] = (int32_t)hv(w, w->i_perm1, i);
        s_perm2[i] = (int32_t)hv(w, w->i_perm2, i);'''
CHECK = '''        /* Generated const tables must match this model before inference. */
        if (hv(w, w->i_perm1, i) != (float)s_perm1[i] ||
            hv(w, w->i_perm2, i) != (float)s_perm2[i])
            return -13;'''


def permutations(data):
    """Read two bounded v4 tensors, rejecting values unsafe as array indices."""
    if len(data) < 196:
        raise ValueError('Truncated CACT v4 header')
    h = struct.unpack_from('<48If', data)
    if h[0] != 0x05E12A84 or h[7] != 512 or not 1 <= h[10] <= 16:
        raise ValueError('Unsupported CACT geometry')
    n, codebook = h[1:3]
    directory = 196 + codebook * 4
    end = directory + n * 44
    first = 10 + h[10] * 27
    if n <= first + 1 or end > len(data):
        raise ValueError('Truncated CACT directory')
    result = []
    for index in (first, first + 1):
        pos = directory + index * 44
        dtype, ndim = struct.unpack_from('<BB', data, pos)
        shape = struct.unpack_from('<4I', data, pos + 4)
        offset, size = struct.unpack_from('<QQ', data, pos + 20)
        if dtype not in (1, 2) or ndim != 1 or shape[0] != 512:
            raise ValueError('Unsupported permutation tensor')
        width, fmt = (2, 'e') if dtype == 1 else (4, 'f')
        if size != 512 * width or offset < end or offset + size > len(data):
            raise ValueError('Permutation payload bounds')
        values = struct.unpack_from('<512' + fmt, data, offset)
        if any(not math.isfinite(v) or not v.is_integer() or not 0 <= v < 512 for v in values):
            raise ValueError('Permutation values must be integer indices 0..511')
        values = tuple(map(int, values))
        if len(set(values)) != 512:
            raise ValueError('Permutation contains duplicate indices')
        result.append(values)
    return tuple(result)


def adapt_source(raw):
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unreviewed Whistle source for const adaptation')
    text = raw.decode('utf-8')
    for anchor in (DECLARATION, INITIALIZATION):
        if text.count(anchor) != 1:
            raise ValueError('Whistle adaptation anchor mismatch')
    return text.replace(DECLARATION, '#include "whistle_permutations.h"').replace(INITIALIZATION, CHECK)


def header(tables):
    lines = ['/* Generated from the verified model; never edit. */']
    for i, values in enumerate(tables, 1):
        lines.append(f'static const int32_t s_perm{i}[512] = {{')
        lines += ['    ' + ', '.join(map(str, values[p:p + 16])) + ',' for p in range(0, 512, 16)]
        lines.append('};')
    return '\n'.join(lines) + '\n'
