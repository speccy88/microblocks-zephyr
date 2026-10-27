#!/usr/bin/env python3
"""Make a deterministic candidate package; packaging is not runtime acceptance.

Requires a separately built ELF64 AArch64 executable and the pinned SmallVM
source checkout. Does not compile, download, execute or publish the executable.
"""
# SPDX-License-Identifier: MIT
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile

SOURCE_COMMIT = '2071df569623ba9cdcd6f8106b61796e047df38b'


def package(binary, license_bytes, output, version, *, epoch=0):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version) or version == 'latest':
        raise ValueError('A pinned release version is required')
    if len(binary) < 64 or len(binary) > 32 * 1024 * 1024 or binary[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', binary, 18)[0] != 183:
        raise ValueError('Expected a little-endian ELF64 AArch64 executable under 32 MiB')
    manifest = {
        'version': version, 'architecture': 'linux-aarch64', 'vm_version': 417,
        'source_repository': 'https://codeberg.org/MicroBlocks/smallvm',
        'source_commit': SOURCE_COMMIT,
        'binary_sha256': hashlib.sha256(binary).hexdigest(),
        'acceptance': 'candidate; requires real Raspberry Pi execution evidence before release',
    }
    entries = {
        'smallvm': binary,
        'manifest.json': (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode(),
        'LICENSE': license_bytes,
        'NOTICE': b'SmallVM is MPL-2.0. Corresponding source: https://codeberg.org/MicroBlocks/smallvm at ' + SOURCE_COMMIT.encode() + b'.\nPort changes and build recipe must accompany a published release.\n',
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    checksum = output.with_name(output.name + '.sha256')
    if output.exists() or checksum.exists():
        raise FileExistsError('Refusing to overwrite existing candidate package')
    with output.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode='w', format=tarfile.USTAR_FORMAT) as bundle:
                for name in sorted(entries):
                    content = entries[name]
                    info = tarfile.TarInfo(name)
                    info.size = len(content); info.mtime = epoch
                    info.uid = info.gid = 0; info.uname = info.gname = ''
                    info.mode = 0o755 if name == 'smallvm' else 0o644
                    bundle.addfile(info, io.BytesIO(content))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum.write_text(f'{digest}  {output.name}\n', encoding='ascii')
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path, help='Official SmallVM Git checkout containing the pinned commit')
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    # Read from the exact Git revision, never mutable checkout bytes.
    license_bytes = subprocess.check_output(['git', '-C', str(args.source), 'show', SOURCE_COMMIT + ':LICENSE'])
    epoch = int(subprocess.check_output(['git', '-C', str(args.source), 'show', '-s', '--format=%ct', SOURCE_COMMIT], text=True).strip())
    digest = package(args.binary.read_bytes(), license_bytes, args.output, args.version, epoch=epoch)
    print(json.dumps({'candidate_package': str(args.output), 'sha256': digest, 'physically_tested': False}, indent=2))


if __name__ == '__main__':
    main()
