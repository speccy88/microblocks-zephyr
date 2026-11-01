"""iPhone source contracts plus reproducible real-engine packaging tests."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_iphone_editor import package


class IPhoneContracts(unittest.TestCase):
    def test_native_port_limits_and_stale_event_contracts(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node required')
        result = subprocess.run([node, str(ROOT / 'tests/iphone-transport.test.cjs')],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1])['passed'], 8)

    def test_board_profiles_point_to_canonical_manifests_and_exclude_usb_only(self):
        profiles = json.loads((ROOT / 'ios/board-profiles.json').read_text())
        self.assertFalse(profiles['physical_iphone_validated'])
        boards = {b['id']: b for b in profiles['boards']}
        for b in boards.values():
            self.assertTrue((ROOT / b['manifest']).is_file())
        self.assertIsNone(boards['p2']['transport'])
        self.assertIsNone(boards['p4']['transport'])
        self.assertIsNone(boards['ble']['transport'])

    def test_native_scope_and_no_unsafe_transport_relaxations(self):
        project = (ROOT / 'ios/project.yml').read_text()
        self.assertIn('NSLocalNetworkUsageDescription:', project)
        self.assertIn('NSAllowsLocalNetworking: true', project)
        self.assertNotIn('NSAllowsArbitraryLoads', project)
        transport = (ROOT / 'ios/MicroBlocks/WirelessTransport.swift').read_text()
        self.assertIn('forHTTPHeaderField: "Origin"', transport)
        self.assertIn('.string("ready")', transport)
        self.assertIn('self.generation == token', transport)
        self.assertIn('completionHandler(nil)', transport)

    def test_board_primitive_aliases_match_canonical_ports(self):
        for name in ['boards/waveshare_esp32s3_rlcd_4_2/integration/rlcd_smallvm_primitives.c',
                     'boards/adafruit_fruit_jam/smallvm/src/platform.c',
                     'boards/sparkfun_xrp_rp2350/smallvm/src/platform.c']:
            self.assertIn('addPrimitiveSet(IOPrims', (ROOT / name).read_text())


class IPhonePackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get('JS_EDITOR_UPSTREAM', str(ROOT.parent / 'editor-upstream')))
        if not (cls.source / '.git').exists():
            raise unittest.SkipTest('Exact pinned upstream Git objects unavailable')

    def test_deterministic_profile_engine_integrity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / 'first', Path(temp) / 'second'
            a, b = package(self.source, first), package(self.source, second)
            self.assertEqual(a, b)
            self.assertFalse(a['physical_iphone_validated'])
            self.assertFalse(a['upstream_engine_modified'])
            for name, record in a['files'].items():
                data = (first / name).read_bytes()
                self.assertEqual(data, (second / name).read_bytes())
                self.assertEqual(hashlib.sha256(data).hexdigest(), record['sha256'])
            manifest = json.loads((first / 'source-manifest.json').read_text())
            for record in manifest['files']:
                self.assertEqual(hashlib.sha256((first / record['path']).read_bytes()).hexdigest(), record['sha256'])
            html = (first / 'index.html').read_text()
            self.assertIn('iphone-transport.js', html)
            self.assertNotIn('linux-compat.js', html)
            self.assertNotIn('user-scalable=no', html)
            for name, source in [('Waveshare RLCD 4.2.ubl', 'boards/waveshare_esp32s3_rlcd_4_2/integration/Waveshare_RLCD_4_2.ubl'),
                                 ('Fruit Jam.ubl', 'boards/adafruit_fruit_jam/integration/Fruit_Jam.ubl')]:
                self.assertEqual((first / 'Libraries/Zephyr' / name).read_bytes(), (ROOT / source).read_bytes())
            with self.assertRaises(FileExistsError):
                package(self.source, first)
            node = shutil.which('node')
            self.assertIsNotNone(node)
            result = subprocess.run([node, str(ROOT / 'tests/iphone-transport.test.cjs'), str(first)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1])['passed'], 9)


if __name__ == '__main__':
    unittest.main()
