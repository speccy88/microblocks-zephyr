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
    def test_packaged_bundle_is_exact_canonical_library(self):
        files = target_assets('propeller2')
        receipt = json.loads(files['target-library-source.json'])
        raw = (ROOT/receipt['source_path']).read_bytes()
        self.assertEqual(files[receipt['bundle']], raw)
        self.assertEqual(receipt['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipt['required_extension_revision'], 1)
        self.assertIn(b'[p2:p2CogStart]', raw)
        self.assertEqual(target_assets('waveshare'), {})
