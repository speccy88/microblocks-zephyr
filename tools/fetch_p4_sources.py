#!/usr/bin/env python3
"""Fetch only immutable manifest-listed SmallVM/editor files; verify every hash."""
# SPDX-License-Identifier: MIT
import argparse, concurrent.futures, hashlib, json, urllib.request
from pathlib import Path

def fetch(repo, output, local_vm=None):
    def one(job):
        name, url, target, digest, candidate = job
        data = target.read_bytes() if target.exists() else None
        if data is None and candidate and candidate.is_file(): data = candidate.read_bytes()
        if data is None: data = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Hash mismatch: '+name)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    for manifest_name, folder, prefix, revision in [
        ('smallvm-v417.json','smallvm','mirror_prefix','mirror_commit'),
        ('ide-assets.json','ide','source_prefix','source_commit')]:
        manifest = json.loads((repo/'dependencies'/manifest_name).read_text())
        base = 'https://raw.githubusercontent.com/speccy88/uno-q-microblocks/'+manifest[revision]+'/'+manifest[prefix]
        jobs=[]
        for entry in manifest['files']:
            path=Path(entry['path'])
            if path.is_absolute() or '..' in path.parts: raise ValueError('Unsafe path')
            candidate=local_vm/path if local_vm and folder=='smallvm' else None
            jobs.append((str(path),base+path.as_posix(),output/folder/path,entry['sha256'],candidate))
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(one,jobs))
        (output/folder/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
        if folder=='smallvm':
            data=(local_vm/'LICENSE').read_bytes() if local_vm and (local_vm/'LICENSE').is_file() else urllib.request.urlopen(base+'LICENSE',timeout=30).read()
            (output/folder/'LICENSE').write_bytes(data)
        print(folder+': verified '+str(len(jobs))+' files',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--local-vm',type=Path)
    a=p.parse_args();fetch(Path(__file__).resolve().parents[1],a.output,a.local_vm)
