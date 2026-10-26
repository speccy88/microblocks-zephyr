#!/usr/bin/env python3
"""COM5 native NN golden/import/lifecycle acceptance. No capture or actuation."""
# SPDX-License-Identifier: MIT
import argparse,datetime,hashlib,json,math,struct,time
from pathlib import Path
from p4_serial import P4SerialVM

def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'physical COM5 native Zephyr TFLM','camera_captured':False,'audio_recorded':False,'COM12_accessed':False,'checks':{}}
 vm=None;rid=0
 def request(op,token=0,offset=0,arg=0,data=b'',count=None,error=0):
  nonlocal rid
  rid+=1;size=len(data) if count is None else count
  body=b'P4NN'+bytes([op,1])+struct.pack('<IIIHI',rid,token,offset,size,arg)+data
  start=len(vm.events);vm.send(bytes([251,216,0])+struct.pack('<H',len(body)+1)+body+b'\xfe')
  payload=vm.wait(lambda e:e[0]==216 and len(e[2])>=10 and int.from_bytes(e[2][:4],'little')==rid,after=start,seconds=8)[2]
  assert payload[4]==error,(op,payload[4],error);assert payload[5]==op
  return int.from_bytes(payload[6:10],'little'),payload[10:]
 def state():return json.loads(request(10)[1])
 def finish(seconds=10):
  began=time.monotonic();polls=0;maximum=0
  while True:
   t=time.monotonic();s=state();maximum=max(maximum,(time.monotonic()-t)*1000);polls+=1
   if not s['busy']:return s,{'polls':polls,'max_status_rtt_ms':round(maximum,3)}
   assert time.monotonic()-began<seconds,('bounded NN job timed out',s)
   assert vm.call('imageCount')>=0 # VM must execute another primitive while busy.
   time.sleep(.005)
 def unload(token):
  request(9,token);s,_=finish();assert not s['loaded'] and not s['model_ram_bytes'] and not s['arena_reserved_bytes'],s
 def metadata(raw,source=b'authored local fixture',digest=None):
  result=(digest or hashlib.sha256(raw).digest())+hashlib.sha256((a.fixtures/'sensor-affine.onnx').read_bytes()).digest()+b'\x01'
  for value in [b'sensor-affine-v1',b'MIT',source]:result+=bytes([len(value)])+value
  return result
 def upload(raw,arena=16384,digest=None):
  t,_=request(1,offset=arena,arg=len(raw),data=metadata(raw,digest=digest))
  for offset in range(0,len(raw),512):request(2,t,offset,data=raw[offset:offset+512])
  request(3,t);return t,finish()[0]
 try:
  vm=P4SerialVM();vm.short(15);time.sleep(.1)
  assert vm.call('nnAvailable') is True
  request(4);finish();existing=vm.call('nnCurrentModel')
  if existing:unload(int(existing[3:],16))
  report['checks']['capabilities']=json.loads(request(0)[1])
  reference=vm.call('nnLoadBuiltin','sine-int8-v1');assert reference.startswith('NN:');token=int(reference[3:],16)
  s,timing=finish();assert s['loaded'],s
  info=json.loads(request(5,token)[1]);assert info['input']['dtype']=='int8' and info['input']['shape']==[1,1]
  report['checks']['builtin_metadata']=info
  assert vm.call('nnRun',reference,1) is False # All inputs required.
  assert vm.call('nnSetValue',reference,0,1000) is False
  assert vm.call('nnSetValue',reference,1,-1000) is False
  outputs=[]
  for milli in [0,250,500,1000,1500,2000,3000,4000,5000,6000]:
   assert vm.call('nnSetValue',reference,1,milli) is True
   assert vm.call('nnRun',reference,1) is True;s,_=finish();assert s['phase']=='ready',s
   value=vm.call('nnOutputValue',reference,1);assert isinstance(value,int) and not isinstance(value,bool)
   expected=math.sin(milli/1000);assert abs(value/1000-expected)<.2,(milli,value,expected)
   outputs.append({'input':milli/1000,'output':value/1000,'elapsed_us':s['elapsed_us']})
  report['checks']['builtin_golden']=outputs;report['checks']['builtin_resources']=s
  assert vm.call('nnRun',reference,256) is True
  before=time.monotonic();vm.call('nnCancel');s,timing=finish();assert s['message']=='cancelled',s
  report['checks']['cancellation']={'milliseconds':round((time.monotonic()-before)*1000,3),**timing,'completed_invocations':s['completed_invocations']}
  assert vm.call('nnSetValue',reference,1,1000) is True;assert vm.call('nnRun',reference,1) is True;assert finish()[0]['phase']=='ready'
  unload(token);request(6,token,count=1,error=7)
  fixture=json.loads((a.fixtures/'sensor-affine.json').read_text());raw=(a.fixtures/'sensor-affine.tflite').read_bytes();runs=[]
  for iteration in range(3):
   token,s=upload(raw);assert s['loaded'],s;ref=f'NN:{token:08x}';meta=json.loads(request(5,token)[1]);assert meta['input']['shape']==[1,2] and meta['input']['dtype']=='float32'
   assert vm.call('nnRun',ref,1) is False
   request(7,token,0,data=struct.pack('<f',float('nan')),error=4)
   request(7,token,1,data=b'\0'*4,error=4);request(7,token,8,data=b'\0'*4,error=4)
   for vector in fixture['golden_vectors']:
    request(7,token,data=struct.pack('<2f',*vector['input']))
    assert vm.call('nnRun',ref,1) is True;s,_=finish();assert s['phase']=='ready',s
    actual=list(struct.unpack('<2f',request(6,token,count=8)[1]));assert all(abs(x-y)<1e-5 for x,y in zip(actual,vector['output'])),(actual,vector)
    if iteration==0:runs.append({'input':vector['input'],'actual':actual,'expected':vector['output'],'elapsed_us':s['elapsed_us']})
   if iteration==0:report['checks']['custom_metadata']=meta;report['checks']['custom_resources']=s
   unload(token)
  report['checks']['custom_golden']=runs;report['checks']['load_run_unload_rounds']=3
  errors={}
  for name in ['malformed','unsupported-op','oversized-shape','dynamic-batch','arena-exhaustion']:
   bad=(a.fixtures/(name+'.tflite')).read_bytes();token,s=upload(bad,4096 if name=='arena-exhaustion' else 16384)
   assert not s['loaded'] and s['phase']=='error' and not s['arena_reserved_bytes'] and not s['model_ram_bytes'],s
   errors[name]=s['message']
  _,s=upload(raw,digest=bytes(32));assert not s['loaded'] and 'SHA-256 mismatch' in s['message'];errors['hash_mismatch']=s['message']
  request(1,offset=16384,arg=262145,data=metadata(raw),error=4)
  token,_=request(1,offset=16384,arg=len(raw),data=metadata(raw));request(3,token,error=9);request(2,token,1,data=raw[:32],error=4)
  request(4);assert not state()['model_ram_bytes'];report['checks']['rejections']=errors
  reference=vm.call('nnLoadBuiltin','sine-int8-v1');assert finish()[0]['loaded'];token=int(reference[3:],16)
  assert vm.call('nnSetValue',reference,1,1000) is True;assert vm.call('nnRun',reference,256) is True
  request(9,token);s,_=finish();assert not s['loaded'] and not s['arena_reserved_bytes'];report['checks']['deferred_unload_during_run']=True
  handles=[vm.call('imageCreate',320,180,3) for _ in range(4)];assert min(handles)>0
  for h in handles:assert vm.call('imageRelease',h) is True
  assert vm.call('imageCount')==0 and vm.call('audioCount')==0 and not vm.call('cameraBusy') and not vm.call('audioBusy')
  report['checks']['media_heap_reuse_and_idle']=True;report['checks']['final_status']=state();report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('nnCancel');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute required for authorized COM5 tests')
 main(a)
