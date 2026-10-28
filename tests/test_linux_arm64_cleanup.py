"""Actual VM: protocol cleanup must not leave a task error pending."""
# SPDX-License-Identifier: MIT
import os
from pathlib import Path
import sys
import tempfile
import unittest
from linux_arm64_protocol import Runtime
from linux_arm64_protocol import words,op

BINARY=Path(os.environ.get('SMALLVM_MICRODUCK_BINARY',Path(__file__).resolve().parents[1]/'build-artifacts/linux-ci-native/smallvm'))
CODE12=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
CODE42=bytes([9,0,2,41,2,45,50,2,35,0,127,0,240,0,0,0,0,0,0,0])


@unittest.skipUnless(sys.platform=='linux' and BINARY.is_file(),'native Linux VM required')
class ProtocolCleanup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='vm-cleanup-');self.data=Path(self.temp.name);self.vm=Runtime(BINARY,self.data,821)
    def tearDown(self):self.vm.stop();self.temp.cleanup()
    def test_erase_then_first_new_arithmetic_task_has_no_display_error(self):
        wire=self.vm.wire;wire.upload(0,CODE12,2);self.assertEqual(wire.reporter(0),12)
        wire.short(14,1);wire.short(10,1);wire.ping()
        wire.upload(0,CODE42,2)
        self.assertEqual(wire.reporter(0),42);self.assertEqual(wire.reporter(0),42)
    def test_boardie_soft_reset_display_cleanup_does_not_poison_first_task(self):
        wire=self.vm.wire;wire.upload(0,CODE42,2);wire.short(15,3);wire.ping()
        self.assertEqual(wire.reporter(0),42)
    def test_explicit_unsupported_hardware_still_errors_without_poisoning_later_arithmetic(self):
        wire=self.vm.wire
        code=words([op(9),op(2,3),op(86,1),op(35),op(127),op(240),0,0])
        wire.upload(0,code,2)
        with self.assertRaisesRegex(RuntimeError,'1b'):wire.reporter(0)
        wire.upload(0,CODE42,2);self.assertEqual(wire.reporter(0),42)
