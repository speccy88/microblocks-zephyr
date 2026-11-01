"""Native editor packaging must preserve ordinary GP assets and source guards."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from linux_editor_assets import unpack_package, package_metadata
from package_p4_ide import patch_p4
from patch_sfc_blocks import patch_package
from package_sfc_native import native_html, CHART_ASSETS, build
from sfc_branch_icons import resources


class NativeSFCAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=ROOT/'build-artifacts/ide-source'
        cls.js=cls.data=None
        if not (source/'gp_wasm.data').is_file():return
        cls.js,cls.data=patch_p4((source/'gp_wasm.js').read_bytes(),(source/'gp_wasm.data').read_bytes(),ROOT)

    def test_only_guarded_editor_sources_change_and_engine_assets_survive(self):
        if self.js is None:self.skipTest('pinned GP editor assets not staged; SFC workflow stages and requires them')
        js,data=patch_package(self.js,self.data,ROOT)
        before=unpack_package(self.js,self.data);after=unpack_package(js,data)
        self.assertEqual(set(after)-set(before),set(resources(ROOT)))
        self.assertFalse(set(before)-set(after))
        changed={Path(k).name for k in before if before[k]!=after[k]}
        self.assertEqual(changed,{'MicroBlocksCompiler.gp','MicroBlocksProject.gp','PrettyPrinter.gp','Block.gp',
                                 'MicroBlocksScripter.gp','MicroBlocksRuntime.gp','zzzMicroBlocksPatches.gp'})
        for name in before:
            if Path(name).name not in changed:self.assertEqual(before[name],after[name])
        for name,raw in resources(ROOT).items():self.assertEqual(after[name],raw)

    def test_double_application_is_rejected_instead_of_duplication(self):
        if self.js is None:self.skipTest('pinned GP editor assets not staged; SFC workflow stages and requires them')
        js,data=patch_package(self.js,self.data,ROOT)
        with self.assertRaises(ValueError):patch_package(js,data,ROOT)

    def test_graph_surface_is_removed_but_connection_stays_disabled(self):
        tags=''.join('<script src="'+n+'?v=1234"></script>' if n.endswith('.js') else
            '<link rel="stylesheet" href="'+n+'?v=1234">' for n in sorted(CHART_ASSETS))
        html=native_html(('<head>'+tags+'</head><script>connection_enabled:false</script>').encode())
        for name in CHART_ASSETS:self.assertNotIn(name.encode(),html)
        self.assertIn(b'connection_enabled:false',html)
        with self.assertRaises(ValueError):native_html(b'<head></head>')

    def test_builder_does_not_overwrite_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as name:
            output=Path(name)/'owned';output.mkdir();keep=output/'draft.ubp';keep.write_text('user draft')
            with self.assertRaisesRegex(ValueError,'new native SFC'):build(Path(name)/'source',output,ROOT)
            self.assertEqual(keep.read_text(),'user draft')


if __name__=='__main__':unittest.main()
