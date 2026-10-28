# SPDX-License-Identifier: MPL-2.0
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_js_editor import package


class JSLegacyLoops(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if not node or not (source / '.git').exists():
            raise unittest.SkipTest('Pinned source and Node required')
        cls.temp = tempfile.TemporaryDirectory(prefix='js-legacy-loops-')
        cls.base = Path(cls.temp.name)
        assets = cls.base / 'editor'
        package(source, assets, profile='esp32p4')
        result = subprocess.run([node, str(ROOT / 'tests/js-legacy-loops.test.cjs'), str(assets)], capture_output=True, text=True, timeout=30)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls.report = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_compiler_preserves_source_and_readback_loop_bytes(self):
        self.assertEqual(len(self.report['cases']), 4)
        self.assertTrue(self.report['source_unchanged'])
        self.assertTrue(self.report['readback_recompile_identical'])

    @unittest.skipUnless(sys.platform == 'linux' and os.environ.get('SMALLVM_MICRODUCK_BINARY'), 'Verified local Linux VM required')
    def test_actual_vm_condition_body_nested_and_exit_semantics(self):
        spec = importlib.util.spec_from_file_location('legacy_loops_vm', ROOT / 'tests/test_linux_microduck_vm.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        data = self.base / 'program';data.mkdir(mode=0o700)
        runtime = helper.Runtime(Path(os.environ['SMALLVM_MICRODUCK_BINARY']), data, None)
        try:
            for case in self.report['cases']:
                self.assertEqual(runtime.execute(bytes(case['bytes']), chunk=250), case['expected'], case['name'])
        finally:
            runtime.stop()
        self.assertEqual(runtime.process.returncode, 0, runtime.log_path.read_text())
        print(json.dumps({'legacy_while_actual_local_vm': [c['expected'] for c in self.report['cases']], 'physical_board': False}))
