"""Trusted command assets survive checkout EOLs and reject changed inputs."""
# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('voice_assets',ROOT/'bilingual-kws/scripts/prepare_firmware.py')
assets=importlib.util.module_from_spec(spec);spec.loader.exec_module(assets)
MODEL=ROOT/'bilingual-kws/models/voice_commands_int8.tflite'
MANIFEST=json.loads(MODEL.with_suffix('.json').read_text())

class VoiceAssetTests(unittest.TestCase):
    def test_actual_frontend_has_only_checkout_line_ending_differences(self):
        source=(ROOT/'common/kws/features.c').read_bytes().replace(b'\r\n',b'\n')
        assets.verify_frontend(source,MANIFEST['frontend'])
        assets.verify_frontend(source.replace(b'\n',b'\r\n'),MANIFEST['frontend'])
        with self.assertRaises(ValueError):
            assets.verify_frontend(source+b'\n/* changed implementation */',MANIFEST['frontend'])
    def test_missing_canonical_pin_rejects_an_unpinned_frontend(self):
        with self.assertRaises(ValueError):assets.verify_frontend(b'changed',{'adapter_sha256':'0'*64})
    def test_real_selected_model_generates_hash_checked_readonly_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'assets';assets.run(SimpleNamespace(model=MODEL,output=output))
            self.assertEqual((output/'voice_model.bin').read_bytes(),MODEL.read_bytes())
            self.assertIn('.section .rodata.p4_voice',(output/'voice_assets.S').read_text())
            self.assertEqual(hashlib.sha256(MODEL.read_bytes()).hexdigest(),MANIFEST['model_sha256'])
    def test_tampered_model_is_rejected_before_assets_are_created(self):
        with tempfile.TemporaryDirectory() as directory:
            model=Path(directory)/'changed.tflite';data=bytearray(MODEL.read_bytes());data[-1]^=1;model.write_bytes(data)
            model.with_suffix('.json').write_text(json.dumps(MANIFEST));output=Path(directory)/'assets'
            with self.assertRaises(ValueError):assets.run(SimpleNamespace(model=model,output=output))
            self.assertFalse(output.exists())
if __name__=='__main__':unittest.main()
