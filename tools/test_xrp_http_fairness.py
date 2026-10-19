#!/usr/bin/env python3
"""Physical HTTP fairness/keepalive/abort checks; no VM code or actuators."""
# SPDX-License-Identifier: MIT
import argparse,concurrent.futures,hashlib,http.client,ipaddress,json,socket,threading,time
from datetime import datetime,timezone
from pathlib import Path

class ExactReader:
    """Never prefetch bytes from the next keepalive response."""
    def __init__(self,sock):self.sock=sock
    def read(self,n=-1):
        if n<0:raise ValueError('Explicit read bound required')
        data=bytearray()
        while len(data)<n:
            part=self.sock.recv(n-len(data))
            if not part:break
            data.extend(part)
        return bytes(data)
    def readline(self,limit=65537):
        data=bytearray()
        while len(data)<limit:
            part=self.sock.recv(1)
            if not part:break
            data.extend(part)
            if part==b'\n':break
        return bytes(data)
    def close(self):pass  # The test owns the socket across both responses.
class ResponseSocket:
    def __init__(self,sock):self.sock=sock
    def makefile(self,*args,**kwargs):return ExactReader(self.sock)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True);p.add_argument('--assets',type=Path,required=True)
    p.add_argument('--source-commit',required=True);p.add_argument('--evidence',required=True,type=Path)
    p.add_argument('--pipeline',action='store_true',help='Optional advanced pipelining probe; default is sequential keepalive')
    args=p.parse_args();ipaddress.IPv4Address(args.host)
    assets={x['path']:x for x in json.loads(args.assets.read_text(encoding='utf8'))['assets']}
    large=assets['/gp_wasm.data'];small=assets['/TODO.md'];started=threading.Event()
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),source_commit=args.source_commit,
        host=args.host,checks={},request_mode='pipelined' if args.pipeline else 'sequential keepalive',scope='Physical XRP HTTP fairness, two responses and partial-download cleanup; no browser/VM code change',motor_supply_enabled=False,actuator_commands_sent=False)
    def status():
        begin=time.monotonic();c=http.client.HTTPConnection(args.host,timeout=10)
        try:
            c.request('GET','/api/status',headers={'Connection':'close'})
            with c.getresponse() as r:
                assert r.status==200;s=json.loads(r.read(512))
            assert s['board']=='xrp-rp2350' and s['state']=='connected' and s['radio_pm']==0
            return round(time.monotonic()-begin,3)
        finally:c.close()
    def transfer():
        begin=time.monotonic();sock=socket.create_connection((args.host,80),timeout=15);sock.settimeout(30)
        try:
            request=f'GET /gp_wasm.data HTTP/1.1\r\nHost: {args.host}\r\nAccept-Encoding: gzip\r\nConnection: keep-alive\r\n\r\n'.encode()
            next_request=f'GET /TODO.md HTTP/1.1\r\nHost: {args.host}\r\nAccept-Encoding: gzip\r\nConnection: close\r\n\r\n'.encode()
            sock.sendall(request+(next_request if args.pipeline else b''));wrapper=ResponseSocket(sock)
            first=http.client.HTTPResponse(wrapper);first.begin();assert first.status==200
            prefix=first.read(4096);assert len(prefix)==4096;started.set();time.sleep(1)
            body=prefix+first.read(large['flash_bytes']+1)
            assert len(body)==large['flash_bytes'] and hashlib.sha256(body).hexdigest()==large['flash_sha256']
            if not args.pipeline:sock.sendall(next_request)
            second=http.client.HTTPResponse(wrapper);second.begin();assert second.status==200
            body=second.read(small['flash_bytes']+1)
            assert len(body)==small['flash_bytes'] and hashlib.sha256(body).hexdigest()==small['flash_sha256']
            return dict(result='PASS',large_then_small_content_hashes=True,seconds=round(time.monotonic()-begin,3),large_compressed_bytes=large['flash_bytes'])
        finally:sock.close()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(transfer);assert started.wait(20),'Large response did not start'
            latencies=[];during=0
            for _ in range(8):
                running=not future.done();elapsed=status();latencies.append(elapsed)
                if running:during+=1
                assert elapsed<10,'Another client was starved by the large response'
                time.sleep(.3)
            report['checks']['status_during_large_transfer']=dict(result='PASS',latencies_seconds=latencies,probes_before_large_complete=during)
            assert during>0,'No actual overlapping transfer'
            report['checks']['large_then_small']=future.result(timeout=180)
        checks=[]
        for index in range(2):
            c=http.client.HTTPConnection(args.host,timeout=10)
            try:
                c.request('GET','/gp_wasm.data',headers={'Accept-Encoding':'gzip','Connection':'close'})
                r=c.getresponse();assert r.status==200,'Aborted resource holder not released'
                assert len(r.read(4096))==4096
                checks.append(dict(index=index+1,http_status=200,bytes_before_close=4096));r.close()
            finally:c.close()
            time.sleep(.3)
        report['checks']['aborted_resource_reusable']=checks
        report['checks']['status_after_aborts_seconds']=status();report['result']='PASS'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))

if __name__=='__main__':main()
