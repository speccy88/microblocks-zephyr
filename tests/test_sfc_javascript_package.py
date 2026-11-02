"""SFC uses shared JS overlays and the unchanged upstream engine in each surface."""
# SPDX-License-Identifier: MPL-2.0
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sfc_js_assets import assets, SCRIPTS
from package_mobile_editor import mobile_files
from promote_js_portal import PROFILES


class JavaScriptSFCAssets(unittest.TestCase):
    def test_examples_are_valid_native_sources_with_no_generated_workers(self):
        files=assets()
        self.assertEqual(len(files),12)
        for name,raw in files.items():
            if name.endswith('.ubp'):
                self.assertIn(b'sfcSequence',raw,name)
                self.assertNotIn(b'_sfc1_worker',raw,name)
        self.assertEqual(tuple(n for n in files if n.endswith('.js')),SCRIPTS)

    @unittest.skipUnless(os.environ.get('MOBILE_EDITOR_SOURCE'),'requires verified editor cache')
    def test_same_overlay_and_examples_in_pages_and_all_board_packages(self):
        source=Path(os.environ['MOBILE_EDITOR_SOURCE'])
        for options in [{},*[{'runtime':'board','board':n} for n in ['waveshare','fruit-jam','xrp-rp2350']]]:
            files,receipt=mobile_files(source,**options)
            for name,raw in assets().items():self.assertEqual(files[name],raw,name)
            self.assertFalse(receipt['upstream_engine_modified'])
            html=files['index.html'].decode()
            self.assertLess(html.index('sfc-core.js'),html.index('sfc-editor.js'))
            self.assertLess(html.index('sfc-editor.js'),html.index('ui/ide.js'))
            self.assertEqual(len([n for n in files if n.startswith('Examples/SFC/')]),10)

    @unittest.skipUnless(os.environ.get('MOBILE_SITE'),'requires composed site')
    def test_every_web_profile_ships_the_same_sfc_and_pinned_engine(self):
        site=Path(os.environ['MOBILE_SITE']);source=json.loads((ROOT/'dependencies/editor-js.json').read_text())
        for profile in PROFILES:
            folder=site/'js-preview'/profile
            receipt=json.loads((folder/'build-manifest.json').read_text())
            self.assertTrue(receipt['native_sfc_javascript'])
            for name,raw in assets().items():self.assertEqual((folder/name).read_bytes(),raw)
            for item in source['files']:
                if item['path'].startswith('engine/'):
                    self.assertEqual(hashlib.sha256((folder/item['path']).read_bytes()).hexdigest(),item['sha256'])


if __name__=='__main__':unittest.main()
