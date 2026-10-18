#!/usr/bin/env python3
"""Prepare a pinned official debugprobe copy for Pico 2 W; never flash a device.

The reviewed upstream only selects plain Pico/Pico 2. Enable the distinct W
board define and omit its GPIO25 status LED (GPIO25 is wireless CS on Pico 2 W).
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

COMMIT='262f9625d75a2bad8d76cc228ee5e21ca3a64d3a'
HASHES={
    'include/board_config.h':'94c515bfe1b365fe1c215bd404571bfe9f857d9104fe36b57d18a2309c120ef2',
    'include/board_pico_config.h':'0fe0239f57165af06001c1842c0da6564791dbc37e766d32bf36a2b524a95798',
    'get-version.sh':'422233b000d1111e1abea0d0c2a5eea6a3d9ebf7a8bf5714843d38f9722f497b',
}

def version_script(output):
    """Copied sources omit .git, so record deterministic reviewed provenance."""
    script=output/'get-version.sh'
    script.write_text('#!/bin/sh\n# SPDX-License-Identifier: MIT\n'
        'mkdir -p generated/probe\ncat > generated/probe/version.h <<\'EOF\'\n'
        '#ifndef _PROBE_VERSION_H\n#define _PROBE_VERSION_H\n'
        '#define PROBE_VERSION "262f9625-pico2w"\n#endif\nEOF\n',encoding='utf-8',newline='\n')
    script.chmod(script.stat().st_mode|0o111)

def prepare(source,output):
    source=source.resolve();output=output.resolve()
    if output.is_relative_to(source):raise ValueError('Output must be outside the upstream checkout')
    if output.exists():raise ValueError('Output must be a new directory; existing trees are never replaced')
    sha=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if sha!=COMMIT:raise ValueError('Unexpected debugprobe revision')
    # Windows-created checkouts may contain CRLF when reviewed from WSL.
    subprocess.run(['git','-c','core.autocrlf=true','-C',str(source),'diff','--quiet','HEAD','--'],check=True)
    if subprocess.check_output(['git','-C',str(source),'ls-files','--others','--exclude-standard'],text=True).strip():
        raise ValueError('Upstream checkout contains unreviewed untracked files')
    submodules=subprocess.check_output(['git','-C',str(source),'submodule','status','--recursive'],text=True)
    if any(line and line[0]!=' ' for line in submodules.splitlines()):
        raise ValueError('Initialize submodules at their pinned revisions before preparing sources')
    texts={}
    for name,digest in HASHES.items():
        text=(source/name).read_text(encoding='utf-8')
        if hashlib.sha256(text.encode()).hexdigest()!=digest:raise ValueError('Unreviewed source: '+name)
        texts[name]=text
    def replace(text,old,new):
        if text.count(old)!=1:raise ValueError('Unexpected patch anchor')
        return text.replace(old,new)
    texts['include/board_config.h']=replace(texts['include/board_config.h'],
        'defined(RASPBERRYPI_PICO) || defined(RASPBERRYPI_PICO2)',
        'defined(RASPBERRYPI_PICO) || defined(RASPBERRYPI_PICO2) || defined(RASPBERRYPI_PICO2_W)')
    texts['include/board_pico_config.h']=replace(texts['include/board_pico_config.h'],
        '#define PROBE_USB_CONNECTED_LED 25',
        '/* Pico 2 W GPIO25 selects the wireless chip; it is not a user LED. */\n'
        '#if !defined(RASPBERRYPI_PICO2_W)\n#define PROBE_USB_CONNECTED_LED 25\n#endif')
    texts['include/board_pico_config.h']=replace(texts['include/board_pico_config.h'],
        '#define PROBE_PRODUCT_STRING "Debugprobe on Pico (CMSIS-DAP)"',
        '#if defined(RASPBERRYPI_PICO2_W)\n'
        '#define PROBE_PRODUCT_STRING "Debugprobe on Pico 2 W (CMSIS-DAP)"\n#else\n'
        '#define PROBE_PRODUCT_STRING "Debugprobe on Pico (CMSIS-DAP)"\n#endif')
    shutil.copytree(source,output,ignore=shutil.ignore_patterns('.git','build','build-*'),symlinks=True)
    for name,text in texts.items():(output/name).write_text(text,encoding='utf-8',newline='\n')
    version_script(output)
    report=dict(upstream_commit=COMMIT,upstream='https://github.com/raspberrypi/debugprobe',
        source_hashes=HASHES,board='pico2_w',swd_gpio=dict(clock=2,data=3,reset=1),
        status_led_disabled=True,radio_used=False,physical_validation=False,deterministic_version='262f9625-pico2w',
        scope='Reviewed adaptation of official sources; not an official prebuilt Pico 2 W image')
    (output/'pico2w-provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.output),indent=2))
