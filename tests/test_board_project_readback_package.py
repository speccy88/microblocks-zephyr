"""Connected-board recovery uses one canonical overlay on every editor surface."""
# SPDX-License-Identifier: MPL-2.0
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from js_editor_shared_assets import assets, SCRIPTS
from package_mobile_editor import mobile_files
from promote_js_portal import PROFILES


class BoardProjectReadbackPackage(unittest.TestCase):
    def test_canonical_overlay_and_startup_order(self):
        self.assertEqual(assets()['board-project-readback.js'],
                         (ROOT / 'web/js-editor/board-project-readback.js').read_bytes())
        self.assertIn('board-project-readback.js', SCRIPTS)
        for name in ['package_js_editor.py', 'package_iphone_editor.py',
                     'package_mobile_editor.py', 'promote_js_portal.py']:
            self.assertIn('from js_editor_shared_assets import', (ROOT / 'tools' / name).read_text())

    @unittest.skipUnless(os.environ.get('MOBILE_EDITOR_SOURCE'), 'requires verified editor cache')
    def test_mobile_packages_ship_the_same_fix_before_the_ui(self):
        for options in [{}, *[dict(runtime='board', board=name) for name in ['waveshare', 'fruit-jam', 'xrp-rp2350']]]:
            files, receipt = mobile_files(Path(os.environ['MOBILE_EDITOR_SOURCE']), **options)
            self.assertEqual(files['board-project-readback.js'], assets()['board-project-readback.js'])
            config = json.loads(re.search(r'<script id="mobile-load-config" type="application/json">(.*?)</script>',
                                         files['index.html'].decode()).group(1))
            names = [entry.get('src', '').split('?')[0] for entry in config['scripts']]
            self.assertLess(names.index('engine/mb-editor.js'), names.index('board-project-readback.js'))
            self.assertLess(names.index('board-project-readback.js'), names.index('ui/ide.js'))
            self.assertFalse(receipt['upstream_engine_modified'])

    @unittest.skipUnless(os.environ.get('MOBILE_SITE'), 'requires composed site')
    def test_all_desktop_profiles_ship_the_same_hashed_overlay(self):
        raw = assets()['board-project-readback.js']
        for profile in PROFILES:
            folder = Path(os.environ['MOBILE_SITE']) / 'js-preview' / profile
            self.assertEqual((folder / 'board-project-readback.js').read_bytes(), raw)
            receipt = json.loads((folder / 'build-manifest.json').read_text())
            self.assertTrue(receipt['connected_board_project_readback'])
            self.assertEqual(receipt['files']['board-project-readback.js']['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertIn('board-project-readback.js', (folder / 'files.txt').read_text().splitlines())
            self.assertLess((folder / 'index.html').read_text().index('board-project-readback.js'),
                            (folder / 'index.html').read_text().index('ui/ide.js'))
