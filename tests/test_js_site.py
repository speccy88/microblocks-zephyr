# SPDX-License-Identifier: MPL-2.0
import importlib.util
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
from package_js_editor import package
from package_js_site import build, hashes


class JSTargetProfiles(unittest.TestCase):
    def test_target_policy_blocks_providers_before_connection(self):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        result = subprocess.run([node, str(ROOT / 'tests/js-target-profile.test.cjs')], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['passed'], 10)

    def test_unknown_profile_fails_before_source_or_output_access(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            package(Path('absent'), Path('unused'), profile='unknown')

    def test_side_by_side_preserves_gp_and_separates_robot_libraries(self):
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if not (source / '.git').exists():
            self.skipTest('Pinned JS source unavailable')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            gp = base / 'gp'
            gp.mkdir()
            (gp / 'index.html').write_bytes(b'unchanged GP portal')
            (gp / 'sample.bin').write_bytes(bytes(range(256)))
            before = hashes(gp)
            output = base / 'combined'
            report = build(source, gp, output, profiles=('raspberry-pi5', 'microduck'))
            self.assertEqual(report['gp_files_preserved'], before)
            self.assertEqual(hashes(gp), before)
            for name, digest in before.items():
                self.assertEqual(hashes(output)[name], digest)
            pi, duck = output / 'js-preview/raspberry-pi5', output / 'js-preview/microduck'
            self.assertFalse((pi / 'Libraries/MicroDuck Linux.ubl').exists())
            self.assertTrue((duck / 'Libraries/MicroDuck Linux.ubl').is_file())
            for profile in (pi, duck):
                self.assertFalse((profile / 'purejs.html').exists())
                self.assertTrue((profile / 'sources/upstream-entry/purejs.html.txt').is_file())
                self.assertIn('target-config.js', (profile / 'index.html').read_text(encoding='utf-8'))
            self.assertFalse(json.loads((pi / 'target-profile.json').read_text())['requires_robot_services'])
            self.assertTrue(json.loads((duck / 'target-profile.json').read_text())['placeholder'])
            self.assertEqual((pi / 'engine/mb-compiler.js').read_bytes(), (duck / 'engine/mb-compiler.js').read_bytes())
            node = os.environ.get('NODE_BINARY') or shutil.which('node')
            if node:
                result = subprocess.run([node, str(ROOT / 'tests/js-profile-integration.test.cjs'), str(pi), str(duck)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(json.loads(result.stdout.strip().splitlines()[-1])['actual_pinned_comm_port'])
                result = subprocess.run([node, str(ROOT / 'tests/js-typed-libraries.test.cjs'), str(duck)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['functions'], 169)
            with self.assertRaises(FileExistsError):
                build(source, gp, output)
            with self.assertRaisesRegex(ValueError, 'separate'):
                build(source, gp, gp / 'nested')


if __name__ == '__main__':
    unittest.main()
