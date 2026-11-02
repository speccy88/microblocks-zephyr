#!/usr/bin/env python3
"""Explicit local speaker/P4 microphone Whistle test; no audio export."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
from pathlib import Path
import re
import time
from p4_serial import P4SerialVM
from pose_eyes import call

def main(a):
    import winsound
    vm=P4SerialVM(baudrate=921600);report={'microphone':'P4 ES8311','engine':'native P4 Whistle d4','controlled_word':'happy','audio_exported':False}
    clip=0
    try:
        vm.short(15);assert vm.call('sttAvailable') is True
        assert call(vm,'begin',64,0,60,primitive_set=26)
        call(vm,'mood',2,primitive_set=26);call(vm,'gaze',0,500,primitive_set=26)
        original=json.loads(call(vm,'settings',primitive_set=26))
        assert vm.call('cameraSettings',1156,195,3831)
        assert vm.call('audioRequest',2500);time.sleep(.45)
        winsound.PlaySound(str(a.word_wav.resolve()),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
        deadline=time.monotonic()+5
        while vm.call('audioBusy'):
            if time.monotonic()>deadline:raise TimeoutError('Recording')
            time.sleep(.04)
        winsound.PlaySound(None,0)
        clip=vm.call('audioResult');assert clip
        report['recording']={'frames':vm.call('audioFrames',clip),'peak':vm.call('audioPeak',clip),'rms':vm.call('audioRMS',clip)}
        assert vm.call('sttRequest',clip,0)
        assert vm.call('audioRelease',clip);clip=0
        started=time.monotonic();last='';roundtrips=0
        while vm.call('sttBusy'):
            state=json.loads(vm.call('sttStatus'))
            if state['phase']!=last:print('Whistle phase: '+state['phase'],flush=True);last=state['phase']
            roundtrips+=1
            if time.monotonic()-started>185:raise TimeoutError('Whistle bounded deadline')
            time.sleep(.1)
        state=json.loads(vm.call('sttStatus'));words=vm.call('sttResult')
        keywords=[w for w in re.findall('[a-z]+',words.lower()) if w in ('up','down','left','right','angry','happy','tired','normal')]
        report['inference']={**state,'first_keyword':keywords[0] if keywords else '', 'transcript_characters':len(words),'vm_roundtrips':roundtrips}
        assert state['buffers_released'] and state['phase']=='ready'
        assert state['stack_unused_bytes']>=8192
        after=json.loads(call(vm,'settings',primitive_set=26));assert all(original[k]==after[k] for k in ('x','y','mood'))
        report['inference_does_not_change_eye_state_by_itself']=True
        assert vm.call('audioRequest',300)
        while vm.call('audioBusy'):time.sleep(.02)
        clip=vm.call('audioResult');assert clip
        assert vm.call('sttRequest',clip,0);vm.call('audioRelease',clip);clip=0;vm.call('sttCancel')
        end=time.monotonic()+4
        while vm.call('sttBusy'):
            if time.monotonic()>end:raise TimeoutError('Whistle cancellation')
            time.sleep(.03)
        cancelled=json.loads(vm.call('sttStatus'));assert cancelled['buffers_released'];assert vm.call('sttResult')==''
        report['cancel_releases_buffers_and_clears_old_text']=True
        report['acoustic_keyword_result']='PASS' if keywords and keywords[0]=='happy' else 'NOT_CONFIRMED'
        report['result']='PASS_LIFECYCLE'
        print(json.dumps(report),flush=True)
    finally:
        winsound.PlaySound(None,0);vm.call('sttCancel')
        if clip:vm.call('audioRelease',clip)
        vm.call('audioReleaseAll');report['cleanup_audio_handles']=vm.call('audioCount')
        vm.close();a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--word-wav',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
    if not a.execute:p.error('--execute and current local audio-test authorization required')
    main(a)
