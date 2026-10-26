#!/usr/bin/env python3
"""Offline restricted ONNX Gemm/Relu conversion into native dense TFLite.

No ONNX Runtime, model service, code execution, external tensor data or robot
actuation. Unsupported graphs are rejected instead of silently rewritten.
"""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,math
from pathlib import Path

def dense_tflite(layers):
 """Serialize the pinned TFLite v3 dense subset using FlatBuffers tables."""
 import flatbuffers,numpy as np
 if not 1<=len(layers)<=16:raise ValueError('Expected 1..16 dense layers')
 b=flatbuffers.Builder(1024)
 def ints(values):
  b.StartVector(4,len(values),4)
  for value in reversed(values):b.PrependInt32(int(value))
  return b.EndVector()
 def offsets(values):
  b.StartVector(4,len(values),4)
  for value in reversed(values):b.PrependUOffsetTRelative(value)
  return b.EndVector()
 def buffer(raw):
  vector=b.CreateByteVector(raw) if raw else 0;b.StartObject(3)
  if vector:b.PrependUOffsetTRelativeSlot(0,vector,0)
  return b.EndObject()
 buffers=[buffer(b'')];tensors=[];ops=[];previous=0;macs=0
 first=np.asarray(layers[0][0]);tensors.append(([1,int(first.shape[1])],0,'input'))
 for i,(weight,bias,activation) in enumerate(layers):
  weight=np.asarray(weight,dtype='<f4');bias=np.asarray(bias,dtype='<f4');units,features=weight.shape
  if not units or not features or weight.size>16384 or bias.shape!=(units,) or features!=math.prod(tensors[previous][0]):raise ValueError('Dense tensor shape/element limit exceeded')
  if not np.isfinite(weight).all() or not np.isfinite(bias).all() or activation not in ['NONE','RELU']:raise ValueError('Non-finite or unsupported dense parameter')
  macs+=weight.size
  if macs>1000000:raise ValueError('MAC budget exceeded')
  wi=len(tensors);buffers.append(buffer(weight.tobytes()));tensors.append(([units,features],len(buffers)-1,'weights_'+str(i)))
  bi=len(tensors);buffers.append(buffer(bias.tobytes()));tensors.append(([units],len(buffers)-1,'bias_'+str(i)))
  oi=len(tensors);tensors.append(([1,units],0,'output_'+str(i)));ops.append(([previous,wi,bi],oi,activation));previous=oi
 if len(tensors)>64:raise ValueError('Tensor count exceeds native limit')
 tables=[]
 for shape,buf,name in tensors:
  shape_vec=ints(shape);label=b.CreateString(name);b.StartObject(9);b.PrependUOffsetTRelativeSlot(0,shape_vec,0);b.PrependUint32Slot(2,buf,0);b.PrependUOffsetTRelativeSlot(3,label,0);b.PrependBoolSlot(8,True,False);tables.append(b.EndObject())
 op_tables=[]
 for inputs,output,activation in ops:
  b.StartObject(5);b.PrependInt8Slot(0,1 if activation=='RELU' else 0,0);options=b.EndObject();iv=ints(inputs);ov=ints([output]);b.StartObject(5);b.PrependUOffsetTRelativeSlot(1,iv,0);b.PrependUOffsetTRelativeSlot(2,ov,0);b.PrependUint8Slot(3,8,0);b.PrependUOffsetTRelativeSlot(4,options,0);op_tables.append(b.EndObject())
 tv=offsets(tables);iv=ints([0]);ov=ints([previous]);opv=offsets(op_tables);label=b.CreateString('dense');b.StartObject(5)
 for slot,value in [(0,tv),(1,iv),(2,ov),(3,opv),(4,label)]:b.PrependUOffsetTRelativeSlot(slot,value,0)
 graph=b.EndObject();b.StartObject(4);b.PrependInt8Slot(0,9,0);b.PrependInt32Slot(2,1,1);b.PrependInt32Slot(3,9,0);opcode=b.EndObject()
 graphs=offsets([graph]);codes=offsets([opcode]);bufs=offsets(buffers);description=b.CreateString('Offline static dense conversion; CPU inference only');b.StartObject(8);b.PrependUint32Slot(0,3,0)
 for slot,value in [(1,codes),(2,graphs),(3,description),(4,bufs)]:b.PrependUOffsetTRelativeSlot(slot,value,0)
 root=b.EndObject();b.Finish(root,file_identifier=b'TFL3');raw=bytes(b.Output())
 if len(raw)>262144:raise ValueError('Converted model exceeds 256 KiB')
 return raw,{'input':{'dtype':'float32','shape':tensors[0][0]},'output':{'dtype':'float32','shape':tensors[previous][0]},'macs':macs}

def convert(raw):
 import onnx,numpy as np
 if len(raw)>524288:raise ValueError('ONNX source exceeds 512 KiB conversion limit')
 model=onnx.load_model_from_string(raw)
 if model.functions or model.graph.sparse_initializer or len(model.graph.node)>32 or len(model.graph.initializer)>64:raise ValueError('Functions, sparse data or graph size unsupported')
 if any(x.domain not in ('','ai.onnx') or not 7<=x.version<=21 for x in model.opset_import):raise ValueError('Unsupported ONNX domain/opset')
 for t in model.graph.initializer:
  if t.external_data or t.data_location==onnx.TensorProto.EXTERNAL or t.data_type!=onnx.TensorProto.FLOAT or not t.dims or any(d<=0 for d in t.dims) or math.prod(t.dims)>16384:raise ValueError('Only bounded embedded float32 tensors are supported')
 onnx.checker.check_model(model)
 graph=model.graph
 if len(graph.input)!=1 or len(graph.output)!=1:raise ValueError('Expected one data input and one output')
 def shape(value):
  t=value.type.tensor_type
  if t.elem_type!=onnx.TensorProto.FLOAT or len(t.shape.dim)!=2 or any(d.HasField('dim_param') or not d.HasField('dim_value') or d.dim_value<=0 for d in t.shape.dim):raise ValueError('Expected static float32 [1,N] tensors')
  result=[d.dim_value for d in t.shape.dim]
  if result[0]!=1 or math.prod(result)>16384:raise ValueError('Batch/element limit exceeded')
  return result
 input_shape=shape(graph.input[0]);expected_output=shape(graph.output[0]);constants={t.name:onnx.numpy_helper.to_array(t) for t in graph.initializer}
 if len(constants)!=len(graph.initializer) or graph.input[0].name in constants:raise ValueError('Mutable or duplicate weights unsupported')
 current=graph.input[0].name;features=input_shape[1];layers=[]
 for node in graph.node:
  if node.domain not in ('','ai.onnx') or len(node.output)!=1:raise ValueError('Unsupported operator domain/output count')
  if node.op_type=='Gemm':
   if len(node.input) not in (2,3) or node.input[0]!=current or node.input[1] not in constants:raise ValueError('Expected sequential Gemm with constant weights')
   attrs={a.name:onnx.helper.get_attribute_value(a) for a in node.attribute}
   if any(k not in ('alpha','beta','transA','transB') for k in attrs) or attrs.get('alpha',1)!=1 or attrs.get('beta',1)!=1 or attrs.get('transA',0)!=0 or attrs.get('transB',0) not in (0,1):raise ValueError('Unsupported Gemm attributes')
   weight=np.asarray(constants[node.input[1]],dtype='<f4');weight=weight if attrs.get('transB',0) else weight.T
   if weight.ndim!=2 or weight.shape[1]!=features:raise ValueError('Gemm shape mismatch')
   units=weight.shape[0]
   if len(node.input)==3:
    if node.input[2] not in constants:raise ValueError('Bias must be constant')
    bias=np.asarray(constants[node.input[2]],dtype='<f4')
    if bias.shape not in [(units,),(1,units)]:raise ValueError('Only per-output bias is supported')
    bias=bias.reshape(units)
   else:bias=np.zeros(units,dtype='<f4')
   layers.append([weight,bias,'NONE']);features=units
  elif node.op_type=='Relu':
   if not layers or node.input!=[current] or node.attribute or layers[-1][2]!='NONE':raise ValueError('Expected one fused Relu after Gemm')
   layers[-1][2]='RELU'
  else:raise ValueError('Unsupported ONNX operator: '+node.op_type)
  current=node.output[0]
 if current!=graph.output[0].name or expected_output!=[1,features] or not layers:raise ValueError('Graph output/shape mismatch')
 artifact,details=dense_tflite(layers);return artifact,details

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--id',default='custom-dense');p.add_argument('--license',required=True);p.add_argument('--arena-bytes',type=int,default=65536);a=p.parse_args()
 if a.source.stat().st_size>524288:p.error('ONNX source exceeds 512 KiB')
 raw=a.source.read_bytes();artifact,details=convert(raw)
 manifest=dict(schema=1,id=a.id,backend='tflm-reference-dense-v1',artifact_format='tflite',source_format='onnx',source='local ONNX file',source_sha256=hashlib.sha256(raw).hexdigest(),sha256=hashlib.sha256(artifact).hexdigest(),bytes=len(artifact),license=a.license,arena_bytes=a.arena_bytes,operators=['FULLY_CONNECTED'],**details)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(artifact);a.output.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n',newline='\n');print(json.dumps({'id':a.id,'artifact_bytes':len(artifact),'artifact_sha256':manifest['sha256'],'conversion':'ONNX Gemm/Relu to TFLite; not direct ONNX Runtime'}))
