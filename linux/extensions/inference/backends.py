"""Lazy, explicit CPU adapters; independent artifact formats and no delegates."""
# SPDX-License-Identifier: MIT
import importlib
import importlib.metadata
import importlib.util
import math
from ..api import ExtensionError

PACKAGES={'litert':('ai_edge_litert','ai-edge-litert','tflite'),
          'onnx':('onnxruntime','onnxruntime','onnx')}

def availability():
    results=[]
    for name,(module,package,format) in PACKAGES.items():
        try:installed=importlib.util.find_spec(module) is not None
        except (ImportError,ValueError):installed=False
        try:version=importlib.metadata.version(package) if installed else None
        except importlib.metadata.PackageNotFoundError:version=None
        results.append({'backend':name,'format':format,'installed':installed,'version':version,
                        'provider':'CPU','acceleration_validated':False,
                        'reason':'Load a compatible model to validate this installation' if installed else 'Install optional '+package+' in the configured Python environment'})
    return results

def tensor(shape,dtype,name):
    shape=[int(x) if type(x) is int or type(x).__module__.startswith('numpy') else x for x in shape]
    if not shape or len(shape)>4 or any(type(n) is not int or not 1<=n<=4096 for n in shape):
        raise ExtensionError('tensor_shape','Only fixed positive tensor dimensions are supported')
    if dtype!='float32':raise ExtensionError('tensor_type','This adapter currently requires float32 input and output')
    return {'name':name,'shape':shape,'dtype':dtype,'elements':math.prod(shape)}

class Onnx:
    def __init__(self,raw,threads,maximum):
        import numpy as np
        import onnx
        import onnxruntime as ort
        model=onnx.load_model_from_string(raw)
        # Self-contained protobuf only. Never let a model choose an external
        # tensor path or custom shared library. Parse data before native load.
        pending=[model];count=0
        while pending:
            message=pending.pop();count+=1
            if count>100000:raise ExtensionError('model_limit','ONNX structure exceeds the configured scope')
            if message.DESCRIPTOR.full_name=='onnx.TensorProto' and (message.external_data or message.data_location==1):
                raise ExtensionError('model_external_data','External ONNX tensor files are unsupported; export a self-contained model')
            for field,value in message.ListFields():
                if field.type==field.TYPE_MESSAGE:pending.extend(value if field.is_repeated else [value])
        options=ort.SessionOptions();options.intra_op_num_threads=threads;options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.enable_mem_pattern=False
        if 'CPUExecutionProvider' not in ort.get_available_providers():raise ExtensionError('backend_unavailable','ONNX Runtime CPU provider is unavailable on this platform')
        self.session=ort.InferenceSession(raw,sess_options=options,providers=['CPUExecutionProvider'])
        if self.session.get_providers()!=['CPUExecutionProvider']:raise ExtensionError('backend_unavailable','Unexpected execution provider; only CPU is commissioned')
        inputs=self.session.get_inputs();outputs=self.session.get_outputs()
        if len(inputs)!=1 or len(outputs)!=1:raise ExtensionError('tensor_count','This interface currently requires one input and one output tensor')
        self.input=tensor(inputs[0].shape,'float32' if inputs[0].type=='tensor(float)' else inputs[0].type,inputs[0].name)
        self.output=tensor(outputs[0].shape,'float32' if outputs[0].type=='tensor(float)' else outputs[0].type,outputs[0].name)
        self.np=np
    def prepare(self):pass
    def infer(self,values):
        array=self.np.asarray(values,dtype=self.np.float32).reshape(self.input['shape'])
        return self.session.run([self.output['name']],{self.input['name']:array})[0]

class LiteRT:
    def __init__(self,raw,threads,maximum):
        import numpy as np
        from ai_edge_litert.interpreter import Interpreter,OpResolverType
        if raw[4:8]!=b'TFL3':raise ExtensionError('model_format','Expected a self-contained TFLite model for LiteRT')
        self.session=Interpreter(model_content=raw,num_threads=threads,
            experimental_op_resolver_type=OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES)
        inputs=self.session.get_input_details();outputs=self.session.get_output_details()
        if len(inputs)!=1 or len(outputs)!=1:raise ExtensionError('tensor_count','This interface currently requires one input and one output tensor')
        self.input=tensor(inputs[0]['shape'],np.dtype(inputs[0]['dtype']).name,inputs[0]['name'])
        self.output=tensor(outputs[0]['shape'],np.dtype(outputs[0]['dtype']).name,outputs[0]['name'])
        self.in_index=inputs[0]['index'];self.out_index=outputs[0]['index'];self.np=np
        if any(any(int(d)<=0 for d in x.get('shape_signature',x['shape'])) for x in inputs+outputs):raise ExtensionError('tensor_shape','Dynamic LiteRT shapes are unsupported by this adapter')
        # Check known tensor sizes before allocation; native scratch/workspace
        # is still backend-specific, not a promise of a complete model sandbox.
        for detail in self.session.get_tensor_details():
            shape=detail['shape']
            if len(shape)>8 or any(int(d)<0 for d in shape) or math.prod(int(d) for d in shape)>max(maximum,1048576):
                raise ExtensionError('model_limit','LiteRT tensor allocation exceeds the supported bounded scope')
    def prepare(self):self.session.allocate_tensors()
    def infer(self,values):
        self.session.set_tensor(self.in_index,self.np.asarray(values,dtype=self.np.float32).reshape(self.input['shape']))
        self.session.invoke();return self.session.get_tensor(self.out_index)

def create(name,raw,threads,maximum):
    if not isinstance(name,str) or name not in PACKAGES:raise ExtensionError('backend_unknown','Choose the litert or onnx CPU backend')
    try:return {'onnx':Onnx,'litert':LiteRT}[name](raw,threads,maximum)
    except ExtensionError:raise
    except (ImportError,OSError):raise ExtensionError('dependency_missing','Install the optional '+PACKAGES[name][1]+' requirements for this Python/CPU/libc; no accelerator or fallback was loaded') from None
    except Exception:raise ExtensionError('model_rejected','The '+name+' CPU engine rejected this model; verify its format, operators and export compatibility') from None
