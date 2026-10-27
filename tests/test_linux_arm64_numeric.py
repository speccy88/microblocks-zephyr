"""Concrete numeric regressions executed by the real LP64 interpreter over PTY.

No board or network is used. Build and runtime data live in disposable native
Linux directories. Sanitizer diagnostics fail even when UBSan recovers.
Set SMALLVM_NUMERIC_BINARY to an absolute executable path to test an already
built binary without a compiler or Git source. The adjacent protocol helper is
the only other repository file required in that mode.
"""
# SPDX-License-Identifier: MPL-2.0
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL_BINARY = os.environ.get('SMALLVM_NUMERIC_BINARY')
protocol = None
if platform.system() == 'Linux':
    spec = importlib.util.spec_from_file_location('numeric_wire_protocol', ROOT / 'tests/linux_arm64_protocol.py')
    protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(protocol)


def push(value):
    return b'\x04\x00' + struct.pack('<I', ((value << 1) | 1) & 0xFFFFFFFF)


def finish(code):
    code += b'\x23\x00\x7f\x00\xf0\x00' + b'\x00' * 6
    return code + (b'\x00\x00' if len(code) % 4 else b'')


def signed31(value):
    value &= 0x7FFFFFFF
    return value - 0x80000000 if value & 0x40000000 else value


@unittest.skipUnless(platform.system() == 'Linux' and struct.calcsize('P') == 8
                     and (EXTERNAL_BINARY or (shutil.which('gcc') and (SOURCE / '.git').is_dir())),
                     'requires LP64 Linux and an external binary or local GCC/pinned source; no fetch')
class RealInterpreterNumeric(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='smallvm-numeric-')
        cls.work = Path(cls.temporary.name)
        if EXTERNAL_BINARY:
            candidate = Path(EXTERNAL_BINARY)
            if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
                cls.temporary.cleanup()
                raise AssertionError('SMALLVM_NUMERIC_BINARY must name an absolute existing executable')
            cls.binary = candidate.resolve(strict=True)
            return
        build = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.work / 'build'), '--sanitize'],
                               capture_output=True, text=True, timeout=60)
        if build.returncode:
            cls.temporary.cleanup()
            raise AssertionError(build.stdout + build.stderr)
        cls.binary = cls.work / 'build/smallvm'

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @contextmanager
    def runtime(self):
        data = Path(tempfile.mkdtemp(prefix='data-', dir=self.work))
        runtime = protocol.Runtime(self.binary, data, 1)
        try:
            yield runtime.wire
        finally:
            try:
                runtime.stop()
            finally:
                log = (data / 'process-1.log').read_text(encoding='utf-8')
                self.assertEqual(runtime.process.returncode, 0, log)
                self.assertNotIn('runtime error:', log)
                self.assertNotIn('AddressSanitizer', log)

    def execute(self, vm, code, expected=None, error=None):
        vm.upload(0, code, 2)
        start = len(vm.events)
        vm.short(3, 0)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            for kind, index, payload in vm.events[start:]:
                if index != 0 or kind not in (18, 19):
                    continue
                if error is not None:
                    self.assertEqual(kind, 19, 'invalid numeric input must fail the task')
                    self.assertEqual(payload[0], error)
                else:
                    self.assertEqual(kind, 18, 'valid input must return an integer')
                    self.assertEqual(len(payload), 5)
                    self.assertEqual(payload[0], 1)
                    self.assertEqual(struct.unpack('<i', payload[1:])[0], expected)
                return
            vm.pump(.02)
        self.fail('interpreter did not return a result or VM error')

    def test_long_multiply_shift_has_defined_signed64_behavior_and_bounds(self):
        with self.runtime() as vm:
            for left, right in ((-2, 3), (-1073741824, 1073741823), (0, 1073741823)):
                for count in (0, 1, 31, 32, 62, 63):
                    with self.subTest(left=left, right=right, count=count):
                        self.execute(vm, finish(b'\x09\x00' + push(left) + push(right) + push(count) + b'\x46\x03'),
                                     expected=signed31((left * right) >> count))
            for count in (-1, 64, 1000):
                with self.subTest(invalid_count=count):
                    self.execute(vm, finish(b'\x09\x00' + push(-2) + push(3) + push(count) + b'\x46\x03'), error=32)
            self.execute(vm, finish(b'\x09\x00' + push(2) + push(3) + b'\x46\x02'), error=28)

    def test_decimal_prefix_conversion_is_bounded_to_signed31(self):
        with self.runtime() as vm:
            for text, expected in ((b'-1073741824', -1073741824), (b'1073741823', 1073741823),
                                   (b' \t+123tail', 123), (b'no digits', 0), (b'-0', 0)):
                with self.subTest(valid=text):
                    vm.long(8, 0, b'\x02' + text)
                    vm.ping(81)
                    self.execute(vm, finish(b'\x09\x00\x06\x00' + push(0) + b'\x32\x02'), expected=expected)
            for text in (b'-2147483648', b'2147483647', b'1073741824', b'-1073741825',
                         b'9223372036854775808', b'-999999999999999999999999999'):
                vm.long(8, 0, b'\x02' + text)
                vm.ping(82)
                for opcode in (50, 53, 54, 71):
                    with self.subTest(invalid=text, opcode=opcode):
                        code = b'\x09\x00\x06\x00'
                        if opcode != 71:
                            code += push(-1)
                        self.execute(vm, finish(code + bytes((opcode, 1 if opcode == 71 else 2))), error=44)
            # Existing zero-divide error and signed31 wrap behavior survive.
            for opcode in (53, 54):
                self.execute(vm, finish(b'\x09\x00' + push(-1073741824) + push(0) + bytes((opcode, 2))), error=31)
            self.execute(vm, finish(b'\x09\x00' + push(-1073741824) + push(-1) + b'\x35\x02'), expected=-1073741824)
            self.execute(vm, finish(b'\x09\x00' + push(-1073741824) + push(-1) + b'\x36\x02'), expected=0)
            self.execute(vm, finish(b'\x09\x00' + push(1073741823) + push(-1073741824) + b'\x36\x02'), expected=1073741823)

    def test_byte_array_decimal_conversion_ignores_storage_padding(self):
        with self.runtime() as vm:
            # newByteArray(3, ASCII '9') stores four '9' bytes in its one payload
            # word, but only the first three belong to the byte array. The old
            # strtol-based evalInt incorrectly read padding and returned 9999.
            code = bytearray(b'\x09\x00' + push(3) + push(57))
            second_word = len(code) + 2
            code += b'\x25\x02\x00\x00' + push(0) + b'\x32\x02\x23\x00'
            self.assertEqual(len(code) % 4, 0)
            offset = (len(code) - second_word) // 2
            struct.pack_into('<H', code, second_word, (1 << 10) | offset)  # DataPrims=1
            name = b'newByteArray\x00'
            name += b'\x00' * (-len(name) % 4)
            code += struct.pack('<I', ((len(name) // 4) << 4) | 4) + name
            code += b'\x7f\x00\xf0\x00' + b'\x00' * 8
            self.execute(vm, bytes(code), expected=999)


if __name__ == '__main__':
    unittest.main()
