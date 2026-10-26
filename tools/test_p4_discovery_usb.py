#!/usr/bin/env python3
"""COM5-only address/ID/register acceptance; never captures camera/audio."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,time
from pathlib import Path
from p4_serial import P4SerialVM,primitive
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute and approved COM5 scope required')
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'native Zephyr COM5 real I2C bus 0','camera_captured':False,'audio_recorded':False,'COM12_accessed':False,'checks':{}}
 v=None
 try:
  v=P4SerialVM();v.short(15)
  def call(name,*args):v.upload(10,primitive(name,args,4),2);return v.run_reporter(10)
  def finish():
   began=time.monotonic();polls=0;max_rtt=0
   while call('busy'):
    t=time.monotonic();assert v.call('imageCount')==0;max_rtt=max(max_rtt,(time.monotonic()-t)*1000);polls+=1
    assert time.monotonic()-began<4,'I2C deadline did not finish';time.sleep(.001)
   return {'elapsed_ms':round((time.monotonic()-began)*1000,2),'vm_calls_while_busy':polls,'max_vm_rtt_ms':round(max_rtt,2),'status':call('status')}
  assert call('scan',1,False) is False;assert 'Only bus 0' in call('status')
  assert call('scan',0,False) is True;report['checks']['address_scan']=finish();count=call('count');assert 2<=count<=32,count
  old=call('sensorAt',1);assert old.startswith('I2C:');assert call('sensorAt',0)=='' and call('sensorAt',33)==''
  address_devices=[]
  for i in range(1,count+1):
   ref=call('sensorAt',i);address=call('address',ref);assert call('measurementCount',ref)==0
   assert call('confidence',ref) in ['address only','candidate only'];address_devices.append(address)
  assert 0x10 in address_devices and 0x18 in address_devices;report['checks']['address_only_addresses']=address_devices
  assert call('scan',0,True) is True;report['checks']['identified_scan']=finish();assert call('address',old) is False
  devices=[];camera=None
  for i in range(1,call('count')+1):
   ref=call('sensorAt',i);address=call('address',ref);name=call('name',ref);identity=call('confidence',ref)
   measurements=[call('measurement',ref,j) for j in range(1,call('measurementCount',ref)+1)]
   devices.append({'address':address,'name':name,'identity':identity,'bus':call('bus',ref),'measurements':measurements})
   if address in [0x10,0x18]:
    assert identity=='confirmed ID',(address,name,identity);assert call('read',ref,'device ID') is True;finish()
    assert call('value')==({0x10:0x219,0x18:0x8311}[address]);assert call('unit')=='ID' and call('scale')==1
    devices[-1]['actual_device_ID']=call('value')
   if address==0x10:camera=ref
  assert camera
  for measurement in ['exposure lines','analog gain code']:
   assert call('read',camera,measurement) is True;finish();value=call('value');assert isinstance(value,int) and not isinstance(value,bool) and 0<=value<=65535
   report['checks'][measurement]={'value':value,'unit':call('unit'),'scale':call('scale'),'meaning':'sensor configuration register, not a captured image'}
  assert call('read',camera,'temperature') is False;assert 'unsupported' in call('status');assert call('value') is False
  assert call('read','I2C:ffffffff:10','device ID') is False
  assert call('scan',0,False) is True;v.short(15);report['checks']['stop_all']=finish()
  for _ in range(3):assert call('scan',0,True) is True;finish()
  report['checks']['devices']=devices;report['checks']['rescan_rounds']=3;report['checks']['stale_refs_and_unsupported_measurements']=True
  assert not v.call('cameraBusy') and not v.call('audioBusy') and v.call('imageCount')==0 and v.call('audioCount')==0
  report['checks']['capture_idle']=True;report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if v:
   try:v.short(15)
   except Exception:pass
   v.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2),flush=True)
