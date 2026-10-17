#!/usr/bin/env python3
"""Verify actual board HTTP assets against the generated build manifest."""
# SPDX-License-Identifier: MIT
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('--host',required=True)
parser.add_argument('--manifest',type=Path,required=True)
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
manifest=json.loads(args.manifest.read_text())
base='http://'+args.host

def verify(asset):
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
    return {'path':asset['path'],'bytes':len(raw),'sha256':asset['sha256']}

report={'host':args.host,'scope':'HTTP asset/content-policy verification; no graphical UI interaction','result':'FAIL'}
try:
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(verify,manifest['assets']))
    report.update(result='PASS',verified_assets=len(results),uncompressed_bytes=sum(x['bytes'] for x in results),assets=results)
finally:
    args.evidence.parent.mkdir(parents=True,exist_ok=True)
    args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='assets'},indent=2))
