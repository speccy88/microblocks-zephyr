"""Final assembly audit against a composed reviewed site."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import unittest


@unittest.skipUnless(os.environ.get('MOBILE_SITE'),'requires composed site')
class JavaScriptPortal(unittest.TestCase):
    def test_main_entry_preserves_js_and_omits_gp_deployment(self):
        site = Path(os.environ['MOBILE_SITE'])
        report = json.loads((site/'js-portal-manifest.json').read_text())
        self.assertEqual(report['default_editor'],'javascript')
        self.assertFalse(report['gp_branch_changed'])
        self.assertFalse(report['physical_hardware_validated'])
        for name,digest in report['preserved_files'].items():
            if name == 'index.html': continue
            self.assertEqual(hashlib.sha256((site/name).read_bytes()).hexdigest(),digest,name)
        self.assertIn('js-preview/fruit-jam/index.html',(site/'index.html').read_text())
        self.assertIsNone(report['legacy_entry'])
        self.assertFalse(report['gp_editor_published'])
        self.assertNotIn('legacy/',(site/'index.html').read_text())
        for folder in ['legacy', 'editor', 'preview']:
            self.assertFalse((site/folder).exists(), folder)
        for name in report['omitted_gp_files']:
            self.assertFalse((site/name).exists(), name)
        self.assertFalse(list(site.rglob('gp_wasm*')))

    def test_p2_runtime_profile_matches_current_library(self):
        site = Path(os.environ['MOBILE_SITE'])/'js-preview/propeller2'
        profile = json.loads((site/'target-profile.json').read_text())
        source = json.loads((site/'target-library-source.json').read_text())
        self.assertEqual(profile['function_names'], source['function_names'])
        self.assertTrue(profile['auto_load_target_blocks'])
        self.assertEqual(profile['target_library_sha256'], source['sha256'])
        runtime = (site/'target-config.js').read_text()
        self.assertIn(json.dumps(profile, separators=(',', ':')), runtime)
        html = (site/'index.html').read_text()
        self.assertIn('target-config.js?v='+hashlib.sha256(runtime.encode()).hexdigest()[:16], html)
        self.assertIn('target-blocks.js?v=', html)


if __name__ == '__main__': unittest.main()
