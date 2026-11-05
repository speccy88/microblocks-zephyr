"""P2 installer protocol tests are software evidence, not hardware acceptance."""
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_p2_web_firmware import reviewed_sources


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
        self.assertEqual(pin['firmware_source_commit'],'ac4fce0a118761b2d75add8147e946e0e43aa4ca')
        html=(ROOT/'web/p2-installer/index.html').read_text(encoding='utf-8')
        self.assertIn('2–8 MB',html)
        self.assertIn('RAM load can therefore affect saved flash projects',html)
        self.assertNotIn('checked',html)

    def test_reviewed_installer_does_not_take_candidate_sources(self):
        pin=json.loads((ROOT/'dependencies/p2-web-installer.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='p2-source-pin-') as folder:
            provenance=reviewed_sources(pin,Path(folder))
            self.assertEqual(provenance['firmware_source_commit'],pin['firmware_source_commit'])
            self.assertFalse((Path(folder)/'boards/propeller2/native/propeller2/p2LEDs.c').exists())
            self.assertNotIn('p2LEDs.c',(Path(folder)/'tools/build_propeller2.py').read_text(encoding='utf-8'))
            self.assertGreater(len(provenance['native_sources_sha256']),15)
