#!/usr/bin/env python3
"""Flash revision-guarded native Zephyr simple-boot image to COM5 only."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
from serial.tools import list_ports
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Current user authorization and --execute are required')
 ports=[x for x in list_ports.comports() if x.device.upper()=='COM5']
 if len(ports)!=1 or (ports[0].vid,ports[0].pid)!=(0x1a86,0x55d3):raise RuntimeError('COM5 CH343 identity mismatch')
 raw=a.image.read_bytes()
 if raw[0]!=0xe9 or struct.unpack_from('<H',raw,12)[0]!=18 or struct.unpack_from('<HH',raw,15)!=(103,199):raise RuntimeError('Expected guarded pre-v3 native P4 image')
 cmd=[sys.executable,'-m','esptool','--chip','esp32p4','--port','COM5','--baud','460800','--before','default-reset','--after','hard-reset','write-flash','--flash-size','32MB','--flash-mode','dio','--flash-freq','80m','0x2000',str(a.image.resolve())]
 r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 output=re.sub(r'(?i)\b(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\b','<redacted>',r.stdout+r.stderr);print(output)
 report={'runtime':'native Zephyr','target':'COM5 ESP32-P4 revision 1.3','offset':'0x2000','image_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'minimum_revision':'1.3','maximum_revision':'1.99','exit_code':r.returncode,'hash_verified':'Hash of data verified' in output and not r.returncode,'backup_performed':False,'COM12_accessed':False}
 a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
 sys.exit(r.returncode)
