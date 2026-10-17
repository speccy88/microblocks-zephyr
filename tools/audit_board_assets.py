#!/usr/bin/env python3
"""Verify actual board HTTP assets against the generated build manifest."""
# SPDX-License-Identifier: MIT
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import time
from pathlib import Path
import urllib.parse
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--host',required=True)
parser.add_argument('--manifest',type=Path,required=True)
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--workers',type=int,default=4)
args=parser.parse_args()
manifest=json.loads(args.manifest.read_text())
base='http://'+args.host

def verify(asset):
    started=time.monotonic()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url=base+urllib.parse.quote(asset['path'],safe='/')
    with opener.open(url,timeout=20) as response:
        assert urllib.parse.urlsplit(response.geturl()).netloc==args.host,'Off-board redirect'
        encoded=response.read()
        assert response.headers.get('Content-Encoding','')==asset['encoding'],'Content encoding mismatch'
        assert response.headers.get_content_type()==asset['content_type'],'MIME mismatch'
        raw=gzip.decompress(encoded) if asset['encoding']=='gzip' else encoded
        assert hashlib.sha256(raw).hexdigest()==asset['sha256'],'Asset content mismatch'
        csp=response.headers.get('Content-Security-Policy','')
        assert "connect-src 'self' ws://"+args.host in csp,'Missing board-only connection policy'
        assert response.headers.get('Cross-Origin-Opener-Policy')=='same-origin'
    return {'path':asset['path'],'bytes':len(raw),'sha256':asset['sha256'],
        'seconds':round(time.monotonic()-started,3)}

report={'host':args.host,'scope':'HTTP asset/content-policy verification; no graphical UI interaction',
    'workers':args.workers,'result':'FAIL'}
def checked(asset):
    try:return verify(asset)
    except Exception as exc:return {'path':asset['path'],'error':type(exc).__name__+': '+str(exc)}
try:
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    until=time.monotonic()+30
    while True:
        try:
            with opener.open(base+'/api/status',timeout=2) as response:assert json.loads(response.read())['vm']==417
            break
        except Exception:
            if time.monotonic()>until:raise
            time.sleep(.5)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:results=list(pool.map(checked,manifest['assets']))
    failed=[x for x in results if 'error' in x]
    report.update(result='FAIL' if failed else 'PASS',verified_assets=len(results)-len(failed),failed_assets=failed,
        uncompressed_bytes=sum(x.get('bytes',0) for x in results),assets=results)
finally:
    args.evidence.parent.mkdir(parents=True,exist_ok=True)
    args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='assets'},indent=2))
if report['result']!='PASS':raise SystemExit(1)
