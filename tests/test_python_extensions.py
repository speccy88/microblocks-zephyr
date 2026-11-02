"""Real Linux Python worker, SQLite and private Unix service tests."""
# SPDX-License-Identifier: MIT
import asyncio
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from linux.extensions.api import Context,ExtensionError,bounded_json
if platform.system()=='Linux':
    from linux.extensions.service import Service,configuration
    from linux.extensions.plugins.sqlite import Extension as SQLite


class PortableContract(unittest.TestCase):
    def test_json_refuses_nonfinite_or_unbounded_values(self):
        for value in [float('nan'),{'bad':object()},'x'*70000]:
            with self.assertRaises(ExtensionError):bounded_json(value)


@unittest.skipUnless(platform.system()=='Linux','requires Linux private file/socket/process APIs')
class SQLiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='python-sql-');self.state=Path(self.tmp.name)
        self.db=SQLite({'max_rows':2,'max_cell_bytes':64},Context(self.state,'linux-test'))
        self.db.execute({'sql':'CREATE TABLE readings(label TEXT,value INTEGER)'})

    def tearDown(self):self.db.close();self.tmp.cleanup()

    def test_parameters_quotes_sql_text_and_persistence(self):
        value="x'); DROP TABLE readings; --"
        self.db.execute({'sql':'INSERT INTO readings VALUES (?,?)','parameters':[value,42]})
        self.assertEqual(self.db.execute({'sql':'SELECT * FROM readings'})['rows'],[(value,42)])
        self.db.close();self.db=SQLite({},Context(self.state,'linux-test'))
        self.assertEqual(self.db.execute({'sql':'SELECT COUNT(*) FROM readings'})['rows'],[(1,)])

    def test_row_limit_is_explicit_and_null_zero_false_survive(self):
        for i in range(3):self.db.execute({'sql':'INSERT INTO readings VALUES (?,?)','parameters':[str(i),i]})
        result=self.db.execute({'sql':'SELECT * FROM readings ORDER BY value'})
        self.assertTrue(result['truncated']);self.assertEqual(len(result['rows']),2)
        self.assertEqual(self.db.execute({'sql':'SELECT NULL,0,0.5'})['rows'],[(None,0,.5)])

    def test_files_extensions_transactions_and_multiple_statements_rejected(self):
        for sql in ["ATTACH DATABASE '/tmp/no-extension-access.db' AS other",'PRAGMA journal_mode','BEGIN','COMMIT','SELECT 1; SELECT 2',"SELECT load_extension('unknown')"]:
            with self.assertRaises(ExtensionError):self.db.execute({'sql':sql})
        self.assertEqual(self.db.execute({'sql':'SELECT COUNT(*) FROM readings'})['rows'],[(0,)])

    def test_large_cell_rolls_back_and_expensive_sql_is_interrupted(self):
        with self.assertRaises(ExtensionError):self.db.execute({'sql':'INSERT INTO readings VALUES (?,1) RETURNING label','parameters':['x'*65]})
        self.assertEqual(self.db.execute({'sql':'SELECT COUNT(*) FROM readings'})['rows'],[(0,)])
        started=time.monotonic()
        with self.assertRaises(ExtensionError):self.db.execute({'sql':'WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT SUM(x) FROM n'})
        self.assertLess(time.monotonic()-started,2)
        with self.assertRaises(ExtensionError):self.db.execute({'sql':'SELECT zeroblob(1000000000)'})


@unittest.skipUnless(platform.system()=='Linux','requires Linux private file/socket/process APIs')
class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='python-ext-');self.state=Path(self.tmp.name)
        config={'schema':1,'board':'linux-test','extensions':{
            'sqlite':{'factory':'linux.extensions.plugins.sqlite:Extension','settings':{},'timeout':2},
            'fixture':{'factory':'linux.extensions.examples.test_fixture:Extension','settings':{},'timeout':.4},
            'missing':{'factory':'absent_official_dependency:Extension','settings':{},'timeout':1}}}
        self.service=await Service(config,self.state).start();self.number=0

    async def asyncTearDown(self):await self.service.close();self.tmp.cleanup()

    async def call(self,extension,method,args=None):
        self.number+=1
        reader,writer=await asyncio.open_unix_connection(str(self.service.path))
        request={'jsonrpc':'2.0','id':self.number,'method':'extensions.call','params':{'extension':extension,'method':method,'args':args or {}}}
        try:
            writer.write(bounded_json(request)+b'\n');await writer.drain()
            result=json.loads(await asyncio.wait_for(reader.readline(),4))
            return result['result']
        finally:writer.close();await writer.wait_closed()

    async def test_real_sql_worker_and_actionable_missing_extension(self):
        r=await self.call('sqlite','query',{'sql':'SELECT ? AS answer','parameters':[42]})
        self.assertEqual(r['value']['rows'],[[42]])
        r=await self.call('missing','read');self.assertEqual(r['error']['code'],'dependency_missing')
        r=await self.call('unconfigured','anything');self.assertEqual(r['error']['code'],'extension_missing')
        r=await self.call('sqlite','unknown');self.assertEqual(r['error']['code'],'operation_missing')

    async def test_blocked_worker_is_killed_without_blocking_another_extension(self):
        first=asyncio.create_task(self.call('fixture','delay',{'seconds':3}))
        await asyncio.sleep(.1)
        started=time.monotonic();r=await self.call('sqlite','query',{'sql':'SELECT 42'})
        self.assertTrue(r['ok']);self.assertLess(time.monotonic()-started,.7)
        result=await first;self.assertEqual(result['error']['code'],'timeout');self.assertEqual(result['error']['outcome'],'unknown')
        self.assertTrue((await self.call('fixture','echo',{'next':42}))['ok'])

    async def test_crash_recovery_and_same_worker_admission(self):
        self.assertFalse((await self.call('fixture','crash'))['ok'])
        pending=asyncio.create_task(self.call('fixture','delay',{'seconds':.2}))
        await asyncio.sleep(.03)
        r=await self.call('fixture','echo');self.assertEqual(r['error']['code'],'busy')
        self.assertTrue((await pending)['ok'])
        self.assertTrue((await self.call('fixture','echo',{'value':42}))['ok'])

    async def test_shutdown_cancels_pending_clients_and_owned_workers(self):
        self.service.workers['fixture'].entry['timeout']=8
        pending=asyncio.create_task(self.call('fixture','delay',{'seconds':7}))
        while not self.service.workers['fixture'].busy:await asyncio.sleep(.01)
        started=time.monotonic();await asyncio.wait_for(self.service.close(),2)
        self.assertLess(time.monotonic()-started,2)
        await asyncio.gather(pending,return_exceptions=True)
        self.assertFalse(self.service.clients);self.assertIsNone(self.service.workers['fixture'].process)


if __name__=='__main__':unittest.main()
