"""One shared high-level inference extension, with optional Linux CPU engines."""
# SPDX-License-Identifier: MIT
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import re
import stat
import time
from ..api import ExtensionError,arguments,bounded_json
from . import backends

NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}')
SHA=re.compile(r'[a-f0-9]{64}')

def positive(value,maximum,label):
    if type(value) is not int or not 1<=value<=maximum:raise ExtensionError('configuration',label+' is outside its supported bound')
    return value

class Extension:
    def __init__(self,settings,context):
        if set(settings)-{'demo_models','model_dir','models','max_model_bytes','max_elements','threads'}:raise ExtensionError('configuration','Unknown inference setting')
        self.maximum=positive(settings.get('max_elements',256),1024,'Tensor element limit')
        self.max_bytes=positive(settings.get('max_model_bytes',32*1024*1024),64*1024*1024,'Model byte limit')
        self.threads=positive(settings.get('threads',1),4,'CPU thread count')
        demo=settings.get('demo_models',False)
        if type(demo) is not bool:raise ExtensionError('configuration','demo_models must be boolean')
        if demo:
            if 'models' in settings or 'model_dir' in settings:raise ExtensionError('configuration','Choose bundled demo models or an explicit trusted catalog')
            self.directory=Path(__file__).with_name('models');catalog=json.loads((self.directory/'catalog.json').read_text(encoding='utf-8'))
            self.models=catalog['models']
        else:self.directory=Path(settings['model_dir']) if settings.get('model_dir') else None;self.models=settings.get('models',{})
        if self.directory is not None and (not self.directory.is_absolute() or self.directory.resolve()!=self.directory or not self.directory.is_dir()):raise ExtensionError('configuration','Use an existing canonical absolute model directory without symlinks')
        if not isinstance(self.models,dict) or len(self.models)>32 or any(not isinstance(n,str) or not NAME.fullmatch(n) for n in self.models):raise ExtensionError('configuration','Configure at most32 named trusted models')
        bounded_json(self.models,32768)
        self.loaded=None;self.session=None;self.last_us=None
        self.operations={'backends':self.backend_list,'models':self.model_list,'load':self.load,'infer':self.infer,'info':self.info,'unload':self.unload}
    def backend_list(self,args):
        arguments(args,())
        return {'backends':backends.availability(),'provider':'CPU','runtime_family':'linux',
                'cpu_architecture':platform.machine(),'python':platform.python_version(),
                'libc':list(platform.libc_ver()),'npu_validated':False}
    def model_list(self,args):
        arguments(args,())
        return {'models':[{'id':name,'backends':sorted(value.get('variants',{}))} for name,value in self.models.items()]}
    def descriptor(self,value,label):
        if not isinstance(value,dict) or set(value)!={'shape','dtype'} or value.get('dtype')!='float32' or not isinstance(value.get('shape'),list):raise ExtensionError('model_metadata',label+' must declare a fixed float32 tensor')
        result=backends.tensor(value['shape'],value['dtype'],label)
        if result['elements']>self.maximum:raise ExtensionError('model_limit',label+' exceeds the configured element limit')
        return result
    def bytes(self,filename,digest):
        if self.directory is None or not isinstance(filename,str) or not NAME.fullmatch(filename) or not isinstance(digest,str) or not SHA.fullmatch(digest):raise ExtensionError('model_metadata','A simple local filename and exact SHA256 are required')
        path=self.directory/filename
        try:fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        except OSError:raise ExtensionError('model_missing','Configured model file is missing, linked or unavailable') from None
        try:
            meta=os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or not 1<=meta.st_size<=self.max_bytes:raise ExtensionError('model_limit','Model file is not regular or exceeds its byte bound')
            with os.fdopen(fd,'rb',closefd=False) as source:raw=source.read(self.max_bytes+1)
            if len(raw)!=meta.st_size or hashlib.sha256(raw).hexdigest()!=digest:raise ExtensionError('model_integrity','Model bytes differ from the configured SHA256; previous model retained')
            return raw
        finally:os.close(fd)
    def load(self,args):
        arguments(args,{'model','backend'},{'model','backend'})
        model=args['model'];backend=args['backend']
        if not isinstance(backend,str) or backend not in backends.PACKAGES:raise ExtensionError('backend_unknown','Choose litert or onnx; no automatic backend fallback')
        if not isinstance(model,str) or model not in self.models:raise ExtensionError('model_unknown','Choose a model ID from the configured catalog')
        entry=self.models[model]
        if not isinstance(entry,dict) or not isinstance(entry.get('variants'),dict):raise ExtensionError('model_metadata','Invalid configured model entry')
        variant=entry['variants'].get(backend)
        if not isinstance(variant,dict) or set(variant)!={'file','format','sha256'} or variant['format']!=backends.PACKAGES[backend][2]:raise ExtensionError('model_format','This model has no matching verified artifact for the selected backend')
        expected_in=self.descriptor(entry.get('input'),'input');expected_out=self.descriptor(entry.get('output'),'output')
        raw=self.bytes(variant['file'],variant['sha256']);start=time.perf_counter_ns()
        candidate=backends.create(backend,raw,self.threads,self.maximum)
        for actual,expected in [(candidate.input,expected_in),(candidate.output,expected_out)]:
            if actual['shape']!=expected['shape'] or actual['dtype']!=expected['dtype']:raise ExtensionError('model_metadata','Actual engine tensor metadata differs from the configured model contract')
        try:candidate.prepare()
        except Exception:raise ExtensionError('model_rejected','Engine could not allocate the model; verify operators, shapes and memory') from None
        self.session=candidate;self.loaded={'model':model,'backend':backend,'format':variant['format'],'sha256':variant['sha256'],'input':candidate.input,'output':candidate.output,'provider':'CPU','threads':self.threads,'load_us':(time.perf_counter_ns()-start)//1000,'acceleration_validated':False}
        self.last_us=None;return self.loaded
    def info(self,args):
        arguments(args,())
        return {'loaded':self.loaded is not None,'model':self.loaded,'last_infer_us':self.last_us,'timing_scope':'CPU wall time including tensor input/output; not a performance benchmark'}
    def infer(self,args):
        arguments(args,{'values','input_scale','output_scale'},{'values'})
        if self.session is None:raise ExtensionError('model_not_loaded','Load a neural model and backend before inference')
        values=args['values'];input_scale=args.get('input_scale',1);output_scale=args.get('output_scale',1000)
        for value in (input_scale,output_scale):
            if type(value) is not int or not 1<=value<=1000000:raise ExtensionError('tensor_scale','Tensor scales must be integers1..1000000')
        if not isinstance(values,list) or len(values)!=self.session.input['elements'] or any(type(v) not in (int,float) or abs(v)>1e30 or not math.isfinite(v) for v in values):raise ExtensionError('tensor_input','Provide the exact number of finite flattened numeric input values')
        inputs=[float(v)/input_scale for v in values];start=time.perf_counter_ns()
        try:result=self.session.infer(inputs)
        except Exception:raise ExtensionError('inference_failed','CPU inference failed; verify the loaded model and its input contract') from None
        self.last_us=(time.perf_counter_ns()-start)//1000
        if list(result.shape)!=self.session.output['shape'] or result.dtype.name!='float32':raise ExtensionError('tensor_output','Engine output tensor differs from its validated contract')
        floats=[float(v) for v in result.reshape(-1)]
        if any(not math.isfinite(v) for v in floats):raise ExtensionError('tensor_output','Engine returned nonfinite output')
        scaled=[round(v*output_scale) for v in floats]
        if any(not -(1<<30)<=v<(1<<30) for v in scaled):raise ExtensionError('tensor_output','Scaled output exceeds SmallVM signed31; choose a smaller output scale')
        return {'model':self.loaded['model'],'backend':self.loaded['backend'],'values':scaled,'output_scale':output_scale,'shape':self.session.output['shape'],'dtype':'float32','infer_us':self.last_us,'provider':'CPU'}
    def unload(self,args):arguments(args,());self.session=None;self.loaded=None;self.last_us=None;return {'loaded':False}
    def close(self):self.unload({})
