#!/usr/bin/env python3
"""Packaging tests use non-executable headers, never a release or working VM."""
# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('linux_arm64_package', REPO / 'linux/arm64/package.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CandidatePackage(unittest.TestCase):
    def setUp(self):
        parent = REPO / 'build-artifacts/linux-arm64-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=parent)
        self.work = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def fixture(self):
        data = bytearray(64); data[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', data, 18, 183)
        return bytes(data)

    def test_reproducible_bytes_and_checksum(self):
        a = self.work / 'a.tar.gz'; b = self.work / 'b.tar.gz'
        first = module.package(self.fixture(), b'MPL-2.0 fixture', a, 'v417-test', epoch=1234)
        second = module.package(self.fixture(), b'MPL-2.0 fixture', b, 'v417-test', epoch=1234)
        self.assertEqual(first, second)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertTrue(a.with_name(a.name + '.sha256').read_text().startswith(first))
        with tarfile.open(a) as archive:
            self.assertEqual(set(archive.getnames()), {'smallvm', 'manifest.json', 'LICENSE', 'NOTICE'})
            self.assertTrue(all(member.uid == 0 and member.mtime == 1234 for member in archive.getmembers()))

    def test_foreign_binary_rejected(self):
        with self.assertRaises(ValueError):
            module.package(b'#!/bin/sh\n', b'MPL-2.0', Path('unused'), 'v417-test')

    def test_latest_rejected(self):
        with self.assertRaises(ValueError):
            module.package(self.fixture(), b'MPL-2.0', Path('unused'), 'latest')

    def test_existing_file_not_overwritten(self):
        target = self.work / 'keep'; target.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            module.package(self.fixture(), b'MPL-2.0', target, 'v417-test')
        self.assertEqual(target.read_bytes(), b'keep')

    def test_existing_checksum_not_overwritten(self):
        target = self.work / 'package.tar.gz'
        checksum = target.with_name(target.name + '.sha256'); checksum.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            module.package(self.fixture(), b'MPL-2.0', target, 'v417-test')
        self.assertEqual(checksum.read_bytes(), b'keep')
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
