#!/usr/bin/env python3
"""Read actual GP fixture results over COM5 after disconnecting the editor."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
import re
from pathlib import Path
import time
from p4_serial import P4SerialVM
from pose_eyes import call

def main(a):
    vm=P4SerialVM(baudrate=921600)
    try:
        start=len(vm.events);vm.short(9);deadline=time.monotonic()+.5
        while time.monotonic()<deadline:vm.pump()
        names={event[2].decode('utf-8'):event[1] for event in vm.events[start:] if event[0]==29}
        def value(name):
            index=names[name];start=len(vm.events);vm.short(7,index)
            body=vm.wait(lambda e:e[:2]==(21,index),after=start)[2]
            if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
            if body[0]==2:return body[1:].decode('utf-8')
            if body[0]==3:return bool(body[1])
            raise ValueError('Unexpected variable type')
        report={'engine':'Actual GP 2.5.8 compiled code on native P4 SmallVM','suite':a.suite,
                'cases_passed':value('voiceTestsPassed'),'cases_failed':value('voiceTestsFailed'),
                'summary':value('voiceTestSummary'),'eye_state':json.loads(call(vm,'settings',primitive_set=26)),
                'microphone_used':a.suite=='microphone','audio_handles':vm.call('audioCount'),'inference_running':vm.call('sttBusy')}
        expected=21 if a.suite=='mapping' else 2
        if a.suite == 'microphone':
            report['first_command']=value('voiceFirstCommand')
            report['first_phase']=json.loads(value('voiceFirstPhase'))
            report['first_transcript_characters']=value('voiceFirstChars')
            tokens=re.findall('[a-z]+',value('voiceFirstText').lower())
            report['first_whistle_keyword']=next((s for s in tokens if s in ('up','down','left','right','angry','happy','tired','normal')),'')
        report['result']='PASS' if report['cases_passed']==expected and report['cases_failed']==0 and report['summary']=='VOICE_TESTS_PASSED' and report['audio_handles']==0 and not report['inference_running'] else 'FAIL'
        a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));assert report['result']=='PASS'
    finally:vm.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);p.add_argument('--suite',choices=['mapping','microphone'],default='mapping');a=p.parse_args()
    if not a.execute:p.error('--execute required')
    main(a)
