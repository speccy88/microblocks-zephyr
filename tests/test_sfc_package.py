"""Opt-in authoring package contract; no board or browser control."""
import importlib.util
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from package_sfc_studio import inject,build,offline_adapter

class SFCAssets(unittest.TestCase):
    def test_disconnected_profile_hashes_and_existing_library_are_explicit(self):
        html=b'<html><head><script>window.PORTAL_BOARD={board:"esp32p4",name:"P4"};</script></head><body></body></html>'
        assets=inject({'microblocks.html':html},ROOT)
        text=assets['microblocks.html'].decode()
        self.assertIn('connection_enabled:false',text)
        self.assertIn('hardware connection is disabled',text)
        for name in ['sfc-core.js','sfc-studio.js','sfc-studio.css','sfc-library.js']:
            self.assertIn(name+'?v=',text);self.assertGreater(len(assets[name]),100)
        self.assertEqual(assets['microblocks.html'],assets['index.html'])

    def test_drifted_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'profile anchor'):
            inject({'microblocks.html':b'<head></head>'},ROOT)

    def test_execution_and_export_load_in_dependency_order_with_hashes(self):
        import hashlib
        assets=inject({'microblocks.html':b'<head><script>window.PORTAL_BOARD={board:"esp32p4",name:"P4"};</script></head>'},ROOT)
        html=assets['microblocks.html'].decode()
        names=['sfc-core.js','sfc-execution.js','sfc-export.js','sfc-library.js','sfc-studio.js']
        self.assertEqual(sorted(names,key=html.index),names)
        for name in names:self.assertIn(name+'?v='+hashlib.sha256(assets[name]).hexdigest()[:16],html)
        self.assertIn('connection_enabled:false',html)

    def test_execution_assets_are_repository_bytes_and_no_hardware_endpoint_is_added(self):
        assets=inject({'microblocks.html':b'<head><script>window.PORTAL_BOARD={board:"esp32p4",name:"P4"};</script></head>'},ROOT)
        for name in ['sfc-core.js','sfc-execution.js','sfc-export.js','sfc-studio.js','sfc-actions.css']:
            self.assertEqual(assets[name],(ROOT/'web/sfc'/name).read_bytes())
        self.assertNotIn(b'navigator.serial',assets['sfc-export.js'])

    def test_preview_names_its_actual_scope(self):
        original=b'XRP development preview: the production RP2350 library is available for editing. Hardware connection is not enabled yet.'
        actual=offline_adapter(original)
        self.assertIn(b'SFC authoring preview',actual)
        self.assertNotIn(b'RP2350',actual)
        with self.assertRaises(ValueError):offline_adapter(b'changed')

    def test_existing_unowned_output_and_source_are_preserved(self):
        with tempfile.TemporaryDirectory() as parent:
            parent=Path(parent);source=parent/'source';source.mkdir();output=parent/'out';output.mkdir()
            keep=output/'keep';keep.write_text('mine')
            with self.assertRaisesRegex(ValueError,'owned SFC'):
                build(source,output,ROOT)
            self.assertEqual(keep.read_text(),'mine')
            with self.assertRaisesRegex(ValueError,'separate'):
                build(source,source,ROOT)

if __name__=='__main__':unittest.main()
