#!/usr/bin/env python3
"""COM5-only native result snapshots; generated images, no camera capture."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,struct,time
from pathlib import Path
from p4_serial import P4SerialVM

def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'camera_captured':False,'COM12_accessed':False,'checks':{}}
 vm=None;rid=0;session=93713
 def request(op,token=0,uid=0,offset=0,count=0,nonce=None,ok=True):
  nonlocal rid
  rid+=1;s=session if nonce is None else nonce
  body=b'P4MR'+bytes([op,0])+struct.pack('<IIIIHI',rid,s,token,offset,count,uid)
  start=len(vm.events);vm.send(bytes([251,208,0,len(body)+1,0])+body+b'\xfe')
  data=vm.wait(lambda e:e[0]==208 and len(e[2])>=14 and int.from_bytes(e[2][:4],'little')==rid,after=start)[2]
  assert data[5]==op and int.from_bytes(data[6:10],'little')==s
  assert (data[4]==0)==ok,(op,data[4]);return data[14:]
 try:
  vm=P4SerialVM();vm.short(15);time.sleep(.1)
  caps=json.loads(request(0,nonce=0));assert caps['protocol']==1 and caps['chunk_bytes']==512
  request(1)
  handle=vm.call('imageCreate',320,180,3);assert handle>0
  token_start=len(vm.events);assert vm.call('mediaSnapshot',handle,101,session)==handle
  event=vm.wait(lambda e:e[0]==209 and int.from_bytes(e[2][4:8],'little')==101,after=token_start)[2]
  assert int.from_bytes(event[:4],'little')==session;token=int.from_bytes(event[8:12],'little');assert token>0
  assert vm.call('imageRelease',handle) is True
  meta=json.loads(request(2,token,101));assert (meta['source_width'],meta['source_height'],meta['width'],meta['height'],meta['bytes'])==(320,180,160,90,43200)
  raw=bytearray()
  for offset in range(0,meta['bytes'],512):raw.extend(request(3,token,101,offset,min(512,meta['bytes']-offset)))
  assert len(raw)==43200 and not any(raw)
  request(3,token,101,0,513,ok=False);request(3,token,102,0,1,ok=False);request(3,token,101,43200,1,ok=False)
  request(2,token,101,nonce=session+1,ok=False);report['checks']['released_source_retains_exact_snapshot']=True
  request(4,token,101);request(2,token,101,ok=False)
  for i in range(12):
   h=vm.call('imageCreate',80,40,1);assert h>0
   start=len(vm.events);assert vm.call('mediaSnapshot',h,200+i,session)==h;vm.call('imageRelease',h)
   e=vm.wait(lambda e:e[0]==209 and int.from_bytes(e[2][4:8],'little')==200+i,after=start)[2]
   t=int.from_bytes(e[8:12],'little');m=json.loads(request(2,t,200+i));assert m['width']==80 and m['height']==40
   request(4,t,200+i)
  report['checks']['reuse_rounds']=12
  h=vm.call('imageCreate',40,20,1);start=len(vm.events);vm.call('mediaSnapshot',h,300,session);vm.call('imageRelease',h)
  e=vm.wait(lambda e:e[0]==209 and int.from_bytes(e[2][4:8],'little')==300,after=start)[2];t=int.from_bytes(e[8:12],'little')
  request(5);request(2,t,300,ok=False);request(1)
  assert vm.call('imageCount')==0 and vm.call('imageMemory')==0 and vm.call('audioCount')==0
  report['checks']['end_session_invalidates_snapshots']=True;report['checks']['error_bounds_and_stale_ids']=True;report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute required for physical COM5 test')
 main(a)
