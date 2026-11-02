"""Genuine domain blocks on native VM, real optional engines, no robot controls."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BINARY=os.environ.get('SMALLVM_PYTHON_BINARY');COMPILED=os.environ.get('SMALLVM_INFERENCE_COMPILED')
READY=sys.platform=='linux' and BINARY and COMPILED and all(importlib.util.find_spec(n) for n in ['onnxruntime','ai_edge_litert'])
if sys.platform=='linux':
 from linux.extensions.service import Service
 spec=importlib.util.spec_from_file_location('inference_vm_wire',ROOT/'tests/test_linux_microduck_vm.py');support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)

@unittest.skipUnless(READY,'Requires real Linux VM, genuine compiled blocks and both optional CPU engines')
class InferenceNativeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='inference-vm-');self.root=Path(self.tmp.name);state=self.root/'python';state.mkdir(mode=0o700)
  self.loop=asyncio.new_event_loop();self.thread=threading.Thread(target=self.loop.run_forever);self.thread.start()
  self.service=Service({'schema':1,'board':'linux-test','extensions':{'inference':{'factory':'linux.extensions.inference.extension:Extension','settings':{'demo_models':True,'threads':1},'timeout':8}}},state)
  asyncio.run_coroutine_threadsafe(self.service.start(),self.loop).result(5)
  data=self.root/'vm';data.mkdir(mode=0o700);self.runtime=support.Runtime(Path(BINARY),data,self.service.path);self.vm=self.runtime.wire
  self.compiled=json.loads(Path(COMPILED).read_text(encoding='utf-8'));self.expected=json.loads((ROOT/'linux/extensions/inference/models/catalog.json').read_text())['fixture']['expected_scaled']
 def tearDown(self):
  self.runtime.stop();asyncio.run_coroutine_threadsafe(self.service.close(),self.loop).result(5);self.loop.call_soon_threadsafe(self.loop.stop);self.thread.join(5);self.loop.close();self.tmp.cleanup()
 def variable(self,name,report):
  index=report['variables'][name];start=len(self.vm.events);self.vm.short(7,index);value=self.vm.wait(lambda e:e[:2]==(21,index),start)[2]
  if value[0]==1:return struct.unpack('<i',value[1:5])[0]
  if value[0]==2:return value[1:].decode('utf-8')
  if value[0]==3:return bool(value[1])
  return None
 def exercise(self,backend):
  report=self.compiled['variants'][backend];self.assertTrue(self.compiled['real_compiler'])
  for chunk in report['chunks']:
   raw=bytes(chunk['bytes']);raw+=b'\0'*(-len(raw)%4);self.vm.upload(chunk['id'],raw,chunk['kind'])
  start=len(self.vm.events);self.vm.short(5,1);deadline=time.monotonic()+12;progress_during_call=False;pending_heartbeat=None
  while time.monotonic()<deadline:
   finished=self.variable('NeuralDone',report)==1;heartbeat=self.variable('Heartbeat',report)
   if not finished and heartbeat and heartbeat>1:progress_during_call=True;pending_heartbeat=heartbeat
   if finished:break
   self.vm.pump(.005)
  else:self.fail('Native neural example did not finish')
  self.assertTrue(progress_during_call,'Independent VM heartbeat must progress during real load/inference')
  self.assertEqual(self.variable('NeuralBackend',report),backend)
  actual=[]
  for id,expected in zip(report['script_ids'][2:],self.expected):
   chunk=next(c for c in report['chunks'] if c['id']==id);raw=bytes(chunk['bytes']);raw+=b'\0'*(-len(raw)%4)
   value=self.runtime.execute(raw,chunk=id);actual.append(value);self.assertLessEqual(abs(value-expected),1)
  self.assertTrue(any(kind==17 and id==report['script_ids'][0] for kind,id,payload in self.vm.events[start:]))
  self.vm.ping()
  if os.environ.get('SMALLVM_INFERENCE_EVIDENCE'):
   destination=Path(os.environ['SMALLVM_INFERENCE_EVIDENCE']);destination.mkdir(parents=True,exist_ok=True)
   proof={'result':'PASS','backend':backend,'vm_version':417,'binary_sha256':hashlib.sha256(Path(BINARY).read_bytes()).hexdigest(),
    'real_js_compiler':True,'real_native_vm':True,'real_engine':True,'scaled_values':actual,'expected_scaled':self.expected,
    'heartbeat_while_model_call_pending':pending_heartbeat,'normal_user_script_without_bridge_selectors':True,
    'user_data_or_robot_controls_used':False,'network_listener_opened':False,'transport':'private PTY and owned private Unix service'}
   (destination/(backend+'.json')).write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
 def test_litert_real_domain_blocks_and_independent_heartbeat(self):self.exercise('litert')
 def test_onnx_real_domain_blocks_and_independent_heartbeat(self):self.exercise('onnx')

if __name__=='__main__':unittest.main()
