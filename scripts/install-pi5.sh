#!/bin/sh
# SPDX-License-Identifier: MPL-2.0
# Readable GitHub bootstrap. The immutable payload is verified before extraction
# or execution; see docs/PI5_INSTALLER.md for network and service options.
set -eu
command -v python3 >/dev/null 2>&1 || { echo 'Python 3.11+ is required.' >&2; exit 1; }
exec python3 -I -B - "$@" <<'PI5_BOOTSTRAP_PY'
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit

SOURCE_COMMIT = '4eaae9b3d88f167a6262753c7850577d39054973'
SOURCE_SHA256 = '9df8a9636c242d41739b29a73fa1c293988f1162ab53aaf8ab08111611b0bbd2'
SOURCE_URL = 'https://github.com/speccy88/microblocks-zephyr/archive/' + SOURCE_COMMIT + '.tar.gz'
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024

def download(url, target, expected, opener=urllib.request.urlopen):
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url, headers={'User-Agent': 'MicroBlocks-Pi5-Bootstrap/1'})
    with opener(request, timeout=45) as response, target.open('xb') as out:
        final = urlsplit(response.url)
        if final.scheme != 'https' or final.hostname not in ('github.com', 'codeload.github.com') or final.username or final.password:
            raise RuntimeError('Unexpected source download destination')
        while True:
            raw = response.read(1024 * 1024)
            if not raw:
                break
            size += len(raw)
            if size > MAX_ARCHIVE:
                raise RuntimeError('Source archive exceeds download bound')
            digest.update(raw)
            out.write(raw)
    if digest.hexdigest() != expected:
        raise RuntimeError('GitHub source SHA256 differs; nothing was extracted or executed')
    return size

def extract(archive, directory, commit):
    expected_root = 'microblocks-zephyr-' + commit
    directory.mkdir(mode=0o700)
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers()
        if not 1 <= len(members) <= 10000 or sum(m.size for m in members) > MAX_EXPANDED:
            raise RuntimeError('Source archive exceeds extraction bounds')
        seen = set()
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or not name.parts
                    or name.parts[0] != expected_root or '\\' in member.name
                    or any(ord(c) < 32 for c in member.name) or name in seen
                    or not (member.isdir() or member.isfile())
                    or member.size < 0 or member.size > 64 * 1024 * 1024):
                raise RuntimeError('Unsafe or duplicate source archive entry')
            seen.add(name)
        for member in members:
            path = directory / member.name
            if member.isdir():
                path.mkdir(parents=True, mode=0o700, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                with source.extractfile(member) as raw, path.open('xb') as out:
                    while True:
                        block = raw.read(1024 * 1024)
                        if not block:
                            break
                        out.write(block)
                path.chmod(0o600)
    root = directory / expected_root
    if not (root / 'tools/install_pi5.py').is_file():
        raise RuntimeError('Verified archive does not contain the Pi5 installer')
    return root

def main(arguments):
    if arguments == ['--bootstrap-info']:
        print(json.dumps({'source_commit': SOURCE_COMMIT, 'source_sha256': SOURCE_SHA256, 'source_url': SOURCE_URL}, indent=2))
        return 0
    if os.geteuid() == 0:
        raise RuntimeError('Use your ordinary account; do not pipe this script into sudo')
    if sys.version_info < (3, 11):
        raise RuntimeError('Python3.11+ is required')
    os.umask(0o077)
    print('Verified Pi5 source: ' + SOURCE_COMMIT + '\nSHA256: ' + SOURCE_SHA256, flush=True)
    with tempfile.TemporaryDirectory(prefix='microblocks-pi5-source-') as temporary:
        directory = Path(temporary)
        archive = directory / 'source.tar.gz'
        print('Downloading the pinned source from this project on GitHub...', flush=True)
        download(SOURCE_URL, archive, SOURCE_SHA256)
        root = extract(archive, directory / 'source', SOURCE_COMMIT)
        (root / '.pi5-bootstrap.json').write_text(json.dumps({'source_commit': SOURCE_COMMIT, 'source_sha256': SOURCE_SHA256}) + '\n')
        return subprocess.run([sys.executable, '-I', '-B', str(root / 'tools/install_pi5.py'), *arguments], stdin=subprocess.DEVNULL).returncode

if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, RuntimeError, tarfile.TarError) as error:
        raise SystemExit('Pi5 bootstrap stopped: ' + str(error))
PI5_BOOTSTRAP_PY
