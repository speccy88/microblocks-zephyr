"""Final assembly audit against a composed reviewed site."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.environ.get('MOBILE_SITE'),'requires composed site')
class JavaScriptPortal(unittest.TestCase):
    def test_main_entry_and_preserved_legacy_assets(self):
        site = Path(os.environ['MOBILE_SITE'])
        report = json.loads((site/'js-portal-manifest.json').read_text())
        self.assertEqual(report['default_editor'],'javascript')
        self.assertFalse(report['gp_branch_changed'])
        self.assertFalse(report['physical_hardware_validated'])
        for name,digest in report['preserved_files'].items():
            if name == 'index.html': continue
            self.assertEqual(hashlib.sha256((site/name).read_bytes()).hexdigest(),digest,name)
        self.assertIn('js-preview/fruit-jam/index.html',(site/'index.html').read_text())
        self.assertIn('legacy/portal.js',(site/'legacy/index.html').read_text())
        self.assertIn('editor/fruit-jam/microblocks.html',(site/'legacy/index.html').read_text())


if __name__ == '__main__': unittest.main()
