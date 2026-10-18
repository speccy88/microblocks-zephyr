#!/usr/bin/env python3
"""Fruit Jam-only fail-closed/wiping guards for the private setup envelope.

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
    text='#include "wifi_control.h"\n'+text
    text=replace_once(text,
      '\tif (!rcvByteCount || !receiveTimeout()) return;',
      '\tif (!rcvByteCount || !receiveTimeout()) return;\n'
      '\tif (rcvByteCount >= 2 && rcvBuf[0] == 251 && rcvBuf[1] == FJ_WIFI_MESSAGE) {\n'
      '\t\tfj_secure_clear(rcvBuf, sizeof(rcvBuf)); rcvByteCount = 0; return;\n\t}')
    text=replace_once(text,'static void processLongMessage() {',
      'static void processLongMessage() {\n'
      '\tif (rcvByteCount >= 5 && rcvBuf[1] == FJ_WIFI_MESSAGE) {\n'
      '\t\tunsigned setupLength = ((unsigned)rcvBuf[4] << 8) | rcvBuf[3];\n'
      '\t\tif (setupLength < 1 || setupLength > FJ_WIFI_MAX_REQUEST + 1 ||\n'
      '\t\t    (rcvByteCount >= 5 + setupLength && rcvBuf[5 + setupLength - 1] != 254)) {\n'
      '\t\t\tfj_secure_clear(rcvBuf, sizeof(rcvBuf)); rcvByteCount = 0; return;\n\t\t}\n\t}')
    text=replace_once(text,' outBufStart=outBufEnd=0; rcvByteCount=0;',
      ' fj_secure_clear(rcvBuf, sizeof(rcvBuf)); outBufStart=outBufEnd=0; rcvByteCount=0;')
    path.write_text(text,encoding='utf-8',newline='\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('prepared',type=Path)
    prepare_runtime(parser.parse_args().prepared)
