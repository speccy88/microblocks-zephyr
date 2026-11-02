"""Self-contained genuine MicroBlocks project; microphone off until manual start."""
from common import PROJECT
MAIN="""module main

script 20 20 {
    whenStarted
    voiceEyesInitialize
    sayIt 'Voice eye state ready. Click start voice commands to enable the microphone.'
}

script 20 150 {
    p4StartVoiceCommands
}

script 20 230 {
    '[p4:voiceStop]'
}

script 380 20 {
    p4WhenVoiceCommand
    voiceEyesApply ('[p4:voiceCommand]')
    sayIt ('[p4:voiceCommand]')
}

script 380 180 {
    sayIt (voiceEyesGazeX)
    sayIt (voiceEyesGazeY)
    sayIt (voiceEyesMood)
}

script 380 350 {
    sayIt ('[p4:voiceStatus]')
}

"""
def run():
 libs=[PROJECT.parent/'boards/waveshare_esp32p4_wifi6/integration/P4_Voice_Commands.ubl',
       PROJECT/'esp32p4/microblocks/Voice_Eyes.ubl',
       PROJECT.parent/'boards/waveshare_esp32p4_wifi6/integration/Robot_Eyes.ubl']
 out=PROJECT/'esp32p4/microblocks/voice-commands-eyes.ubp'
 out.write_text(MAIN+'\n'.join(p.read_text() for p in libs));print(out)
if __name__=='__main__':run()
