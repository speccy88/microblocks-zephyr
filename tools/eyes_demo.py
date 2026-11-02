#!/usr/bin/env python3
"""SIMULATED face + arm events on the real OLED, without a camera/model."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
from pathlib import Path
import time
from face_tracker import demo_samples
from pose_eyes import call

def main(a):
    from p4_serial import P4SerialVM
    vm=P4SerialVM();began=time.monotonic();sequence=0;last=None;transitions=[]
    try:
        vm.short(15)
        if not call(vm,'begin',64,0,60,primitive_set=26):raise RuntimeError('OLED initialization rejected')
        call(vm,'follow',True,True,primitive_set=27)
        call(vm,'attention',True,2,primitive_set=27)
        print('SIMULATED INPUT: no camera capture or neural inference. Close the editor before this COM5-only demo.',flush=True)
        while not a.seconds or time.monotonic()-began<a.seconds:
            t=time.monotonic()-began;face,person=demo_samples(t);sequence+=1
            vm.send(person.packet(sequence));vm.send(face.packet(sequence));vm.pump();vm.events.clear()
            if sequence%5==1:
                state=call(vm,'attentionStatus',primitive_set=27)
                if state!=last:
                    row=dict(seconds=round(t,1),state=state,simulated_face=face.visible)
                    transitions.append(row);print(json.dumps(row),flush=True);last=state
            time.sleep(.10)
    except KeyboardInterrupt:pass
    finally:
        # Keep the native idle routine running after this demo; Stop All freezes it.
        call(vm,'cameraEnabled',False,primitive_set=27)
        vm.close()
        report=dict(input='SIMULATED',real_vision_tested=False,transitions=transitions,images_saved=False)
        if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--seconds',type=float,default=0);p.add_argument('--report',type=Path);a=p.parse_args()
    if not a.execute or a.seconds<0:p.error('Use --execute and nonnegative --seconds (0 runs until Ctrl+C)')
    main(a)
