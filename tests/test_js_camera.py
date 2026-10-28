"""Actual pinned JS import/compiler and native VM, fictional mediad only."""
# SPDX-License-Identifier: MIT
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from package_js_editor import package

class CameraLibraries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node=os.environ.get('NODE_BINARY') or shutil.which('node');source=Path(os.environ.get('JS_EDITOR_UPSTREAM',ROOT.parent/'microblocks-editor-upstream-20261027'))
        if not node or not (source/'.git').exists():raise unittest.SkipTest('Pinned JS source and Node required')
        cls.temp=tempfile.TemporaryDirectory(prefix='js-camera-');cls.root=Path(cls.temp.name);cls.assets=cls.root/'editor'
        package(source,cls.assets,profile='microduck')
        p=subprocess.run([node,str(ROOT/'tests/js-camera-libraries.test.cjs'),str(cls.assets)],capture_output=True,text=True,timeout=45)
        if p.returncode:raise AssertionError(p.stdout+p.stderr)
        cls.compiled=json.loads(p.stdout)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_optional_bundle_preserves_other_imports_and_coexisting_layers(self):
        self.assertEqual(self.compiled['modules'],12);self.assertTrue(self.compiled['roundtrip'])
        self.assertEqual(len(self.compiled['functions']),227)
        self.assertEqual(len(json.loads((self.assets/'microduck-libraries.json').read_text())['sources']),6)
        self.assertEqual(len(json.loads((self.assets/'microduck-starter-libraries.json').read_text())['sources']),10)
        catalog=json.loads((self.assets/'readback-libraries.json').read_text())
        self.assertIn('MicroDuck Camera',catalog['modules']);self.assertIn('MicroDuck Simple Camera',catalog['modules'])
        self.assertFalse(json.loads((self.assets/'target-profile.json').read_text())['connection_enabled'])


@unittest.skipUnless(sys.platform=='linux' and os.environ.get('SMALLVM_MICRODUCK_BINARY'),'Verified local VM required')
class CameraCompiledNative(CameraLibraries,unittest.IsolatedAsyncioTestCase):
    async def test_actual_compiled_simple_and_advanced_blocks_share_frame_api(self):
        def helper(name,file):
            s=importlib.util.spec_from_file_location(name,ROOT/'tests'/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
        camera=helper('js_camera_wire','test_linux_microduck_camera_service.py');vm=helper('js_camera_vm','test_linux_microduck_vm.py')
        work=self.root/'execution';work.mkdir(mode=0o700);data=work/'program';data.mkdir(mode=0o700)
        wire=await camera.CameraWire(work/'media.sock').start()
        service=await camera.gateway.Gateway({},camera=camera.source(wire.path)).start(work/'gateway.sock')
        runtime=await asyncio.to_thread(vm.Runtime,Path(os.environ['SMALLVM_MICRODUCK_BINARY']),data,service.path)
        async def execute(name):
            code=bytes(self.compiled['probes'][name]);code+=bytes(-len(code)%4)
            return await asyncio.to_thread(runtime.execute,code,None,250)
        try:
            for f in self.compiled['functions']:
                code=bytes(f['bytes']);code+=bytes(-len(code)%4);await asyncio.to_thread(runtime.wire.upload,f['id'],code,3)
            for name,expected in [('simpleZero',0),('simpleMax',255),('outOfRange','out_of_range'),('invalid','error'),('advanced',30),('timestamp',str(2**128-1))]:
                before=len(wire.audit);self.assertEqual(await execute(name),expected,name)
                self.assertEqual(len(wire.audit)-before,0 if name=='invalid' else 2,name)
                self.assertFalse(service.camera.entries,name)
            saved=service.camera;service.camera=None
            try:self.assertEqual(await execute('unavailable'),'error')
            finally:service.camera=saved
            self.assertTrue(all(q['method'] in ('hello','media.frame') for q in wire.audit))
        finally:
            await asyncio.to_thread(runtime.stop);await service.stop();await wire.stop()
        self.assertEqual(runtime.process.returncode,0);log=runtime.log_path.read_text()
        self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log)
