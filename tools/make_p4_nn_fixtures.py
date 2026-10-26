#!/usr/bin/env python3
"""Generate authored numeric-only ONNX/TFLite fixtures; no user model upload."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np,onnx
from onnx import helper,numpy_helper,TensorProto
from onnx.reference import ReferenceEvaluator
from convert_p4_onnx_dense import convert,dense_tflite

def generate(folder):
 folder.mkdir(parents=True,exist_ok=True)
 w=np.array([[2,3],[-1,.5]],dtype=np.float32);bias=np.array([1,-2],dtype=np.float32)
 graph=helper.make_graph([helper.make_node('Gemm',['input','weights','bias'],['output'],transB=1)],'sensor-affine-demo',[helper.make_tensor_value_info('input',TensorProto.FLOAT,[1,2])],[helper.make_tensor_value_info('output',TensorProto.FLOAT,[1,2])],[numpy_helper.from_array(w,'weights'),numpy_helper.from_array(bias,'bias')])
 model=helper.make_model(graph,opset_imports=[helper.make_opsetid('',13)],ir_version=8);source=model.SerializeToString();artifact,details=convert(source)
 (folder/'sensor-affine.onnx').write_bytes(source);(folder/'sensor-affine.tflite').write_bytes(artifact)
 manifest=dict(schema=1,id='sensor-affine-v1',backend='tflm-reference-dense-v1',artifact_format='tflite',source_format='onnx',source='authored numeric sensor demo; no actuator binding',source_sha256=hashlib.sha256(source).hexdigest(),sha256=hashlib.sha256(artifact).hexdigest(),bytes=len(artifact),license='MIT',arena_bytes=16384,operators=['FULLY_CONNECTED'],**details)
 evaluator=ReferenceEvaluator(model);vectors=[]
 for values in [[0,0],[1,2],[-2,4],[.125,-.5]]:
  result=evaluator.run(None,{'input':np.array([values],dtype=np.float32)})[0].reshape(-1).tolist();vectors.append({'input':values,'output':result})
 manifest['golden_vectors']=vectors;(folder/'sensor-affine.json').write_text(json.dumps(manifest,indent=2)+'\n',newline='\n')
 large,_=dense_tflite([(np.ones((1,8192),dtype=np.float32),np.zeros(1,dtype=np.float32),'NONE')]);(folder/'arena-exhaustion.tflite').write_bytes(large)
 class Table:
  def __init__(self,raw,pos):self.raw=raw;self.pos=pos
  def field(self,index):
   vt=self.pos-struct.unpack_from('<i',self.raw,self.pos)[0];size=struct.unpack_from('<H',self.raw,vt)[0]
   return self.pos+struct.unpack_from('<H',self.raw,vt+4+index*2)[0] if 4+index*2<size and struct.unpack_from('<H',self.raw,vt+4+index*2)[0] else 0
  def vector(self,index):p=self.field(index);v=p+struct.unpack_from('<I',self.raw,p)[0];return v+4,struct.unpack_from('<I',self.raw,v)[0]
  def entry(self,index,item):start,n=self.vector(index);assert item<n;p=start+4*item;return Table(self.raw,p+struct.unpack_from('<I',self.raw,p)[0])
 unsupported=bytearray(artifact);root=Table(unsupported,struct.unpack_from('<I',unsupported)[0]);code=root.entry(1,0)
 if code.field(0):unsupported[code.field(0)]=25
 if code.field(3):struct.pack_into('<i',unsupported,code.field(3),25)
 (folder/'unsupported-op.tflite').write_bytes(unsupported)
 badshape=bytearray(artifact);root=Table(badshape,struct.unpack_from('<I',badshape)[0]);tensor=root.entry(2,0).entry(0,0);dims,n=tensor.vector(0);assert n==2;struct.pack_into('<i',badshape,dims+4,0x7fffffff);(folder/'oversized-shape.tflite').write_bytes(badshape)
 malformed=bytearray(64);malformed[4:8]=b'TFL3';(folder/'malformed.tflite').write_bytes(malformed)
 return {'authored_model_bytes':len(artifact),'golden_source':'ONNX ReferenceEvaluator, local CPU','golden_vectors':vectors,'arena_exhaustion_model_bytes':len(large),'artifacts_uploaded':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(generate(a.output),indent=2))
