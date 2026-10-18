#!/usr/bin/env python3
"""Bounded streamed integrity/timing check of the real Fruit Jam IDE data asset."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,time,urllib.request,zlib
from datetime import datetime,timezone
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--host',required=True);p.add_argument('--manifest',type=Path,required=True)
p.add_argument('--evidence',type=Path,required=True);p.add_argument('--firmware-elf-sha256',required=True)
p.add_argument('--deadline',type=int,default=180);a=p.parse_args()
if not 20<=a.deadline<=300:p.error('deadline must be 20..300 seconds')
asset=next(x for x in json.loads(a.manifest.read_text())['assets'] if x['path']=='/gp_wasm.data')
r={'result':'FAIL','started_utc':datetime.now(timezone.utc).isoformat(),'host':a.host,'path':asset['path'],
   'firmware_elf_sha256':a.firmware_elf_sha256,'credentials_read':False,'coprocessor_reset':False,
   'scope':'Streamed real IDE data integrity and bounded progress; no graphical acceptance',
   'wire_bytes':0,'decoded_bytes':0,'progress':[],'deadline_seconds':a.deadline}
start=time.monotonic();digest=hashlib.sha256();wire_digest=hashlib.sha256();decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
try:
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://'+a.host+asset['path'],timeout=15) as response:
        assert response.status==200 and response.headers.get('Content-Encoding')=='gzip'
        assert int(response.headers['Content-Length'])==asset['flash_bytes']
        r['headers_seconds']=round(time.monotonic()-start,3)
        while True:
            if time.monotonic()-start>a.deadline:raise TimeoutError('Overall asset deadline exceeded')
            chunk=response.read1(16384)
            if not chunk:break
            wire_digest.update(chunk);r['wire_bytes']+=len(chunk)
            decoded=decoder.decompress(chunk);digest.update(decoded);r['decoded_bytes']+=len(decoded)
            if not r['progress'] or r['wire_bytes']-r['progress'][-1]['wire_bytes']>=262144:
                point={'seconds':round(time.monotonic()-start,3),'wire_bytes':r['wire_bytes']}
                r['progress'].append(point);print(json.dumps(point),flush=True)
        tail=decoder.flush();digest.update(tail);r['decoded_bytes']+=len(tail)
        assert decoder.eof and r['wire_bytes']==asset['flash_bytes'] and r['decoded_bytes']==asset['bytes']
        assert wire_digest.hexdigest()==asset['flash_sha256'] and digest.hexdigest()==asset['sha256']
        r['result']='PASS'
except Exception as exc:r['error']=type(exc).__name__+': '+str(exc)
finally:
    r.update(elapsed_seconds=round(time.monotonic()-start,3),finished_utc=datetime.now(timezone.utc).isoformat(),
      decoded_sha256=digest.hexdigest(),wire_sha256=wire_digest.hexdigest())
    a.evidence.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(r,indent=2))
raise SystemExit(0 if r['result']=='PASS' else 1)
