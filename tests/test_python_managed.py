"""Managed application automatically owns Python, including private shutdown."""
# SPDX-License-Identifier: MIT
import asyncio
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'linux/arm64'))
from python_runtime import ManagedPython,inside


@unittest.skipUnless(platform.system()=='Linux','requires Linux private service APIs')
class ManagedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='py-managed-');self.root=Path(self.tmp.name)
        (self.root/'profile.json').write_text(json.dumps({'schema':1,'board':'linux-test','extensions':{'sqlite':{'factory':'linux.extensions.plugins.sqlite:Extension'}}}))
        (self.root/'profile.json').chmod(0o600)
        self.config={'python_extensions':{'profile':'profile.json','state':'python','interpreter':sys.executable}}
    async def asyncTearDown(self):self.tmp.cleanup()
    async def test_domain_sql_service_is_owned_by_application_context(self):
        owner=ManagedPython(self.root,self.config)
        async with owner as path:
            self.assertEqual(path,str(self.root/'python/python.sock'))
            reader,writer=await asyncio.open_unix_connection(path)
            writer.write(json.dumps({'jsonrpc':'2.0','id':1,'method':'extensions.call','params':{'extension':'sqlite','method':'query','args':{'sql':'SELECT ?','parameters':[42]}}}).encode()+b'\n');await writer.drain()
            result=json.loads(await reader.readline());writer.close();await writer.wait_closed()
            self.assertEqual(result['result']['value']['rows'],[[42]])
        self.assertFalse(Path(path).exists());self.assertEqual(owner.process.returncode,0)
    async def test_disabled_application_preserves_original_runtime(self):
        owner=ManagedPython(self.root,{})
        async with owner as path:self.assertIsNone(path);self.assertIsNone(owner.process)
    async def test_cancelled_startup_retains_and_stops_its_owned_child(self):
        owner=ManagedPython(self.root,self.config);starting=asyncio.create_task(owner.__aenter__())
        while owner.process is None:await asyncio.sleep(0)
        starting.cancel()
        with self.assertRaises(asyncio.CancelledError):await starting
        self.assertIsNotNone(owner.process.returncode)
    async def test_paths_and_existing_microduck_gateway_are_preserved(self):
        for name in ['../outside','/tmp/outside','']:
            with self.assertRaises(ValueError):inside(self.root,name)
        config={**self.config,'microduck_socket':'/private/existing.sock'}
        with self.assertRaisesRegex(ValueError,'Preserve the existing'):await ManagedPython(self.root,config).__aenter__()


if __name__=='__main__':unittest.main()
