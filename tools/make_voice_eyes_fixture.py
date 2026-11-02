#!/usr/bin/env python3
"""Reuse the actual project functions in a microphone-off native GP fixture."""
# SPDX-License-Identifier: MIT
import argparse
from pathlib import Path

CASES=[
    ('UP.','up',500,0,0),('down','down',500,1000,0),
    ('Go, LEFT!','left',0,500,0),('RIGHT','right',1000,500,0),
    ('angry','angry',1000,500,2),('happy','happy',1000,500,3),
    ('tired','tired',1000,500,1),('normal','normal',1000,500,0),
    ('Please be HAPPY!','happy',1000,500,3),
    ('cup upload bright abnormal tiredness','',1000,500,3),
    ('','',1000,500,3),('nothing recognised','',1000,500,3),
    ('left happy','left',0,500,3),('normal down','normal',0,500,0),
    ('lookup','',0,500,0),('look up','up',500,0,0),
    ('download upright outright unhappy','',500,0,0),
    ('tiredhappy','',500,0,0),('angry? okay','angry',500,0,2),
    ('UP down','up',500,0,2),('normal.','normal',500,0,0)]

def make(root, suite='mapping'):
    source=(root/'boards/waveshare_esp32p4_wifi6/integration/voice-eyes.ubp').read_text()
    prefix=source.split('\nscript ',1)[0]
    prefix=prefix.replace('voiceStopRequested\n','voiceStopRequested voiceTestsPassed voiceTestsFailed voiceTestSummary\n',1)
    if suite == 'microphone':
        prefix = prefix.replace('voiceTestSummary\n', 'voiceTestSummary voiceFirstCommand voiceFirstPhase voiceFirstChars voiceFirstText voiceBeforePause\n', 1)
        # Reuse Listen once unmodified, including its fixed 2.5 second window.
        # A known local speaker word is played during the first window. The
        # second window is deliberately paused while capture is in progress.
        script = """script 20 30 {
    whenStarted
    voiceInitialize
    eyesLook 'left'
    eyesMood 'angry'
    voiceTestsPassed = 0
    voiceTestsFailed = 0
    waitMillis 5000
    voiceListenOnce
    voiceFirstCommand = voiceCommand
    voiceFirstPhase = (jsonGet ('[p4:sttStatus]') '/phase')
    voiceFirstChars = (size voiceTranscript)
    voiceFirstText = voiceTranscript
    if (and (voiceCommand == 'happy') (and ((jsonGet ('[eyes:settings]') '/x') == '0') ((jsonGet ('[eyes:settings]') '/mood') == '3'))) {
        voiceTestsPassed += 1
    } else { voiceTestsFailed += 1 }
    voiceBeforePause = ('[eyes:settings]')
    sendBroadcast 'pause second voice capture'
    voiceListenOnce
    waitMillis 500
    if (and (voiceBusy == false) (and (voiceRepeatEnabled == false) (and (not ('[p4:sttBusy]')) (and (('[p4:audioCount]') == 0) (('[eyes:settings]') == voiceBeforePause))))) {
        voiceTestsPassed += 1
    } else { voiceTestsFailed += 1 }
    voiceTestSummary = 'VOICE_TESTS_FAILED'
    if (voiceTestsFailed == 0) { voiceTestSummary = 'VOICE_TESTS_PASSED' }
    sayIt voiceTestSummary
}
script 20 500 {
    whenBroadcastReceived 'pause second voice capture'
    waitMillis 1100
    voiceListenOnce
    waitMillis 400
    voicePause
}
""".splitlines()
    else:
        script=['script 20 30 {','    whenStarted','    voiceInitialize','    voiceTestsPassed = 0','    voiceTestsFailed = 0',"    sendBroadcast 'voice test 0'",'}']
    for index,(text,command,x,y,mood) in enumerate(CASES if suite == 'mapping' else []):
        assert "'" not in text
        script += [f'script {20+(index%3)*420} {180+(index//3)*280} {{',f"    whenBroadcastReceived 'voice test {index}'",f"    voiceCommand = (voiceApplyTranscript '{text}')",
                   f"    if (and (voiceCommand == '{command}') (and ((jsonGet ('[eyes:settings]') '/x') == '{x}') (and ((jsonGet ('[eyes:settings]') '/y') == '{y}') ((jsonGet ('[eyes:settings]') '/mood') == '{mood}')))) {{",
                   '        voiceTestsPassed += 1','    } else {','        voiceTestsFailed += 1','    }',f"    sendBroadcast 'voice test {index+1}'",'}']
    if suite == 'mapping':
        script += ['script 20 2400 {',f"    whenBroadcastReceived 'voice test {len(CASES)}'","    voiceTestSummary = 'VOICE_TESTS_FAILED'",'    if (voiceTestsFailed == 0) {',"        voiceTestSummary = 'VOICE_TESTS_PASSED'",'    }','    waitMillis 350','    sayIt voiceTestSummary','}']
    # Use identical dependency modules and compiler; no separate matcher model.
    board=root/'boards/waveshare_esp32p4_wifi6/integration'
    libs=[board/'P4_Camera.ubl',board/'P4_Audio.ubl',board/'P4_Speech.ubl',board/'Robot_Eyes.ubl',board/'Person_Pose.ubl',root/'integration/JSON.ubl']
    return prefix+'\n\n'+'\n'.join(script)+'\n'+'\n'.join(p.read_text() for p in libs)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--suite',choices=['mapping','microphone'],default='mapping');a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(make(Path(__file__).resolve().parents[1],a.suite),encoding='utf-8');print(f'{a.suite} fixture; real production project functions reused')
