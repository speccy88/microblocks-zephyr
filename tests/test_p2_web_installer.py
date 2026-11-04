"""P2 installer protocol tests are software evidence, not hardware acceptance."""
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]


class P2WebInstaller(unittest.TestCase):
    def test_real_loader_protocol_and_failure_cases(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        result=subprocess.run([node,'--test',str(ROOT/'tests/p2-installer.test.cjs')],cwd=ROOT,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_images_are_explicit_source_pins_and_ram_storage_effects_are_disclosed(self):
        pin=json.loads((ROOT/'dependencies/p2-web-installer.json').read_text(encoding='utf-8'))
        self.assertEqual(set(pin['expected_images']),{'eval','edge','edge32'})
        self.assertEqual(pin['extension_revision'],8)
        html=(ROOT/'web/p2-installer/index.html').read_text(encoding='utf-8')
        self.assertIn('2–8 MB',html)
        self.assertIn('RAM load can therefore affect saved flash projects',html)
        self.assertNotIn('checked',html)
