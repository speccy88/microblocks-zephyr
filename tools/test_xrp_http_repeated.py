#!/usr/bin/env python3
"""Bounded repeated physical XRP HTTP/VM checks; no browser or actuator access."""
# SPDX-License-Identifier: MPL-2.0
import argparse,hashlib,http.client,ipaddress,json,time
from datetime import datetime,timezone
from pathlib import Path
from test_xrp_wireless import XRPWirelessVM

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True);p.add_argument('--source-commit',required=True)
    p.add_argument('--evidence',required=True,type=Path)
    args=p.parse_args();ipaddress.IPv4Address(args.host)
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),source_commit=args.source_commit,
        host=args.host,scope='30 fresh HTTP status connections at one-second intervals, three root HTML reads and three real WebSocket version/ping reconnects',
        checks=[],actuator_commands_sent=False,motor_supply_enabled=False,vm_code_modified=False)
    expected_root=None
    try:
        for i in range(30):
            start=time.monotonic();c=http.client.HTTPConnection(args.host,timeout=5)
            try:
                c.request('GET','/api/status',headers={'Connection':'close'})
                with c.getresponse() as r:
                    assert r.status==200;status=json.loads(r.read(512))
                assert status['board']=='xrp-rp2350' and status['state']=='connected'
                assert status['actuators_enabled'] is False and status.get('radio_pm')==0
                record=dict(index=i+1,http_status=True,seconds=round(time.monotonic()-start,3),radio_pm=status['radio_pm'],rssi_dbm=status['rssi_dbm'])
            finally:c.close()
            if i in (0,14,29):
                c=http.client.HTTPConnection(args.host,timeout=8)
                try:
                    c.request('GET','/',headers={'Connection':'close'})
                    with c.getresponse() as r:
                        assert r.status==200 and r.headers.get('Content-Type','').split(';')[0]=='text/html'
                        body=r.read(65536);digest=hashlib.sha256(body).hexdigest()
                    if expected_root is None:expected_root=digest
                    assert digest==expected_root
                    record['root_html_sha256']=digest
                finally:c.close()
                time.sleep(.1);vm=XRPWirelessVM(args.host)
                try:
                    start_event=len(vm.events);vm.short(26,97);vm.wait(lambda e:e[:2]==(26,97),after=start_event)
                    record['wireless_version_and_ping']=True
                finally:vm.close()
            report['checks'].append(record)
            args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
            time.sleep(1)
        report['result']='PASS'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc);raise
    finally:
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))

if __name__=='__main__':main()
