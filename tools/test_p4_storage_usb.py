#!/usr/bin/env python3
"""Explicit COM5-only RAM file acceptance; no camera, mic or radio operations."""
# SPDX-License-Identifier: MIT
import argparse,datetime,hashlib,json,struct,time
from pathlib import Path
from p4_serial import P4SerialVM,primitive

class Files:
 def __init__(self,vm):self.vm=vm;self.session=0;self.rid=0;self.timings=[]
 def request(self,op,path='',token=0,arg=0,count=0,data=b'',error=0,session=None,rid=None):
  self.rid+=1;ident=self.rid if rid is None else rid;s=self.session if session is None else session
  name=path.encode('ascii');body=b'MBFS'+bytes([1,op])+struct.pack('<IIIIHBB',ident,s,token,arg,count,len(name),0)+name+data
  start=len(self.vm.events);t=time.monotonic()
  self.vm.send(bytes([251,217,0])+struct.pack('<H',len(body)+1)+body+b'\xfe')
  b=self.vm.wait(lambda e:e[0]==217 and len(e[2])>=16 and int.from_bytes(e[2][6:10],'little')==ident,after=start,seconds=4)[2]
  self.timings.append((time.monotonic()-t)*1000)
  assert b[:6]==b'MBFR'+bytes([1,op]) and int.from_bytes(b[10:14],'little')==s
  assert b[14]==error and b[15]==0,(op,b[14],error)
  return b[16:]
 def open(self):
  b=self.request(9,token=0x53544f52,session=0);self.session,nonce=struct.unpack('<II',b);assert nonce==0x53544f52
 def close(self):self.request(10);self.session=0
 def meta(self,b):
  r,n,p=struct.unpack_from('<IHB',b);name=b[7:7+p].decode();assert len(b)==7+p
  return {'revision':r,'bytes':n,'path':name}
 def stat(self,path):return self.meta(self.request(3,path))
 def begin(self,path,n,revision=0,error=0):
  b=self.request(5,path,token=revision,arg=n,error=error);return struct.unpack('<I',b)[0] if not error else None
 def save(self,path,data,revision=0):
  job=self.begin(path,len(data),revision)
  for i in range(0,len(data),512):
   part=data[i:i+512];r=self.request(6,token=job,arg=i,count=len(part),data=part);assert struct.unpack('<H',r)[0]==i+len(part)
  return self.meta(self.request(7,token=job))
 def read(self,path):
  m=self.stat(path);data=bytearray()
  for i in range(0,m['bytes'],512):
   n=min(512,m['bytes']-i);b=self.request(4,path,token=m['revision'],arg=i,count=n)
   assert struct.unpack_from('<IH',b)==(m['revision'],n);data.extend(b[6:])
  assert len(data)==m['bytes'];return m,bytes(data)

def main(a):
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'physical COM5 USB RAM storage','physical_tested':True,'camera_capture':False,'audio_recording':False,'C6_accessed':False,'COM12_accessed':False,'checks':{}}
 vm=None;f=None;owned=[];timings=[]
 def storage(name,*args):vm.upload(10,primitive(name,args,25));return vm.run_reporter(10)
 try:
  vm=P4SerialVM();report['vm']=vm.version;vm.short(15)
  assert json.loads(vm.call('networkStatus'))['target']=='USB-only'
  assert storage('available','RAM') is True and storage('available','Flash') is False and storage('available','SD') is False
  assert storage('used')==0 and storage('slots')==8,'Pre-existing RAM data: stop instead of erasing it'
  f=Files(vm);f.open();assert f.request(1)==bytes([8,0,32,0,2,3,1])
  cases=[('/RAM/accept-empty',b''),('/RAM/accept-text','Café — stockage RAM\n'.encode()),('/RAM/accept-binary',bytes(range(256))*32)]
  for path,data in cases:
   owned.append(path);m=f.save(path,data);assert f.read(path)==(m,data)
   report['checks'][path]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  assert storage('text','/RAM/accept-text')=='Café — stockage RAM\n'
  job=storage('write','/RAM/accept-text','VM writes share this file.',True);assert isinstance(job,int) and job>0
  assert storage('state',job)=='done';m,data=f.read('/RAM/accept-text');assert data==b'VM writes share this file.'
  old=m['revision'];m=f.save('/RAM/accept-text',b'new version',old)
  f.request(4,'/RAM/accept-text',token=old,count=1,error=7)
  f.begin('/RAM/accept-text',1,old,error=7);f.begin('/RAM/accept-text',1,error=8)
  f.begin('/Flash/not-allowed',1,error=4);f.begin('/RAM/../bad',1,error=3);f.begin('/RAM/large',8193,error=5)
  report['checks']['shared_vm_store_and_revision_errors']=True
  j=f.begin('/RAM/accept-text',4,m['revision']);f.request(6,token=j,count=4,data=b'nope')
  assert storage('write','/RAM/accept-text','not allowed',True) is False
  f.request(8,token=j);assert f.read('/RAM/accept-text')[1]==b'new version'
  report['checks']['cancel_and_vm_contention']=True
  j=f.begin('/RAM/accept-text',4,m['revision']);f.request(6,token=j,count=4,data=b'nope');vm.short(15)
  f.request(7,token=j,error=13);assert f.read('/RAM/accept-text')[1]==b'new version'
  report['checks']['stop_all_preserves_committed_file']=True
  before=f.rid;f.request(1,rid=before,error=1)
  for body in [b'MBFS',b'MBFS'+bytes([2,1])+b'\0'*20,b'MBFS'+bytes([1,1])+b'\0'*19+b'\1']:
   start=len(vm.events);vm.send(bytes([251,217,0])+struct.pack('<H',len(body)+1)+body+b'\xfe')
   end=time.monotonic()+.15
   while time.monotonic()<end:vm.pump()
   assert not any(e[0]==217 for e in vm.events[start:])
   f.request(1)
  report['checks']['replay_and_malformed_recovery']=True
  for i in range(5):
   path=f'/RAM/accept-full{i}';owned.append(path);raw=bytes([i])*8192
   mfull=f.save(path,raw);assert f.read(path)==(mfull,raw)
  f.begin('/RAM/overflow',0,error=10);assert storage('slots')==0
  # Replace the small files too, reaching the real 65536-byte store bound.
  for path,_ in cases[:2]:
   mm=f.stat(path);f.save(path,b'R'*8192,mm['revision'])
  assert storage('used')==65536
  handles=[vm.call('imageCreate',1280,720,3) for _ in range(3)];assert min(handles)>0 and vm.call('imageMemory')==8294400
  assert f.read('/RAM/accept-binary')[1]==bytes(range(256))*32
  vm.call('imageReleaseAll');assert vm.call('imageMemory')==0
  report['checks']['full_ram_and_independent_psram_image_allocation']={'ram_bytes':65536,'image_bytes':8294400}
  for i in range(16):
   mm=f.stat('/RAM/accept-binary');raw=bytes((n+i)%256 for n in range(8192));m=f.save('/RAM/accept-binary',raw,mm['revision']);assert f.read('/RAM/accept-binary')==(m,raw)
   assert vm.call('imageCount')==0
  report['checks']['full_size_replace_read_cycles']=16
  oldsession=f.session;j=f.begin('/RAM/accept-binary',1,m['revision']);f.close();f.open()
  assert f.session!=oldsession;f.request(1,session=oldsession,error=2)
  assert f.read('/RAM/accept-binary')[1]==raw
  f.close();timings.extend(f.timings);vm.close();vm=P4SerialVM();f=Files(vm);f.open();assert f.read('/RAM/accept-binary')[1]==raw
  report['checks']['close_cancels_staging_and_usb_reconnect_preserves_files']=True
  f.close()
  timings.extend(f.timings);report['max_request_rtt_ms']=round(max(timings),3);report['file_requests']=len(timings)
  report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=f'{type(e).__name__}: {e}');raise
 finally:
  if vm:
   try:
    vm.short(15);vm.call('imageReleaseAll')
    if f and f.session:f.close()
    for path in owned:storage('delete',path)
    report['cleanup']={'ram_bytes':storage('used'),'free_slots':storage('slots'),'camera_busy':vm.call('cameraBusy'),'audio_busy':vm.call('audioBusy')}
   except Exception as e:report['cleanup_error']=str(e)
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Current authorization and --execute required')
 main(a)
