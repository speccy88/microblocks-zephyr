"""Installer bundle integrity and immutable-copy behavior; no host installation."""
# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'linux/arm64'))
spec=importlib.util.spec_from_file_location('pi_install_bundle',ROOT/'linux/arm64/install_bundle.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


class BundleIntegrity(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def fixture(self):
        (self.root/'file').write_bytes(b'checked')
        manifest={'platform':'raspberry-pi5-aarch64','files':{'file':hashlib.sha256(b'checked').hexdigest()}}
        (self.root/'bundle-manifest.json').write_text(json.dumps(manifest));return manifest
    def test_exact_manifest_verifies(self):
        self.fixture();manifest,digest=b.verify_bundle(self.root)
        self.assertEqual(manifest['platform'],'raspberry-pi5-aarch64');self.assertEqual(len(digest),64)
    def test_changed_payload_is_rejected(self):
        self.fixture();(self.root/'file').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):b.verify_bundle(self.root)
    def test_unlisted_payload_and_different_target_are_rejected(self):
        manifest=self.fixture();(self.root/'extra').write_bytes(b'unlisted')
        with self.assertRaisesRegex(ValueError,'member set'):b.verify_bundle(self.root)
        (self.root/'extra').unlink();manifest['platform']='microduck';(self.root/'bundle-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'target'):b.verify_bundle(self.root)
    def test_external_manifest_path_is_rejected(self):
        manifest=self.fixture();manifest['files']['../outside']='0'*64;(self.root/'bundle-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):b.verify_bundle(self.root)
    @unittest.skipUnless(sys.platform=='linux','symlink creation requires Linux fixture')
    def test_symlink_payload_is_rejected(self):
        self.fixture();(self.root/'file').unlink();(self.root/'file').symlink_to(self.root/'bundle-manifest.json')
        with self.assertRaisesRegex(ValueError,'links'):b.verify_bundle(self.root)
    def test_immutable_reinstall_matches_and_foreign_changes_are_preserved(self):
        source=self.root/'source';source.mkdir();(source/'a').write_bytes(b'one')
        target=self.root/'target';b.copy_immutable(source,target);b.copy_immutable(source,target)
        (target/'a').write_bytes(b'other')
        with self.assertRaisesRegex(ValueError,'differs'):b.copy_immutable(source,target)
        self.assertEqual((target/'a').read_bytes(),b'other')
    @unittest.skipUnless(sys.platform=='linux','loginctl contract requires Linux fixture')
    def test_boot_policy_without_terminal_consent_refuses_all_linger_changes(self):
        with patch.object(b.subprocess,'check_output',return_value='no\n'),patch('builtins.open',side_effect=OSError('no terminal')),patch.object(b.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'explicit lingering consent'):b.boot_startup(False)
            run.assert_not_called()
    @unittest.skipUnless(sys.platform=='linux','loginctl contract requires Linux fixture')
    def test_login_only_and_existing_boot_policy_need_no_changes(self):
        with patch.object(b.subprocess,'check_output',return_value='no\n'),patch.object(b.subprocess,'run') as run:
            self.assertEqual(b.boot_startup(True),'after-user-login');run.assert_not_called()
        with patch.object(b.subprocess,'check_output',return_value='yes\n'),patch.object(b.subprocess,'run') as run:
            self.assertEqual(b.boot_startup(False),'boot-existing-or-explicitly-approved-linger');run.assert_not_called()
