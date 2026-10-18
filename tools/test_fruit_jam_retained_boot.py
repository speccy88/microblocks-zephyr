#!/usr/bin/env python3
"""Bounded physical retained-association and HTTP timeout acceptance; no credentials."""
# SPDX-License-Identifier: MIT
from pathlib import Path
from datetime import datetime,timezone
import json,socket,time,urllib.request,hashlib,gzip
import argparse
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',required=True);p.add_argument('--evidence',type=Path,required=True);args=p.parse_args()
assert args.host=='192.168.1.7','This acceptance is scoped to the identified Fruit Jam association'
r=Path(__file__).resolve().parents[1];ev=r/'evidence/2026-10-18/fruit-jam'
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def status():
 with opener.open('http://192.168.1.7/api/status',timeout=4) as response:return json.load(response)
start=time.monotonic();deadline=start+30
while True:
 try:initial=status();break
 except (OSError,ValueError):
  if time.monotonic()>deadline:raise
  time.sleep(.2)
a=initial['airlift'];assert a['network_ready'] and a['generation']==1 and a['operation']==0 and not a['reset_requested'],initial
assert a['mac']=='58:e6:c5:f5:a3:58' and a['version']=='3.3.0'
probes=[]
for name,payload,field in [('idle_preconnection',b'','idle'),('partial_http_header',b'GET /api/status HTTP/1.1\r\nHost: 192.168.1.7\r\n','request')]:
 before=status()['network']['timeouts'];s=socket.create_connection(('192.168.1.7',80),timeout=3);s.settimeout(8)
 if payload:s.sendall(payload)
 began=time.monotonic();data=s.recv(1);elapsed=time.monotonic()-began;s.close()
 assert data==b'' and 4.5<elapsed<8,(name,elapsed,data)
 after=status()['network']['timeouts'];assert after[field]==before[field]+1 and after['state']==1 and after['bytes']==len(payload),(before,after)
 probes.append({'case':name,'elapsed_seconds':round(elapsed,3),'received_bytes':len(data),'before':before,'after':after})
result={'result':'PASS','checked_utc':datetime.now(timezone.utc).isoformat(),'source_commit':json.loads((ev/'network-build-verification.json').read_text())['compiled_source_commit'],'scope':'Automatic retained-association initialization after RP-only reset, no explicit identify or join, and bounded controlled HTTP timeout classification','initial_status':initial,'probes':probes,'credentials_read':False,'join_submitted':False,'coprocessor_reset':False,'human_observation_requested':False}
args.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result,indent=2))
