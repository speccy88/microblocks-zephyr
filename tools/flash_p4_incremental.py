#!/usr/bin/env python3
"""Hash-checked COM5 application update; unchanged model sectors stay in place.

Uses local build files and device digests only. No read_flash/backup operation.
The installed full application must exactly match the supplied local baseline.
"""
# SPDX-License-Identifier: MIT
import argparse,contextlib,datetime,hashlib,io,json,re,struct
from pathlib import Path

def changed_sectors(before,after):
 for image in [before,after]:
  if not 24<=len(image)<=0xfe0000-0x2000 or image[0]!=0xe9 or struct.unpack_from('<H',image,12)[0]!=18 or struct.unpack_from('<HH',image,15)!=(103,199):raise ValueError('Expected bounded revision-guarded native P4 images')
 result=[]
 for offset in range(0,max(len(before),len(after)),4096):
  previous=before[offset:offset+4096];previous+=b'\xff'*(4096-len(previous))
  data=after[offset:offset+4096];data+=b'\xff'*(4096-len(data))
  if previous!=data:
   if 0x2000+offset+len(data)>0xfe0000:raise ValueError('Changed sector crosses application region')
   result.append((0x2000+offset,data))
 if sum(len(data) for _,data in result)>262144:raise ValueError('More than 256 KB changed; use the normal full-image flasher')
 return result

def main(a):
 import esptool
 from esptool.cmds import attach_flash,verify_flash,write_flash
 from p4_serial import require_com5
 require_com5();before=a.baseline.read_bytes();after=a.image.read_bytes();sectors=changed_sectors(before,after)
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'target':'COM5 native P4 application only','baseline_sha256':hashlib.sha256(before).hexdigest(),'image_sha256':hashlib.sha256(after).hexdigest(),'image_bytes':len(after),'changed_sectors':[{'offset':hex(addr),'bytes':len(data)} for addr,data in sectors],'changed_bytes':sum(len(data) for _,data in sectors),'backup_performed':False,'firmware_readback_performed':False,'assets_or_NVS_written':False,'C6_flashed':False,'COM12_accessed':False,'baseline_verified':False,'hash_verified':False}
 esp=None;capture=io.StringIO()
 try:
  with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
   esp=esptool.detect_chip('COM5',115200)
   if esp.CHIP_NAME!='ESP32-P4' or esp.get_chip_revision()!=103:raise RuntimeError('Physical P4 revision mismatch')
   esp=esp.run_stub();esp.change_baud(921600);attach_flash(esp)
   verify_flash(esp,[(0x2000,before)],flash_size='32MB',flash_mode='dio',flash_freq='80m',diff=False)
   report['baseline_verified']=True
   if sectors:write_flash(esp,sectors,flash_size='32MB',flash_mode='dio',flash_freq='80m',compress=True,no_progress=True)
   verify_flash(esp,[(0x2000,after)],flash_size='32MB',flash_mode='dio',flash_freq='80m',diff=False)
   report.update(hash_verified=True,result='PASS')
 except BaseException as e:
  report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if esp:
   with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):
    try:esp.hard_reset()
    finally:esp._port.close()
  # SDK output is metadata only; still remove any unique address defensively.
  output=re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b','<redacted>',capture.getvalue())
  print('\n'.join(line for line in output.splitlines() if line.startswith(('Verifying','Verification','Hard resetting'))));a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps({k:v for k,v in report.items() if k!='changed_sectors'},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--image',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:p.error('--execute and current P4 flash authorization required')
 main(a)
