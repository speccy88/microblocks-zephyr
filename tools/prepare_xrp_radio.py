#!/usr/bin/env python3
"""Verify/fetch only the two pinned CYW43439 build blobs; never access a board.

The Infineon blob EULA remains in the external HAL and licenses/. No blob or
complete firmware image is published by this script. --fetch is explicit.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import yaml

REVISION = '2191db4d7723737ffd3d59d01b50f7595dac2944'
BLOBS = {
    'img/whd/resources/firmware/COMPONENT_43439/43439A0.bin': 'bf545b5e5796e7f9348ec4a77f87d25e557ab97378dc2046a99e70997d2e1ca8',
    'img/whd/resources/clm/COMPONENT_43439/COMPONENT_MURATA-1YN/43439A0.clm_blob': '07bc4851449db809ce154ff79194a36cc6a2f7015c8b80b4073b5aa6f862ccb6',
}

def prepare(root, fetch=False):
    root = root.resolve()
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != REVISION:
        raise ValueError('Use the Zephyr-pinned Infineon HAL revision')
    metadata = yaml.safe_load((root/'zephyr/module.yml').read_text())
    selected = {b['path']: b for b in metadata['blobs'] if b['path'] in BLOBS}
    if set(selected) != set(BLOBS):
        raise ValueError('Missing expected CYW43439 blob metadata')
    report = []
    for name, digest in BLOBS.items():
        entry = selected[name]
        if entry['sha256'] != digest or not entry['url'].startswith('https://github.com/Infineon/'):
            raise ValueError('Changed blob source/hash')
        target = root/'zephyr/blobs'/name
        if not target.exists() and fetch:
            data = urllib.request.urlopen(entry['url'], timeout=60).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('Downloaded blob hash mismatch')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('Blob missing or changed: '+name)
        report.append(dict(path=name, sha256=digest, url=entry['url'], version=entry['version'], bytes=target.stat().st_size))
    license_file = root/'zephyr/blobs/license.txt'
    return dict(hal_revision=revision, blobs=report,
                license_sha256=hashlib.sha256(license_file.read_bytes()).hexdigest(),
                board_access=False, binaries_committed=False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hal', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    report = prepare(args.hal, args.fetch)
    text = json.dumps(report, indent=2)+'\n'
    if args.evidence:
        args.evidence.write_text(text, encoding='utf-8', newline='\n')
    print(text)
