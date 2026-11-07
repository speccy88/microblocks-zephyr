"""Shared custom-help coverage, deterministic packaging, and safe editor hooks."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import block_help


class BlockHelpTests(unittest.TestCase):
    def test_authored_coverage(self):
        self.assertEqual(set(block_help.inventory()), set(block_help.catalog()))
        self.assertGreater(len(block_help.catalog()), 300)
        self.assertEqual(block_help.inventory()['p2DigitalRead']['modules'], ['P2 Simple IO'])
        self.assertEqual(block_help.inventory()['p2TrianglePWM']['modules'], ['P2 PWM Triangle'])

    def test_missing_new_block_fails_build(self):
        inventory = block_help.inventory()
        inventory['newUndocumentedBlock'] = {}
        with patch.object(block_help, 'inventory', return_value=inventory):
            with self.assertRaisesRegex(ValueError, 'newUndocumentedBlock'):
                block_help.assets()

    def test_incomplete_or_duplicate_content_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'one.json'
            path.write_text(json.dumps({'schema': 1, 'blocks': {'x': {'summary': 'A block'}}}))
            with self.assertRaisesRegex(ValueError, 'missing returns'):
                block_help.catalog(Path(directory))
            path.write_text('{"schema":1,"blocks":{"x":{},"x":{}}}')
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
                block_help.catalog(Path(directory))

    def test_shared_assets_are_deterministic_and_injected_in_order(self):
        from js_editor_shared_assets import assets, scripts
        one, two = assets(), assets()
        for name in block_help.assets(): self.assertEqual(one[name], two[name])
        tags = scripts()
        self.assertLess(tags.index('block-help-index.js'), tags.index('block-help.js'))
        self.assertNotIn('block-help-data.js', tags)
        self.assertIn('block-help.html', one)
        page = one['block-help.html'].decode()
        for name in ('block-help-data.js', 'block-help-page.js', 'block-help.css'):
            version = hashlib.sha256(one[name]).hexdigest()[:16]
            self.assertIn(name + '?v=' + version, page)
        self.assertIn(hashlib.sha256(one['block-help.html']).hexdigest()[:16], one['block-help-index.js'].decode())

    @unittest.skipUnless(shutil.which('node'), 'Node is required for adapter test')
    def test_adapter_and_page(self):
        subprocess.run(['node', str(ROOT / 'tests/block-help.test.cjs')], check=True, cwd=ROOT)


if __name__ == '__main__': unittest.main()
