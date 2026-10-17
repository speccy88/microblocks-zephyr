#!/usr/bin/env python3
"""Stage hash-verified SmallVM/IDE snapshots from the pinned UNO Q checkout."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('reference', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
reference, output = args.reference.resolve(), args.output.resolve()
project = Path(__file__).resolve().parents[1]
revision = subprocess.check_output(['git','-C',str(reference),'rev-parse','HEAD'],text=True).strip()
expected = '70690291ac44a5c3a50dce572ee0c29ba99dc57f'
if revision != expected:
    raise SystemExit('Reference checkout must match '+expected)
for manifest_name, folder, prefix_key in [('smallvm-v417.json','smallvm','mirror_prefix'),('ide-assets.json','ide','source_prefix')]:
    manifest_path = project/'dependencies'/manifest_name
    manifest = json.loads(manifest_path.read_text())
    destination = output/folder
    destination.mkdir(parents=True,exist_ok=True)
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe snapshot path')
        source = reference/manifest[prefix_key]/relative
        if source.is_symlink():raise ValueError('Snapshot symlinks are unsupported')
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:raise ValueError('Source hash mismatch: '+str(relative))
        target = destination/relative
        if target.exists() and target.read_bytes()!=data:raise ValueError('Refusing to overwrite different content: '+str(target))
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    (destination/'provenance.json').write_bytes(manifest_path.read_bytes())
    if folder=='smallvm':
        license_data=subprocess.check_output(['git','-C',str(reference),'show',expected+':sources/smallvm/LICENSE'])
        (destination/'LICENSE').write_bytes(license_data)
print('Verified snapshots staged: '+str(output/'smallvm')+' and '+str(output/'ide'))
