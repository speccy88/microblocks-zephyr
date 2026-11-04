"""The current P2 blocks must reach the frozen editor without changing engines."""
# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from js_editor_shared_assets import target_assets


class P2TargetAssets(unittest.TestCase):
    def test_grouped_bundle_preserves_canonical_source_and_unique_api(self):
        files = target_assets('propeller2')
        receipt = json.loads(files['target-library-source.json'])
        raw = (ROOT/receipt['source_path']).read_bytes()
        self.assertEqual(receipt['canonical_source_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['sha256'], hashlib.sha256(files[receipt['bundle']]).hexdigest())
        self.assertEqual(receipt['modules'], ['P2 Core','P2 Signals','P2 Serial','P2 Analog','P2 Capture'])
        self.assertEqual(len(receipt['function_names']), len(set(receipt['function_names'])))
        self.assertEqual(files[receipt['bundle']], b'\n'.join(files['Libraries/P2/'+name+'.ubl'] for name in receipt['modules']))
        self.assertNotIn(b"module 'P2 Hardware'", files[receipt['bundle']])
        self.assertEqual(receipt['required_extension_revision'], 8)
        self.assertIn('p2Quadrature', receipt['function_names'])
        self.assertIn(b'[p2:p2CogStart]', raw)
        self.assertEqual(target_assets('waveshare'), {})
