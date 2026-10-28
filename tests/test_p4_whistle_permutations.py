"""No external model is needed for bounded metadata/value regression coverage."""
# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('p4_permutations', Path(__file__).resolve().parents[1] / 'tools/p4_whistle_permutations.py')
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)


def fixture(dtype=2):
    n = 120; base = 196 + n * 44; width = 4 if dtype == 2 else 2
    data = bytearray(base + 1024 * width)
    struct.pack_into('<I', data, 0, 0x05E12A84)
    struct.pack_into('<I', data, 4, n)
    struct.pack_into('<I', data, 28, 512)
    struct.pack_into('<I', data, 40, 4)
    for i in range(2):
        pos = 196 + (118 + i) * 44
        struct.pack_into('<BB', data, pos, dtype, 1)
        struct.pack_into('<I', data, pos + 4, 512)
        struct.pack_into('<QQ', data, pos + 20, base + i * 512 * width, 512 * width)
        struct.pack_into('<512' + ('f' if width == 4 else 'e'), data, base + i * 512 * width, *range(512))
    return data


class Permutations(unittest.TestCase):
    def test_half_and_float_match_indices(self):
        for dtype in (1, 2):
            self.assertEqual(p.permutations(fixture(dtype)), (tuple(range(512)),) * 2)

    def test_truncation_and_geometry(self):
        for data in (b'', fixture()[:195], fixture()[:5200], fixture()[:-1]):
            with self.assertRaises(ValueError): p.permutations(data)
        for offset, value in [(0, 0), (4, 0xffffffff), (8, 0xffffffff), (28, 1024), (40, 17)]:
            data = fixture(); struct.pack_into('<I', data, offset, value)
            with self.assertRaises(ValueError): p.permutations(data)

    def test_tensor_metadata_and_bounds(self):
        for offset, fmt, value in [(0, '<B', 3), (1, '<B', 2), (4, '<I', 513),
                                    (20, '<Q', 0), (20, '<Q', 2**64-1), (28, '<Q', 2047)]:
            data = fixture(); struct.pack_into(fmt, data, 196 + 118 * 44 + offset, value)
            with self.assertRaises(ValueError): p.permutations(data)

    def test_noninteger_nonfinite_out_of_range_and_duplicate(self):
        for value in (-1, 512, .5, float('nan'), float('inf'), 1):
            data = fixture(); struct.pack_into('<f', data, 196 + 120 * 44, value)
            with self.assertRaises(ValueError): p.permutations(data)

    def test_unreviewed_source_rejected(self):
        with self.assertRaises(ValueError): p.adapt_source(b'changed upstream')

    def test_generated_tables_are_const_and_complete(self):
        text = p.header(p.permutations(fixture()))
        self.assertEqual(text.count('static const int32_t'), 2)
        self.assertEqual(text.count('510, 511,'), 2)
