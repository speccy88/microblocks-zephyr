"""Pinned-source and packaging checks for the isolated JS editor migration."""
# SPDX-License-Identifier: MIT
import hashlib
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
from js_editor_source import candidate, load_manifest, safe_path, verified_files
from package_js_editor import package


class JSManifestTests(unittest.TestCase):
    def test_untrusted_paths_and_moving_refs_are_rejected(self):
        for path in ('../a', '/a', 'a//b', 'a/./b', 'a\\b', 'a:b', 'a\n'):
            with self.assertRaises(ValueError):
                safe_path(path)
        for ref in ('HEAD', 'dev', '--help', 'a' * 39):
            with self.assertRaises(ValueError):
                candidate(ROOT, ref)

    def test_existing_runtime_and_gp_pins_remain_separate(self):
        vm = load_manifest(ROOT / 'dependencies/smallvm-v417.json')
        gp = load_manifest(ROOT / 'dependencies/ide-assets.json')
        js = load_manifest(ROOT / 'dependencies/editor-js.json')
        self.assertEqual(vm['canonical_commit'], '2071df569623ba9cdcd6f8106b61796e047df38b')
        self.assertEqual(gp['source_commit'], '70690291ac44a5c3a50dce572ee0c29ba99dc57f')
        self.assertNotEqual(js['source_commit'], vm['canonical_commit'])
        paths = {f['path'] for f in js['files']}
        self.assertIn('engine/morphic.js', paths)
        self.assertIn('licenses/upstream/Mozilla Public License, version 2.0.html', paths)
        self.assertFalse(any(p.startswith(('precompiled/', 'esp32/')) for p in paths))


class JSVerifiedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get('JS_EDITOR_UPSTREAM',
            str(ROOT.parent / 'microblocks-editor-upstream-20261027')))
        if not (cls.source / '.git').exists():
            raise unittest.SkipTest('Pinned JS Git objects unavailable: set JS_EDITOR_UPSTREAM')

    def test_manifest_tampering_is_rejected(self):
        manifest = load_manifest(ROOT / 'dependencies/editor-js.json')
        manifest['files'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'differs'):
            verified_files(self.source, manifest)

    def test_deterministic_package_preserves_engine_and_loopback_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a', Path(temp) / 'b'
            first, second = package(self.source, a), package(self.source, b)
            self.assertEqual(first, second)
            for name, record in first['files'].items():
                data = (a / name).read_bytes()
                self.assertEqual(data, (b / name).read_bytes())
                self.assertEqual(hashlib.sha256(data).hexdigest(), record['sha256'])
            html = (a / 'index.html').read_text(encoding='utf-8')
            self.assertIn("location.hostname !== '127.0.0.1'", html)
            self.assertNotIn('linux-compat.js', (a / 'purejs.html').read_text(encoding='utf-8'))
            self.assertFalse(any(p.is_symlink() for p in a.rglob('*')))
            with self.assertRaises(FileExistsError):
                package(self.source, a)

    def test_actual_upstream_compiler_and_port_contract(self):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        if not node:
            self.skipTest('Node unavailable: set NODE_BINARY')
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / 'editor'
            package(self.source, assets)
            result = subprocess.run([node, str(ROOT / 'tests/js-editor-compat.test.cjs'), str(assets)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"passed":10', result.stdout)


if __name__ == '__main__':
    unittest.main()
