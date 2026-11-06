"""Controller fixtures are separate from required real optional-engine tests."""
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from linux.extensions.api import Context,ExtensionError
from linux.extensions.inference.extension import Extension
from linux.extensions.inference import backends

def engines_present():return all(importlib.util.find_spec(name) is not None for name in ['numpy','onnx','onnxruntime','ai_edge_litert'])
CATALOG=ROOT/'linux/extensions/inference/models/catalog.json'

class Array:
    shape=[1,3];dtype=SimpleNamespace(name='float32')
    def reshape(self,_):return [2.95,-2.225,6.8125]
class Session:
    input={'name':'fixture','shape':[1,4],'dtype':'float32','elements':4}
    output={'name':'fixture','shape':[1,3],'dtype':'float32','elements':3}
    def prepare(self):pass
    def infer(self,values):return Array()

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.catalog=json.loads(CATALOG.read_text(encoding='utf-8'))
        self.models=copy.deepcopy(self.catalog['models']);self.fixture=b'owned controller fixture'
        for variant in self.models['tiny-dense-v1']['variants'].values():
            (self.root/variant['file']).write_bytes(self.fixture);variant['sha256']=hashlib.sha256(self.fixture).hexdigest()
        self.extension=Extension({'models':self.models,'model_dir':str(self.root)},Context(self.root,'linux-test'))
    def tearDown(self):self.extension.close();self.tmp.cleanup()
    def load(self):
        with patch.object(backends,'create',return_value=Session()):return self.extension.load({'model':'tiny-dense-v1','backend':'onnx'})
    def test_load_scaled_prediction_unload_and_explicit_no_model(self):
        self.load();self.assertEqual(self.extension.infer({'values':[1000,2000,3000,4000],'input_scale':1000,'output_scale':1000})['values'],[2950,-2225,6812])
        self.assertTrue(self.extension.info({})['loaded']);self.extension.unload({})
        with self.assertRaises(ExtensionError) as failed:self.extension.infer({'values':[1,2,3,4]})
        self.assertEqual(failed.exception.code,'model_not_loaded')
    def test_bad_integrity_and_failed_replacement_keep_prior_session(self):
        self.load();previous=self.extension.session
        (self.root/'tiny-dense.onnx').write_bytes(b'changed')
        with self.assertRaises(ExtensionError) as failed:self.load()
        self.assertEqual(failed.exception.code,'model_integrity');self.assertIs(self.extension.session,previous)
        self.assertEqual(self.extension.infer({'values':[1,2,3,4]})['values'],[2950,-2225,6812])
    def test_model_names_formats_paths_and_shape_bounds_are_explicit(self):
        for args in [{'model':'../outside','backend':'onnx'},{'model':'tiny-dense-v1','backend':['onnx']},{'model':'tiny-dense-v1','backend':'gpu'}]:
            with self.assertRaises(ExtensionError):self.extension.load(args)
        for shape in [[True,4],[0,4],[-1,4],[1,257],['batch',4]]:
            self.extension.models['tiny-dense-v1']['input']['shape']=shape
            with self.assertRaises(ExtensionError):self.load()
        self.extension.models['tiny-dense-v1']['input']['shape']=[1,4]
        self.extension.models['tiny-dense-v1']['variants']['onnx']['file']='../outside.onnx'
        with self.assertRaises(ExtensionError):self.load()
    def test_input_count_type_nonfinite_and_scales_rejected_without_execution(self):
        self.load()
        for values in [[1],['1',2,3,4],[True,2,3,4],[float('nan'),2,3,4],[10**1000,2,3,4]]:
            with self.assertRaises(ExtensionError):self.extension.infer({'values':values})
        for scale in [0,True,1.5,1000001]:
            with self.assertRaises(ExtensionError):self.extension.infer({'values':[1,2,3,4],'input_scale':scale})
    def test_empty_catalog_and_missing_dependency_are_queryable(self):
        empty=Extension({},Context(self.root,'linux-test'));self.assertEqual(empty.model_list({}),{'models':[]})
        with patch.object(backends.importlib.util,'find_spec',return_value=None):
            values=empty.backend_list({})['backends'];self.assertTrue(all(not x['installed'] for x in values));self.assertEqual({x['backend'] for x in values},{'litert','onnx'})
        with patch.object(backends,'Onnx',side_effect=ModuleNotFoundError('optional fixture')):
            with self.assertRaises(ExtensionError) as failed:self.extension.load({'model':'tiny-dense-v1','backend':'onnx'})
        self.assertEqual(failed.exception.code,'dependency_missing')
    def test_metadata_mismatch_does_not_replace_loaded_session(self):
        self.load();previous=self.extension.session;wrong=Session();wrong.output={**wrong.output,'shape':[1,4]}
        with patch.object(backends,'create',return_value=wrong),self.assertRaises(ExtensionError) as failed:self.extension.load({'model':'tiny-dense-v1','backend':'litert'})
        self.assertEqual(failed.exception.code,'model_metadata');self.assertIs(self.extension.session,previous)

@unittest.skipUnless(engines_present(),'Optional real LiteRT and ONNX Runtime CPU requirements')
class RealEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.catalog=json.loads(CATALOG.read_text(encoding='utf-8'))
        self.extension=Extension({'demo_models':True},Context(self.root,'linux-test'))
    def tearDown(self):self.extension.close();self.tmp.cleanup()
    def test_both_real_cpu_engines_match_authored_pytorch_outputs(self):
        import numpy as np
        for backend in ['litert','onnx']:
            with self.subTest(backend=backend):
                metadata=self.extension.load({'model':'tiny-dense-v1','backend':backend});self.assertEqual(metadata['provider'],'CPU');self.assertFalse(metadata['acceleration_validated'])
                actual=self.extension.session.infer(self.catalog['fixture']['input']).reshape(-1)
                np.testing.assert_allclose(actual,self.catalog['fixture']['expected_float32'],rtol=0,atol=self.catalog['fixture']['absolute_tolerance'])
                result=self.extension.infer({'values':self.catalog['fixture']['scaled_input'],'input_scale':1000,'output_scale':1000})
                self.assertTrue(all(abs(a-b)<=1 for a,b in zip(result['values'],self.catalog['fixture']['expected_scaled'])))
                self.assertGreaterEqual(result['infer_us'],0);self.extension.unload({})
    def test_actual_engines_reject_mismatched_contract_and_overflow(self):
        for backend in ['litert','onnx']:
            self.extension.load({'model':'tiny-dense-v1','backend':backend})
            with self.assertRaises(ExtensionError) as failed:self.extension.infer({'values':[1e30]*4,'output_scale':1000000})
            self.assertEqual(failed.exception.code,'tensor_output')
        self.extension.models=copy.deepcopy(self.extension.models);self.extension.models['tiny-dense-v1']['input']['shape']=[1,5]
        with self.assertRaises(ExtensionError) as failed:self.extension.load({'model':'tiny-dense-v1','backend':'onnx'})
        self.assertEqual(failed.exception.code,'model_metadata')
    def test_actual_onnx_external_data_is_refused_before_native_load(self):
        import onnx
        from onnx import helper,TensorProto
        tensor=TensorProto();tensor.name='external';tensor.data_type=TensorProto.FLOAT;tensor.dims.append(1);tensor.data_location=TensorProto.EXTERNAL
        tensor.external_data.add(key='location',value='../../unrelated-private-file')
        graph=helper.make_graph([helper.make_node('Add',['features','external'],['scores'])],'external-test',[helper.make_tensor_value_info('features',TensorProto.FLOAT,[1,4])],[helper.make_tensor_value_info('scores',TensorProto.FLOAT,[1,4])],[tensor])
        raw=helper.make_model(graph).SerializeToString()
        with self.assertRaises(ExtensionError) as failed:backends.create('onnx',raw,1,256)
        self.assertEqual(failed.exception.code,'model_external_data')
    def test_actual_invalid_artifacts_and_dynamic_shapes_fail_clearly(self):
        for backend in ['onnx','litert']:
            with self.assertRaises(ExtensionError):backends.create(backend,b'not a valid model',1,256)
        from onnx import helper,TensorProto
        graph=helper.make_graph([helper.make_node('Identity',['features'],['scores'])],'dynamic',[helper.make_tensor_value_info('features',TensorProto.FLOAT,['batch',4])],[helper.make_tensor_value_info('scores',TensorProto.FLOAT,['batch',4])])
        model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',18)]);model.ir_version=10
        with self.assertRaises(ExtensionError) as failed:backends.create('onnx',model.SerializeToString(),1,256)
        self.assertEqual(failed.exception.code,'tensor_shape')
    def test_real_model_receipts_and_cpu_availability(self):
        self.assertEqual(hashlib.sha256((ROOT/self.catalog['source']).read_bytes()).hexdigest(),self.catalog['source_sha256'])
        for entry in self.catalog['models']['tiny-dense-v1']['variants'].values():self.assertEqual(hashlib.sha256((CATALOG.parent/entry['file']).read_bytes()).hexdigest(),entry['sha256'])
        self.assertTrue(all(x['installed'] and x['provider']=='CPU' for x in self.extension.backend_list({})['backends']))

@unittest.skipUnless(sys.platform=='linux' and engines_present(),'Linux real optional-engine worker lifecycle')
class WorkerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from linux.extensions.service import Service
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.number=0
        config={'schema':1,'board':'linux-test','extensions':{'inference':{'factory':'linux.extensions.inference.extension:Extension','settings':{'demo_models':True},'timeout':8},'sqlite':{'factory':'linux.extensions.plugins.sqlite:Extension','timeout':2}}}
        self.service=await Service(config,self.root).start()
    async def asyncTearDown(self):await self.service.close();self.tmp.cleanup()
    async def call(self,extension,method,args=None):
        self.number+=1;reader,writer=await asyncio.open_unix_connection(self.service.path)
        try:
            writer.write(json.dumps({'jsonrpc':'2.0','id':self.number,'method':'extensions.call','params':{'extension':extension,'method':method,'args':args or {}}}).encode()+b'\n');await writer.drain()
            return json.loads(await asyncio.wait_for(reader.readline(),10))['result']
        finally:writer.close();await writer.wait_closed()
    async def test_real_cpu_worker_switch_load_infer_and_unload(self):
        for backend in ['litert','onnx']:
            self.assertTrue((await self.call('inference','load',{'model':'tiny-dense-v1','backend':backend}))['ok'])
            result=await self.call('inference','infer',{'values':[1000,2000,3000,4000],'input_scale':1000,'output_scale':1000})
            self.assertEqual(result['value']['backend'],backend);self.assertEqual(len(result['value']['values']),3)
            self.assertFalse((await self.call('inference','unload'))['value']['loaded'])
    async def test_paused_owned_native_worker_times_out_without_blocking_sql(self):
        self.assertTrue((await self.call('inference','load',{'model':'tiny-dense-v1','backend':'onnx'}))['ok'])
        # Verify cold worker startup separately from concurrent responsiveness.
        self.assertEqual((await self.call('sqlite','query',{'sql':'SELECT 42'}))['value']['rows'],[[42]])
        worker=self.service.workers['inference'];worker.entry['timeout']=2;paused=worker.process
        os.kill(paused.pid,signal.SIGSTOP) # only this test's owned child
        sent=asyncio.Event();write=paused.stdin.write
        def observe_write(raw):
            write(raw)
            if json.loads(raw).get('method')=='infer':sent.set()
        with patch.object(paused.stdin,'write',side_effect=observe_write):
            pending=asyncio.create_task(self.call('inference','infer',{'values':[1,2,3,4]}))
            try:
                await asyncio.wait_for(sent.wait(),1)
                # Shared runners need headroom, but SQL must finish before the
                # paused worker's two-second timeout can release a global lock.
                result=await asyncio.wait_for(self.call('sqlite','query',{'sql':'SELECT 42'}),1)
                self.assertEqual(result['value']['rows'],[[42]])
                self.assertFalse(pending.done(),'SQL waited for the inference request')
                self.assertIs(worker.process,paused)
                self.assertIsNone(paused.returncode,'SQL completed only after worker termination')
                failure=await pending;self.assertEqual(failure['error']['code'],'timeout')
            finally:
                if not pending.done():pending.cancel()
                await asyncio.gather(pending,return_exceptions=True)
        worker.entry['timeout']=8
        info=await self.call('inference','info');self.assertFalse(info['value']['loaded'])
        failure=await self.call('inference','infer',{'values':[1,2,3,4]});self.assertEqual(failure['error']['code'],'model_not_loaded')

if __name__=='__main__':unittest.main()
