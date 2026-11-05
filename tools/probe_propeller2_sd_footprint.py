#!/usr/bin/env python3
"""Compile-only SD/FAT footprint probe in a fresh private source copy; never flash."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def probe(compiler,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    source=output/'source'
    shutil.copytree(ROOT/'boards/propeller2/native',source/'boards/propeller2/native')
    (source/'tools').mkdir()
    shutil.copy2(ROOT/'tools/build_propeller2.py',source/'tools/build_propeller2.py')
    path=source/'boards/propeller2/native/propeller2/p2Files.c'
    text=path.read_text(encoding='utf-8')
    if text.count('static PrimEntry entries[]={')!=1:
        raise ValueError('Review changed file primitive table before probing')
    text=text.replace('#include <dirent.h>','#include <dirent.h>\n#include <sys/vfs.h>')
    text=text.replace('static PrimEntry entries[]={','''static OBJ sdFootprintProbe(int argc,OBJ *args) {
    if(argc!=4)return falseObj;
    return _vfs_open_sdcardx(obj2int(args[0]),obj2int(args[1]),obj2int(args[2]),obj2int(args[3]))?trueObj:falseObj;
}
static PrimEntry entries[]={
    {"sdFootprintProbe",sdFootprintProbe},''')
    path.write_text(text,encoding='utf-8',newline='\n')
    command=[sys.executable,str(source/'tools/build_propeller2.py'),'--flexcc',str(Path(compiler).resolve()),
             '--board','edge32','--output',str(output/'build')]
    run=subprocess.run(command,capture_output=True,text=True)
    binary=output/'build/vm_propeller2_edge32.bin'
    report={'compile_only':True,'not_installable':True,'repository_native_sources_changed':False,
            'hardware_access':False,'build_exit_code':run.returncode,'minimum_stack_bytes':16384,
            'link_probe_only':'No pin validation, filesystem policy, responsiveness or hardware acceptance; never install this stub.',
            'log':(run.stdout+run.stderr)[-1800:]}
    if binary.exists():
        report.update(bytes=binary.stat().st_size,sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                      stack_gap_bytes=512*1024-binary.stat().st_size)
    (output/'probe.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flexcc',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='New output directory; existing paths are refused')
    args=parser.parse_args();print(json.dumps(probe(args.flexcc,args.output)))
