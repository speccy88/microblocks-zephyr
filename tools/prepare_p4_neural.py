#!/usr/bin/env python3
"""Prepare a hash-pinned public TFLM builtin model; never vendor model bytes."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path

def static_builtin(model):
 """Constrain only the four known batch signatures in the hash-pinned fixture.

 The original has allocated batch 1 but symbolic batch -1 signatures. Custom
 imports still reject symbolic dimensions. No weights, operators or sizes change.
 """
 raw=bytearray(model)
 def field(table,index):
  vtable=table-struct.unpack_from('<i',raw,table)[0]
  size=struct.unpack_from('<H',raw,vtable)[0]
  offset=struct.unpack_from('<H',raw,vtable+4+index*2)[0] if 4+index*2<size else 0
  return table+offset if offset else 0
 def vector(table,index):
  at=field(table,index)
  if not at:raise ValueError('Pinned fixture vector missing')
  at+=struct.unpack_from('<I',raw,at)[0]
  return at+4,struct.unpack_from('<I',raw,at)[0]
 def child(start,index):
  at=start+4*index
  return at+struct.unpack_from('<I',raw,at)[0]
 root=struct.unpack_from('<I',raw)[0];subgraphs,n=vector(root,2)
 if n!=1:raise ValueError('Pinned fixture subgraph changed')
 tensors,count=vector(child(subgraphs,0),0)
 if count!=10:raise ValueError('Pinned fixture tensors changed')
 changes=[]
 for index in (0,7,8,9):
  table=child(tensors,index);shape,rank=vector(table,0);sig,sig_rank=vector(table,7)
  actual=struct.unpack_from('<'+'i'*rank,raw,shape);symbolic=struct.unpack_from('<'+'i'*sig_rank,raw,sig)
  if rank!=2 or sig_rank!=rank or actual[0]!=1 or symbolic!=(-1,actual[1]):raise ValueError('Pinned fixture signature changed')
  struct.pack_into('<i',raw,sig,1);changes.append(index)
 return bytes(raw),changes

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--tflm',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 spec=json.loads((Path(__file__).resolve().parents[1]/'dependencies/p4-tflm.json').read_text())
 actual=subprocess.check_output(['git','-C',str(a.tflm),'rev-parse','HEAD'],text=True).strip()
 if actual!=spec['source_commit']:raise ValueError('TFLM source pin mismatch')
 array=a.source.read_text().split('g_model[] = {',1)[1].split('};',1)[0];model=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',array));pin=spec['physical_probe']
 if len(model)!=pin['model_bytes'] or hashlib.sha256(model).hexdigest()!=pin['model_sha256']:raise ValueError('Builtin model hash mismatch')
 source_digest=hashlib.sha256(model).digest();model,changes=static_builtin(model)
 a.output.mkdir(parents=True,exist_ok=True);path=(a.output/'sine-int8.tflite').resolve();path.write_bytes(model)
 (a.output/'neural_builtin.S').write_text('.section .rodata.p4_nn_builtin,"a"\n.balign 16\n.global p4_nn_builtin_start,p4_nn_builtin_end\np4_nn_builtin_start:\n.incbin '+json.dumps(str(path).replace('\\','/'))+'\np4_nn_builtin_end:\n',newline='\n')
 (a.output/'neural_builtin.h').write_text('#pragma once\nextern "C" const unsigned char p4_nn_builtin_start[],p4_nn_builtin_end[];\nstatic const unsigned char p4_nn_builtin_digest[32]={'+','.join(str(x) for x in hashlib.sha256(model).digest())+'};\nstatic const unsigned char p4_nn_builtin_source_digest[32]={'+','.join(str(x) for x in source_digest)+'};\n',newline='\n')
 report={'builtin':'sine-int8-v1','bytes':len(model),'sha256':hashlib.sha256(model).hexdigest(),'source_sha256':source_digest.hex(),'static_batch_one_tensors':changes,'runtime':actual}
 (a.output/'neural_builtin.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report))
