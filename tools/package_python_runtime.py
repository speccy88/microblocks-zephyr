#!/usr/bin/env python3
"""Portable source candidate for a private Linux acceptance run; installs nothing."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def package(prepared,editor,output):
    prepared,editor,output=map(Path,(prepared,editor,output))
    if output.exists():raise ValueError('Choose a fresh candidate archive')
    manifest_name='source-manifest.json'
    manifest=json.loads((prepared/manifest_name).read_text())
    addon=json.loads((editor/'python-extension-manifest.json').read_text())
    files={}
    for name,entry in manifest['sources'].items():
        p=prepared/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=entry['prepared_sha256']:raise ValueError('Prepared source changed: '+name)
        files['native/'+name]=p
    for name in ['build.sh','LICENSE',manifest_name]:
        files['native/'+name]=prepared/name
    for name,digest in addon['files'].items():
        p=editor/name
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Editor receipt changed: '+name)
        files['editor/'+name]=p
    files['editor/python-extension-manifest.json']=editor/'python-extension-manifest.json'
    for folder in ['linux/extensions','linux/microduck']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.json','.ubl','.ubp','.md'):files['code/'+p.relative_to(ROOT).as_posix()]=p
    for p in (ROOT/'linux/arm64').glob('*'):
        if p.is_file() and (p.suffix in ('.py','.sh') or p.name=='bridge-requirements.txt'):
            files['code/linux/arm64/'+p.name]=p
    receipt={'schema':1,'vm_source':manifest['source_commit'],'js_source':addon['source_commit'],'compiled_on_target':False,
        'files':{name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}}
    with tarfile.open(output,'w:gz') as archive:
        for name,p in sorted(files.items()):
            if p.is_symlink():raise ValueError('No candidate symlinks')
            raw=p.read_bytes();info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o600
            archive.addfile(info,io.BytesIO(raw))
        raw=(json.dumps(receipt,indent=2)+'\n').encode();info=tarfile.TarInfo('candidate.json');info.size=len(raw);info.mode=0o600
        archive.addfile(info,io.BytesIO(raw))
    return {'files':len(files),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'installs_or_starts_service':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['prepared','editor','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(package(a.prepared,a.editor,a.output)))
