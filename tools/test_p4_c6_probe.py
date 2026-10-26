#!/usr/bin/env python3
"""Read bounded SDIO/header diagnostics on COM5; no RF or C6 firmware writes."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,time
from pathlib import Path
from p4_serial import P4SerialVM
def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'scope':'native C6 version and optional read-only MAC-query status; bounded headers/counters, no address output',
 'payloads_or_credentials_recorded':False,'C6_flashed':False,'AP_or_station_configured':False,'COM12_accessed':False}
 vm=None
 try:
  vm=P4SerialVM();report['firmware']=vm.version;report['companion']=json.loads(vm.call('c6Status'))
  report['first']=json.loads(vm.call('c6Trace',-1));time.sleep(2)
  report['second']=json.loads(vm.call('c6Trace',-1))
  report['headers']=[json.loads(vm.call('c6Trace',i)) for i in range(min(8,report['second'].get('valid_headers',0)))]
  report['protocol']=json.loads(vm.call('c6Trace',-2))
  report['request']=json.loads(vm.call('c6Trace',-3))
  report['private_tags']=[json.loads(vm.call('c6Trace',8+i)) for i in range(min(8,report['protocol'].get('tag_count',0)))]
  assert report['first'].get('enabled') is True,'Missing native trace profile'
  assert report['companion']['host_wifi_requests'] is False
  if a.read_control:
   assert vm.call('c6ReadOnlyProbe') is True
   began=time.monotonic();roundtrips=0
   while True:
    state=json.loads(vm.call('c6Trace',-4));roundtrips+=1
    if not state['busy']:break
    assert time.monotonic()-began<8,'Read-only query exceeded bounded deadline'
    time.sleep(.05)
   report['read_only_control']=state;report['vm_roundtrips_during_query']=roundtrips
   report['protocol_after_query']=json.loads(vm.call('c6Trace',-2))
   report['counters_after_query']=json.loads(vm.call('c6Trace',-1))
   report['companion_after_query']=json.loads(vm.call('c6Status'))
   report['control_responded']=state['reply_id']==513
  report['diagnostic_result']='PASS_READ';report['firmware_version_known']=bool(report['companion'].get('version_raw'));report['network_ready']=False
 except BaseException as e:report.update(diagnostic_result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--read-control',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute required for COM5 read')
 main(a)
