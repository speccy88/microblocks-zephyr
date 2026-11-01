"""Pinned source, offline composition and board packaging acceptance."""
# SPDX-License-Identifier: MIT
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import mobile_editor_source as source
import mobile_board_assets as board
from package_mobile_editor import mobile_files


class MobileSourceTests(unittest.TestCase):
    def test_reviewed_template_is_exact_upstream_source(self):
        item = next(r for r in json.loads(source.MANIFEST.read_text())['files'] if r['path'] == 'purejs.html')
        raw = (ROOT / 'web/mobile/purejs-source.html').read_bytes()
        self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (item['bytes'], item['sha256']))

    def test_optional_cache_and_encoded_routes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(board.source_for(Path(temp)))
            self.assertEqual(board.assets(None, 'waveshare'), {})
            with self.assertRaises(ValueError): board.source_for(Path(temp), Path(temp) / 'missing')
        self.assertEqual(board.route('mobile/Libraries/Zephyr/Fruit Jam.ubl'), '/mobile/Libraries/Zephyr/Fruit%20Jam.ubl')
        self.assertEqual(board.route("mobile/Examples/Music/L'Apprenti Sorcier.ubp"), "/mobile/Examples/Music/L'Apprenti%20Sorcier.ubp")
        self.assertEqual(board.route('mobile/Examples/Games/Simon (ED1).ubp'), '/mobile/Examples/Games/Simon%20(ED1).ubp')

    @unittest.skipUnless(os.environ.get('MOBILE_EDITOR_SOURCE'), 'requires verified local source cache')
    def test_actual_engine_assets_and_board_resource_budget(self):
        cache = Path(os.environ['MOBILE_EDITOR_SOURCE'])
        original = source.read_editor(cache)
        pages, _ = mobile_files(cache)
        for name, raw in original.items():
            if name.startswith('engine/'):
                self.assertEqual(pages[name], raw, name)
        for target in ['waveshare', 'fruit-jam', 'xrp-rp2350']:
            files = board.assets(cache, target)
            self.assertIn('index.html', files)
            self.assertIn('mobile/index.html', files)
            self.assertIn(b'"runtime":"board"', files['mobile/index.html'])
            self.assertIn(b'../microblocks.html?layout=desktop', files['mobile/index.html'])
            self.assertNotIn(b'https://cdn.', b''.join(v for n,v in files.items() if n.startswith('mobile/mobile-')))
            self.assertEqual(len({board.route(n) for n in files}), len(files))
            self.assertLess(max(len(board.route(n)) for n in files), 256)
            self.assertLess(board.summary(files)['added_flash_bytes'], 3 * 1024 * 1024)
            for name, raw in files.items():
                self.assertEqual(gzip.decompress(gzip.compress(raw, mtime=0)), raw, name)

    @unittest.skipUnless(os.environ.get('MOBILE_SITE'), 'requires composed reviewed site')
    def test_every_preexisting_site_asset_is_preserved(self):
        site = Path(os.environ['MOBILE_SITE'])
        report = json.loads((site / 'mobile-web-manifest.json').read_text())
        self.assertEqual(report['changed_existing_files'], ['index.html'])
        self.assertGreater(len(report['preserved_existing_files']), 5000)
        for name, digest in {**report['preserved_existing_files'], **report['added_files'], 'index.html':report['landing_sha256']}.items():
            self.assertEqual(hashlib.sha256((site / name).read_bytes()).hexdigest(), digest, name)


if __name__ == '__main__': unittest.main()
