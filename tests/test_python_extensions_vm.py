"""Real SmallVM and Python/SQLite, with genuine JS-compiled domain blocks."""
# SPDX-License-Identifier: MPL-2.0
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import struct
import sys
import tempfile
import threading
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BINARY=os.environ.get('SMALLVM_PYTHON_BINARY')
COMPILED=os.environ.get('SMALLVM_PYTHON_COMPILED')
if platform.system()=='Linux':
    from linux.extensions.service import Service
    spec=importlib.util.spec_from_file_location('python_vm_tools',ROOT/'tests/test_linux_microduck_vm.py')
    support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)


@unittest.skipUnless(platform.system()=='Linux' and BINARY and COMPILED,'requires actual Linux VM and genuine JS compilation reports')
class PythonNative(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='py-vm-');self.root=Path(self.temp.name)
        state=self.root/'python';state.mkdir(mode=0o700)
        config={'schema':1,'board':'linux-test','extensions':{
            'sqlite':{'factory':'linux.extensions.plugins.sqlite:Extension','settings':{},'timeout':2},
            'fixture':{'factory':'linux.extensions.examples.test_fixture:Extension','settings':{},'timeout':2}}}
        self.loop=asyncio.new_event_loop();self.thread=threading.Thread(target=self.loop.run_forever);self.thread.start()
        self.service=Service(config,state);asyncio.run_coroutine_threadsafe(self.service.start(),self.loop).result(5)
        data=self.root/'vm';data.mkdir(mode=0o700)
        self.runtime=support.Runtime(Path(BINARY),data,self.service.path);self.vm=self.runtime.wire
        self.compiled=json.loads(Path(COMPILED).read_text())

    def tearDown(self):
        self.runtime.stop()
        log=(self.root/'vm/runtime.log').read_text()
        self.assertFalse(any(s in log for s in ['AddressSanitizer','runtime error:','LeakSanitizer']),log)
        asyncio.run_coroutine_threadsafe(self.service.close(),self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(5);self.loop.close();self.temp.cleanup()

    def primitive(self,name,args=(),error=None):return self.runtime.execute(support.Program().call(name,args,prim_set=3).finish(),error=error,chunk=250)

    def upload_example(self):
        for chunk in self.compiled['chunks']:
            data=bytes(chunk['bytes']);data+=b'\0'*(-len(data)%4)
            self.vm.upload(chunk['id'],data,chunk['kind'])

    def variable(self,name):
        index=self.compiled['variables'][name];start=len(self.vm.events);self.vm.short(7,index)
        value=self.vm.wait(lambda e:e[:2]==(21,index),start)[2]
        if value[0]==1:return struct.unpack('<i',value[1:5])[0]
        if value[0]==3:return bool(value[1])
        return value

    def until(self,condition,seconds=5):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if condition():return
            self.vm.pump(.01)
        self.fail('Expected real VM state did not arrive')

    def test_visible_domain_example_sql_rows_parameters_and_persistence(self):
        self.upload_example();started=len(self.vm.events);self.vm.short(5,1)
        self.until(lambda:self.variable('SQLCount')==1)
        self.assertGreater(self.variable('Heartbeat'),0)
        self.assertEqual(self.variable('SQLRows')[0],4) # actual VM list, not JSON text
        self.vm.wait(lambda e:e[:2]==(17,self.compiled['script_ids'][0]),started)
        self.vm.short(3,self.compiled['script_ids'][0]);self.until(lambda:self.variable('SQLCount')==2)
        database=self.root/'python/programs.sqlite3'
        self.assertTrue(database.is_file())
        import sqlite3
        with sqlite3.connect(database) as con:self.assertEqual(con.execute('SELECT label,value FROM readings ORDER BY rowid').fetchall(),[('room',21500),('room',21500)])

    def test_real_typed_json_arrays_large_values_and_blank_sql_parameters(self):
        self.upload_example()
        expected=[21500,'9223372036854775807','null','["quote\'text",0,false]',42]
        for id,value in zip(self.compiled['script_ids'][2:],expected):
            chunk=next(c for c in self.compiled['chunks'] if c['id']==id)
            data=bytes(chunk['bytes']);data+=b'\0'*(-len(data)%4)
            self.assertEqual(self.runtime.execute(data,chunk=id),value)
        self.assertEqual(self.primitive('pythonGet',['{"zero":0,"false":false}','/zero']),0)
        self.assertIs(self.primitive('pythonGet',['{"zero":0,"false":false}','/false']),False)
        for _ in range(50):self.assertEqual(self.primitive('pythonGet',['{"v":[[1,2],false,null]}','/v/0/1']),2)

    def test_nested_list_conversion_survives_real_moving_collection(self):
        fill=support.Program().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0).finish()
        self.assertEqual(self.runtime.execute(fill,chunk=249),0)
        started=len(self.vm.events)
        program=support.Program().call('pythonGet',['{"v":[[1,2,3],[4,5,6],[7,8,9]]}','/v'],prim_set=3)
        program.op(37,1);program.fixups.append((len(program.code),'pythonJSON',3<<10));program.code+=b'\0\0'
        self.assertEqual(self.runtime.execute(program.finish(),chunk=250),'[[1,2,3],[4,5,6],[7,8,9]]')
        self.assertTrue(any(kind==20 and b'GC took' in body for kind,index,body in self.vm.events[started:]),'collection must actually occur during conversion')

    def test_nonblocking_native_job_ping_and_independent_task(self):
        self.upload_example();heartbeat=self.compiled['script_ids'][1];self.vm.short(3,heartbeat)
        job=self.primitive('pythonBegin',['fixture','delay','{"seconds":0.7,"value":42}'])
        before=self.variable('Heartbeat');started=time.monotonic()
        self.assertEqual(self.primitive('pythonStatus',[job]),'pending')
        for _ in range(5):self.vm.ping();self.vm.pump(.02)
        self.assertGreater(self.variable('Heartbeat'),before)
        self.until(lambda:self.primitive('pythonStatus',[job])!='pending')
        reply=json.loads(self.primitive('pythonResult',[job]))
        self.assertEqual(reply['result'],{'ok':True,'value':42});self.assertLess(time.monotonic()-started,2)
        self.primitive('pythonRelease',[job])
        self.primitive('pythonBegin',['sqlite','unknown','[]'],error=32)


if __name__=='__main__':unittest.main()
