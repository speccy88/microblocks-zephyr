#!/usr/bin/env python3
"""XRP MBNW v2 frame guards and reviewed upstream encoder initialization fixes.

Runs after prepare_smallvm in an isolated build copy. Shared preparation and
other board sources remain unchanged. No code execution or hardware access.
"""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import argparse
from prepare_smallvm import replace_once

def prepare_runtime(folder):
    path=Path(folder)/'vm/runtime.c'
    text=path.read_text(encoding='utf-8')
    text='#include "network_setup.h"\n'+text
    text=replace_once(text,
      '\tif (!rcvByteCount || !receiveTimeout()) return;',
      '\tif (!rcvByteCount || !receiveTimeout()) return;\n'
      '\tif (rcvByteCount >= 2 && rcvBuf[0] == 251 && rcvBuf[1] == 205) {\n'
      '\t\tmbnw_clear(rcvBuf, sizeof(rcvBuf)); rcvByteCount = 0; return;\n\t}')
    text=replace_once(text,'static void processLongMessage() {',
      'static void processLongMessage() {\n'
      '\tif (rcvByteCount >= 5 && rcvBuf[1] == 205) {\n'
      '\t\tunsigned setupLength = ((unsigned)rcvBuf[4] << 8) | rcvBuf[3];\n'
      '\t\tif (setupLength < 1 || setupLength > MBNW_MAX_REQUEST + 1 ||\n'
      '\t\t    (rcvByteCount >= 5 + setupLength && rcvBuf[5 + setupLength - 1] != 254)) {\n'
      '\t\t\tmbnw_clear(rcvBuf, sizeof(rcvBuf)); rcvByteCount = 0; return;\n\t\t}\n\t}')
    text=replace_once(text,' outBufStart=outBufEnd=0; rcvByteCount=0;',
      ' mbnw_clear(rcvBuf, sizeof(rcvBuf)); outBufStart=outBufEnd=0; rcvByteCount=0;')
    path.write_text(text,encoding='utf-8',newline='\n')
    encoder=Path(folder)/'vm/encoderPrims.cpp'
    code=encoder.read_text(encoding='utf-8')
    code=replace_once(code, 'if (pinA >= 0) detachInterrupt', 'if (pinA != 255) detachInterrupt')
    code=replace_once(code, 'if (pinB >= 0) detachInterrupt', 'if (pinB != 255) detachInterrupt')
    # Prevent a phantom first edge when a wheel starts at a high encoder phase.
    code=replace_once(code, 'this->prevStateA = false;', 'this->prevStateA = digitalRead(pinA);')
    code=replace_once(code, 'this->prevStateB = false;', 'this->prevStateB = digitalRead(pinB);')
    # The ISR must not see stale pin numbers while a counter is initialized.
    code=replace_once(code, '\t\tattachInterrupt(interruptA, handler, CHANGE);\n\t\tif (fullRes) attachInterrupt(interruptB, handler, CHANGE);',
                     '\t\tunsigned irq_key = irq_lock();')
    code=replace_once(code, '\t\tthis->fullRes = fullRes;\n\t\treturn 0;',
                     '\t\tthis->fullRes = fullRes;\n'
                     '\t\tattachInterrupt(interruptA, handler, CHANGE);\n'
                     '\t\tif (fullRes) attachInterrupt(interruptB, handler, CHANGE);\n'
                     '\t\tirq_unlock(irq_key);\n\t\treturn 0;')
    code='#include <zephyr/irq.h>\n'+code
    encoder.write_text(code,encoding='utf-8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('prepared',type=Path)
    prepare_runtime(parser.parse_args().prepared)
