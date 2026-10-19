"""Offline integration checks; these do not establish physical P2 behavior."""
# SPDX-License-Identifier: MIT
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from package_pages import p2_package


class Propeller2Tests(unittest.TestCase):
    def test_library_primitive_contract_and_reserved_ranges(self):
        board = ROOT/'boards/propeller2'
        library = (board/'integration/P2_Hardware.ubl').read_text(encoding='utf-8')
        source = (board/'native/propeller2/p2IOPrims.c').read_text(encoding='utf-8')
        names = re.findall(r"\[p2:([^\]]+)\]", library)
        self.assertGreaterEqual(len(names), 15)
        for name in names:
            self.assertIn('{"'+name+'",', source)
        self.assertIn('validPin(pin + offset)', source)
        self.assertIn('(mode & 0x3e) == P_USB_PAIR', source)
        hardware = json.loads((board/'hardware.json').read_text())
        self.assertFalse(hardware['zephyr'])
        self.assertEqual(hardware['variants']['edge32']['user_pins'], [0, 39])
        self.assertEqual(hardware['variants']['edge32']['psram_reserved_pins'], [40, 57])

    def test_real_editor_patch_routes_p2_names_and_examples(self):
        # Synthetic upstream package exercises the real repacker's anchors.
        files = [('/Compiler.gp', b"atPut primsets 'unoq' (at primsets 'io')"),
            ('/API.gp', b"endPoint == 'unoq.loadLibrary' Libraries/UNO_Q_Hardware.ubl 'UNO Q Hardware' unoq.openExample 'Examples/UNO Q/' 'arithmetic' 'output' 'rgb' 'matrix' 'combined' 'matrix-drawing'"),
            ('/Libraries/UNO_Q_Hardware.ubl', b'old'),
            ('/Examples/UNO Q/arithmetic.ubp', b'module main'),
            ('/Examples/UNO Q/output.ubp', b'repeat 500 {')]
        data = bytearray(); entries = []
        for name, payload in files:
            start = len(data); data.extend(payload)
            entries.append(dict(filename=name, start=start, end=len(data)))
        metadata = json.dumps(dict(files=entries, remote_package_size=len(data)), separators=(',', ':'))
        metadata = re.sub(r'"(files|filename|start|end|remote_package_size)":', r'\1:', metadata)
        js, packed = p2_package(('loadPackage('+metadata+')').encode(), bytes(data), b'P2 library')
        self.assertIn(b"atPut primsets 'p2'", packed)
        self.assertIn(b'p2.loadLibrary', packed)
        self.assertIn(b'P2 library', packed)
        self.assertIn(b'/Libraries/P2_Hardware.ubl', js)
        self.assertIn(b'/Examples/P2/arithmetic.ubp', js)
        self.assertIn(b'repeat 50 {', packed)
        self.assertNotIn(b'unoq.loadLibrary', packed)


if __name__ == '__main__':
    unittest.main()
