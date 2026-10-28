# SPDX-License-Identifier: MPL-2.0
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
from package_js_editor import package, PROFILES


class JSBoardProfiles(unittest.TestCase):
    def node(self):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        return node

    def test_usb_ownership_identity_and_reconnect_queue(self):
        result = subprocess.run([self.node(), str(ROOT / 'tests/js-board-transport.test.cjs')],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['passed'], 14)

    def test_exact_gp_library_sources_remain_bound_to_existing_pin(self):
        record = json.loads((ROOT / 'dependencies/gp-board-libraries.json').read_text(encoding='utf-8'))
        gp = json.loads((ROOT / 'dependencies/ide-assets.json').read_text(encoding='utf-8'))
        self.assertEqual(record['source_commit'], gp['source_commit'])
        for entry in record['files']:
            self.assertEqual(hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest(), entry['sha256'])
        xrp = next(entry for entry in record['files'] if entry['path'] == 'integration/XRP.ubl')
        self.assertEqual(xrp['sha256'], 'c137323584dbe1401b24962eed68a6a5a168215c30094ecf9098430a4c48aa66')
        self.assertEqual(PROFILES['propeller2']['vm_versions'], [405])
        self.assertIn('"v405"', (ROOT / 'boards/propeller2/native/vm/version.h').read_text(encoding='utf-8'))

    def test_all_board_libraries_compile_with_actual_classes_and_roundtrip(self):
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if not (source / '.git').exists():
            self.skipTest('Pinned JS source unavailable')
        ids = [name for name, profile in PROFILES.items() if profile['kind'] == 'serial']
        with tempfile.TemporaryDirectory() as temp:
            for name in ids:
                package(source, Path(temp) / name, profile=name)
            result = subprocess.run([self.node(), str(ROOT / 'tests/js-board-libraries.test.cjs'), temp, *ids],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report['profiles'], 6)
            self.assertTrue(report['actual_pinned_compiler'])
            self.assertTrue(report['roundtrip'])
            result = subprocess.run([self.node(), str(ROOT / 'tests/js-board-connection.test.cjs'), temp, *ids],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertTrue(report['actual_pinned_connection'])
            self.assertTrue(report['wrong_identity_blocked'])
            self.assertEqual(len(report['profiles']), 6)


if __name__ == '__main__':
    unittest.main()
