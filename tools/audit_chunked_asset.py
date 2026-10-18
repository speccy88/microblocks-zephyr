#!/usr/bin/env python3
"""Verify real HTTP chunk framing/content with an optional slow reader.

Only requests a static IDE asset; no VM authentication or settings changes.
"""
# SPDX-License-Identifier: MIT
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import socket
import time
import urllib.parse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--path',default='/gp_wasm.wasm')
    parser.add_argument('--read-delay-ms',type=float,default=5)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    asset=next(a for a in json.loads(args.manifest.read_text())['assets'] if a['path']==args.path)
    report={'host':args.host,'path':args.path,'result':'FAIL','started_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Direct HTTP/1.1 response framing, bounded chunk size, hash/header checks and slow-reader behavior',
        'read_delay_ms':args.read_delay_ms}
    started=time.monotonic()
    try:
        with socket.create_connection((args.host,80),timeout=60) as connection:
            connection.settimeout(60)
            request='GET '+urllib.parse.quote(args.path,safe='/')+' HTTP/1.1\r\nHost: '+args.host+'\r\nConnection: close\r\nAccept-Encoding: gzip\r\n\r\n'
            connection.sendall(request.encode('ascii'))
            with connection.makefile('rb') as stream:
                status=stream.readline(512).decode('ascii').strip()
                assert status.split()[:2]==['HTTP/1.1','200'],status
                headers={}
                for _ in range(32):
                    line=stream.readline(2048)
                    if line==b'\r\n':break
                    assert line and b':' in line
                    name,value=line.decode('ascii').split(':',1)
                    assert name.lower() not in headers,'Duplicate response header: '+name
                    headers[name.lower()]=value.strip()
                else:raise AssertionError('Response header limit exceeded')
                assert headers['transfer-encoding'].lower()=='chunked'
                assert headers.get('content-encoding','')==asset['encoding']
                assert headers['content-type'].split(';')[0]==asset['content_type']
                assert "connect-src 'self' ws://"+args.host in headers['content-security-policy']
                assert headers['cross-origin-opener-policy']=='same-origin'
                chunks=[];encoded=bytearray()
                while True:
                    line=stream.readline(128)
                    assert line.endswith(b'\r\n'),'Incomplete chunk-length line'
                    size=int(line.split(b';',1)[0],16)
                    assert 0<=size<=2048,('Unbounded HTTP chunk',size)
                    if size==0:
                        assert stream.readline(2048)==b'\r\n','Unexpected/truncated trailer'
                        break
                    data=stream.read(size)
                    assert len(data)==size,'Truncated body chunk'
                    assert stream.read(2)==b'\r\n','Missing chunk delimiter'
                    encoded.extend(data);chunks.append(size)
                    assert len(encoded)<=asset['flash_bytes'],'More body bytes than expected'
                    time.sleep(max(0,args.read_delay_ms)/1000)
        raw=gzip.decompress(encoded) if asset['encoding']=='gzip' else bytes(encoded)
        assert len(encoded)==asset['flash_bytes']
        assert hashlib.sha256(raw).hexdigest()==asset['sha256'],'Decoded asset hash differs'
        assert len(chunks)==(len(encoded)+2047)//2048
        report.update(result='PASS',chunks=len(chunks),maximum_chunk_bytes=max(chunks,default=0),
            encoded_bytes=len(encoded),decoded_bytes=len(raw),sha256=asset['sha256'],
            seconds=round(time.monotonic()-started,3))
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
    finally:
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2))
    if report['result']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
