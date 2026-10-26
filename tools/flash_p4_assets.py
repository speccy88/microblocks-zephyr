#!/usr/bin/env python3
"""Write only the bounded editor partition on the authorized COM5 P4."""
# SPDX-License-Identifier: MIT
import argparse,datetime,hashlib,json,re,struct,subprocess,sys,zlib
from pathlib import Path

OFFSET=0xfe0000
LIMIT=0x1fe0000

def validate_assets(raw,manifest):
 if not 64<=len(raw)<=LIMIT-OFFSET:raise ValueError('Editor blob outside reserved partition')
 magic,version,count,size,crc,digest=struct.unpack('<8sIIII32s8x',raw[:64])
 if magic!=b'MBP4AS1\0' or version!=1 or size!=len(raw)-64:raise ValueError('Invalid editor header')
 if zlib.crc32(raw[64:])!=crc or hashlib.sha256(raw[64:]).digest()!=digest:raise ValueError('Editor content hash mismatch')
 if len(raw)!=manifest['bytes'] or hashlib.sha256(raw).hexdigest()!=manifest['sha256'] or count!=manifest['files']:raise ValueError('Editor manifest mismatch')
 if int(manifest['offset'],16)!=OFFSET or manifest['partition_bytes']!=LIMIT-OFFSET:raise ValueError('Unexpected editor destination')
 return {'bytes':len(raw),'sha256':manifest['sha256'],'offset':hex(OFFSET),'end_exclusive':hex(OFFSET+len(raw))}

if __name__=='__main__':
 from p4_serial import require_com5
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--layout',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute and current P4 flash authorization required')
 require_com5();raw=a.assets.read_bytes();manifest=json.loads(a.assets.with_name('assets-manifest.json').read_text());report=validate_assets(raw,manifest)
 layout=json.loads(a.layout.read_text())
 if layout.get('result')!='PASS' or layout.get('overlap') is not False or layout['assets_bytes']!=len(raw) or layout.get('assets_sha256')!=report['sha256']:raise ValueError('Complete linked layout check required for these exact assets')
 cmd=[sys.executable,'-m','esptool','--chip','esp32p4','--port','COM5','--baud','921600','--before','default-reset','--after','hard-reset','write-flash','--flash-size','32MB','--flash-mode','dio','--flash-freq','80m',hex(OFFSET),str(a.assets.resolve())]
 result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 output=re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b','<redacted>',result.stdout+result.stderr)
 print('\n'.join(line for line in output.splitlines() if line.strip() and not line.startswith('Writing at ')))
 report.update(tested_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),target='COM5 P4 editor partition only',exit_code=result.returncode,hash_verified='Hash of data verified' in output and result.returncode==0,application_or_settings_written=False,C6_flashed=False,backup_performed=False,COM12_accessed=False)
 a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');sys.exit(result.returncode)
