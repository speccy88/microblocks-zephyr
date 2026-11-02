#!/usr/bin/env python3
"""Fetch immutable RoboEyes sources and their full license, outside Git."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def verify(directory, manifest):
    for item in manifest['files']:
        path = directory / item['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Changed RoboEyes source: ' + str(path))


def fetch(directory, manifest):
    for item in manifest['files']:
        path = directory / item['path']
        data = path.read_bytes() if path.exists() else urllib.request.urlopen(
            f"https://raw.githubusercontent.com/FluxGarage/RoboEyes/{manifest['commit']}/{item['path']}", timeout=30).read()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('RoboEyes SHA256 mismatch: ' + item['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    verify(directory, manifest)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=root/'build-artifacts/roboeyes')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((root/'dependencies/roboeyes.json').read_text())
    (verify if args.verify else fetch)(args.output, manifest)
    print('Verified RoboEyes ' + manifest['commit'] + ' (GPL-3.0-or-later)')
