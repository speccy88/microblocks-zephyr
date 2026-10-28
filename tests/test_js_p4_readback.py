# SPDX-License-Identifier: MPL-2.0
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


class JSP4Readback(unittest.TestCase):
    def test_full_libraries_and_non_writing_connection_readback(self):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if not node or not (source / '.git').exists():
            self.skipTest('Pinned JS source and Node required')
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / 'p4'
            package(source, assets, profile='esp32p4')
            result = subprocess.run([node, str(ROOT / 'tests/js-p4-readback.test.cjs'), str(assets)], capture_output=True, text=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual((report['passed'], report['functions'], report['specs']), (5, 64, 189))
            self.assertTrue(report['readback_queries_only'])
            self.assertFalse(report['physical_hardware'])
