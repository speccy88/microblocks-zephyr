#!/usr/bin/env python3
"""Provision Fred's explicitly approved AP over USB without printing its key."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,secrets,struct,time
from pathlib import Path
from p4_serial import P4SerialVM

def provision(a):
 root=Path(__file__).resolve().parents[1];private=(root/'secrets').resolve();path=a.private_file.resolve()
 if not path.is_relative_to(private):raise ValueError('Credential file must be in the ignored repository secrets directory')
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'target':'COM5 approved MicroBlocks-P4 WPA2 AP','password_recorded':False,'C6_flashed':False,'Windows_network_changed':False}
 vm=P4SerialVM()
 try:
  before=json.loads(vm.call('networkStatus'));report['before']=before
  if not before.get('wifi_driver_ready') or not before.get('assets_valid'):raise RuntimeError('Safe initialization and verified editor assets required before credential creation')
  if not path.exists():
   if before.get('credentials_saved'):raise RuntimeError('Board already has credentials; recover the existing private file instead of rotating')
   private.mkdir(exist_ok=True)
   with path.open('x',encoding='ascii',newline='\n') as f:f.write(secrets.token_urlsafe(12)+'\n')
   report['private_file_created']=True
  password=path.read_bytes().strip()
  if len(password)!=16 or any(c not in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in password):raise ValueError('Invalid private key file')
  nonce=secrets.randbits(32);body=b'P4AP'+bytes([1,0])+struct.pack('<I',nonce)+bytes([16])+password
  packet=bytes([251,214,0])+struct.pack('<H',len(body)+1)+body+b'\xfe';start=len(vm.events);vm.send(packet)
  reply=vm.wait(lambda e:e[0]==214 and len(e[2])==6 and int.from_bytes(e[2][:4],'little')==nonce,seconds=8,after=start)[2]
  if reply[4]:raise RuntimeError('USB provisioning rejected with status '+str(reply[4]))
  began=time.monotonic()
  while True:
   current=json.loads(vm.call('networkStatus'))
   if current.get('ap_running') or current.get('error'):break
   if time.monotonic()-began>35:raise RuntimeError('AP initialization exceeded bounded deadline')
   time.sleep(.1)
  report['after']=current;report['result']='PASS' if current.get('ap_running') else 'FAIL'
  if not current.get('ap_running'):raise RuntimeError('AP startup failed: '+current['phase']+' ('+str(current['error'])+')')
 finally:
  vm.close();a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--private-file',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:p.error('--execute and explicit AP configuration authorization required')
 provision(a)
