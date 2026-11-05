"""Installation choices expose reviewed methods without pretending to flash."""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from board_installation_pages import guide_assets, installation_url, load_catalog, render_launcher
from promote_js_portal import PROFILES


class BoardInstallationPages(unittest.TestCase):
    def test_every_editor_has_a_reviewed_installation_choice(self):
        catalog = load_catalog(PROFILES)
        direct = [board for board in catalog['boards'] if board['mode'] == 'browser']
        self.assertEqual([board['id'] for board in direct], ['propeller2'])
        self.assertEqual(installation_url(direct[0]), 'install/propeller2/index.html')
        boards = {board['id']: board for board in catalog['boards']}
        self.assertEqual(boards['microduck']['release']['kind'], 'pending')
        self.assertEqual(boards['raspberry-pi5']['release']['kind'], 'older_release')
        self.assertEqual(boards['unoq']['release']['kind'], 'reference_release')
        for key in ['fruit-jam', 'waveshare', 'esp32p4', 'xrp-rp2350']:
            self.assertEqual(boards[key]['release']['kind'], 'source_only')

    def test_paired_links_and_seven_guides_preserve_the_p2_packager(self):
        catalog = load_catalog(PROFILES)
        template = (ROOT / 'web/js-portal/index.html').read_text(encoding='utf-8')
        html = render_launcher(template, catalog)
        self.assertEqual(html.count('class="board-choice"'), 8)
        self.assertEqual(html.count('class="board-install"'), 8)
        files = guide_assets(catalog, 'checked-css')
        self.assertEqual(len([key for key in files if key.endswith('/index.html')]), 7)
        self.assertNotIn('install/propeller2/index.html', files)
        for key, raw in files.items():
            if not key.endswith('.html'):
                continue
            self.assertNotIn(b'<script', raw)
            self.assertNotIn(b'<iframe', raw)
            self.assertIn(b'portal.css?v=checked-css', raw)
            self.assertIn(b'Release availability', raw)
            self.assertIn(b'target="_blank" rel="noopener noreferrer"', raw)
        with self.assertRaises(ValueError):
            load_catalog(PROFILES[:-1])


if __name__ == '__main__':
    unittest.main()
