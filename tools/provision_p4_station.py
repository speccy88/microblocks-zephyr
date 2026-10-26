#!/usr/bin/env python3
"""Consume the existing CurrentUser-DPAPI handoff; COM5 station only.

Never prints credentials or exception details. No prompt, Windows network
change, AP fallback, credential arguments, plaintext file or firmware backup.
"""
# SPDX-License-Identifier: MIT
import argparse,ctypes,datetime,json,os,struct,time
from ctypes import wintypes
from pathlib import Path
from p4_serial import P4SerialVM

class Blob(ctypes.Structure):
 _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def decrypt(path):
 if os.name!='nt':raise RuntimeError('Windows current user required')
 if not 1<=path.stat().st_size<=16384:raise RuntimeError('Invalid encrypted handoff size')
 source=ctypes.create_string_buffer(path.read_bytes());value=Blob(len(source)-1,ctypes.cast(source,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
 crypto=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 crypto.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
 crypto.CryptUnprotectData.restype=wintypes.BOOL;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
 try:
  if not crypto.CryptUnprotectData(ctypes.byref(value),None,None,None,None,1,ctypes.byref(out)):raise RuntimeError('DPAPI unavailable')
  return bytearray(ctypes.string_at(out.data,out.size))
 finally:
  ctypes.memset(source,0,len(source))
  if out.data:ctypes.memset(out.data,0,out.size);kernel.LocalFree(out.data)

def main(a):
 root=Path(__file__).resolve().parents[1];handoff=root/'secrets/p4-station-handoff.dpapi';receipt=root/'build-artifacts/p4-station-entry/status.json'
 vm=None;raw=None;credential=None;payload=None;rid=0;stage='checking_station_firmware';report={}
 def request(op,data=b''):
  nonlocal rid
  rid+=1;body=bytearray(b'P4ST'+bytes([op,1])+struct.pack('<I',rid));body.extend(data)
  start=len(vm.events)
  try:vm.send(bytes([251,214,0])+struct.pack('<H',len(body)+1)+body+b'\xfe')
  finally:body[:]=bytes(len(body))
  answer=vm.wait(lambda e:e[0]==214 and len(e[2])>=6 and int.from_bytes(e[2][:4],'little')==rid,seconds=8,after=start)[2]
  if answer[4] or answer[5]!=op:raise RuntimeError('Board rejected provisioning')
  return answer[6:]
 try:
  vm=P4SerialVM();status=json.loads(request(0))
  if status.get('station_protocol')!=1 or status.get('ap_running') is not False:raise RuntimeError('Station firmware required')
  if not handoff.is_file():raise RuntimeError('Existing encrypted handoff required')
  stage='decrypting_existing_handoff';raw=decrypt(handoff);credential=json.loads(raw)
  if credential.get('schema')!=1 or credential.get('destination')!='COM5 ESP32-P4' or credential.get('security')!='WPA2-PSK' or credential.get('persist') is not True:raise RuntimeError('Unexpected destination or authorization')
  ssid=credential['ssid'].encode('utf8');password=credential['password'].encode('utf8')
  if not 1<=len(ssid)<=32 or not 8<=len(password)<=64 or b'\0' in ssid+password:raise RuntimeError('Invalid credential lengths')
  payload=bytearray([len(ssid),len(password),1,1]);payload.extend(ssid);payload.extend(password)
  stage='provisioning_approved_station';request(1,payload)
  payload[:]=bytes(len(payload));raw[:]=bytes(len(raw));credential=None;ssid=password=None
  status=json.loads(request(0))
  if not status.get('credentials_saved'):raise RuntimeError('Board persistence unverified')
  stage='awaiting_station_connection';deadline=time.monotonic()+75
  while time.monotonic()<deadline:
   status=json.loads(request(0))
   if status.get('ap_running') is not False:raise RuntimeError('Unexpected radio mode')
   if status.get('phase')=='ready' and status.get('station_connected'):break
   if status.get('error'):break
   time.sleep(.5)
  report={'status':'connected' if status.get('station_connected') else 'saved_connection_failed','updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'destination':'ESP32-P4 COM5 station Wi-Fi','ssid_present':True,'password_present':True,'persist_on_board_authorized':True,'board_configuration_applied':True,'credentials_saved_verified':True,'encrypted_handoff':True,'plaintext_written':False,'encrypted_handoff_retained_for_reboot_verification':True,'board_status':status}
 except BaseException:
  # Exception text could contain parser/UART data; never include it in output.
  report={'status':'provisioning_failed','stage':stage,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'destination':'ESP32-P4 COM5 station Wi-Fi','encrypted_handoff_retained':handoff.exists(),'plaintext_written':False,'secret_values_output':False}
 finally:
  if raw:raw[:]=bytes(len(raw))
  if payload:payload[:]=bytes(len(payload))
  credential=None
  if vm:vm.close()
  receipt.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
 return 0 if report.get('status')=='connected' else 1

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:p.error('Current station association/persistence authorization and --execute required')
 raise SystemExit(main(a))
