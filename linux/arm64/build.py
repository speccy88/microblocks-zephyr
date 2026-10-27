#!/usr/bin/env python3
"""Prepare/build the pinned headless LP64 port; never install or publish it.

Run --source-only on Windows to stage verified C sources, then compile the
staged build.sh on an authorized Linux target. Native AArch64 uses ARMv8-A
baseline flags. Host builds are development tests, not ARM64 acceptance.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
from patch_core import patch_core
from patch_persist import patch_persist

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '2071df569623ba9cdcd6f8106b61796e047df38b'
CORE = ['interp.c', 'runtime.c', 'mem.c', 'persist.c', 'dataPrims.c', 'varPrims.c',
        'tinyJSON.c', 'mbFont.c', 'boardHooks.c']


def prepare(upstream, output, sanitize=False):
    if output.exists() and any(output.iterdir()) and not (output / '.linux-arm64-build').is_file():
        raise ValueError('Refusing a nonempty output directory not owned by this build')
    output.mkdir(parents=True, exist_ok=True)
    (output / '.linux-arm64-build').write_text('Pinned SmallVM Linux LP64 development build\n')
    lock = json.loads((ROOT / 'dependencies/smallvm-v417.json').read_text(encoding='utf-8'))
    if lock['canonical_commit'] != COMMIT:
        raise ValueError('Unsupported SmallVM pin')
    sources = {}
    for item in lock['files']:
        name = item['path']
        if not name.startswith('vm/') or '..' in Path(name).parts:
            raise ValueError('Unsafe pinned path')
        raw = subprocess.check_output(['git', '-c', 'safe.directory=' + str(upstream), '-C', str(upstream), 'show', COMMIT + ':' + name])
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Pinned source hash mismatch: ' + name)
        text = raw.decode('utf-8')
        if name == 'vm/persist.c':
            text = patch_persist(text)
        else:
            text = patch_core(Path(name).name, text)
        target = output / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8', newline='\n')
        sources[name] = {'upstream_sha256': item['sha256'], 'prepared_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    for path in sorted((ROOT / 'linux/arm64/runtime').glob('*')):
        if path.suffix not in ('.h', '.c'):
            continue
        target = output / 'vm' / path.name
        shutil.copyfile(path, target)
        sources.setdefault('vm/' + path.name, {}).update({'port_source': path.relative_to(ROOT).as_posix(), 'prepared_sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    platform_paths = sorted((ROOT / 'linux/arm64/platform').glob('*.c'))
    if not platform_paths:
        raise ValueError('Headless platform sources are not ready')
    for path in sorted((ROOT / 'linux/arm64/platform').glob('*')):
        if path.suffix not in ('.h', '.c'):
            continue
        target = output / 'platform' / path.name; target.parent.mkdir(exist_ok=True)
        shutil.copyfile(path, target)
        sources['platform/' + path.name] = {'port_source': path.relative_to(ROOT).as_posix(), 'prepared_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    license_bytes = subprocess.check_output(['git', '-c', 'safe.directory=' + str(upstream), '-C', str(upstream), 'show', COMMIT + ':LICENSE'])
    (output / 'LICENSE').write_bytes(license_bytes)
    json_lock = json.loads((ROOT / 'dependencies/json.json').read_text(encoding='utf-8'))
    if json_lock['commit'] != '6447536015f3d600f3d65323b10976103b337ca7':
        raise ValueError('Unsupported yyjson source pin')
    expected = {'third_party/yyjson/yyjson.c', 'third_party/yyjson/yyjson.h', 'third_party/yyjson/LICENSE'}
    if set(json_lock['files']) != expected:
        raise ValueError('Unexpected JSON dependency file set')
    for name, digest in json_lock['files'].items():
        raw = (ROOT / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Pinned JSON dependency changed: ' + name)
        target = output / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        sources[name] = {'dependency_repository': json_lock['source'], 'dependency_commit': json_lock['commit'],
                         'prepared_sha256': digest}
    name = 'common/json/json_config.h'
    target = output / name; target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / name, target)
    sources[name] = {'port_source': name, 'prepared_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    flags = ['-std=c11', '-O1' if sanitize else '-O2', '-g', '-Wall', '-Wextra',
             '-Werror=pointer-to-int-cast', '-Werror=int-to-pointer-cast',
             '-Werror=incompatible-pointer-types', '-Werror=int-conversion',
             '-DSMALLVM_LINUX_ARM64=1', '-Ivm', '-I.', '-include', 'common/json/json_config.h']
    if sanitize:
        flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    files = ['vm/' + name for name in CORE] + ['vm/arena.c', 'third_party/yyjson/yyjson.c'] + ['platform/' + p.name for p in platform_paths]
    # The architecture is checked on the actual build host, not the staging PC.
    shell = '#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nextra=\ncase "$(uname -m)" in aarch64) extra=-march=armv8-a;; esac\n'
    shell += '"${CC:-gcc}" $extra "-ffile-prefix-map=$PWD=." "-fdebug-prefix-map=$PWD=." ' + ' '.join(shlex.quote(x) for x in flags + files + ['-lm', '-o', 'smallvm']) + '\n'
    (output / 'build.sh').write_text(shell, encoding='utf-8', newline='\n')
    manifest = {'canonical_repository': lock['canonical_repository'], 'source_commit': COMMIT,
                'vm_version': 417, 'sources': sources, 'sanitize': sanitize,
                'scope': 'Development LP64 port; target functionality requires runtime acceptance'}
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-only', action='store_true')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()
    target = args.output.resolve()
    report = prepare(args.upstream.resolve(), target, args.sanitize)
    if not args.source_only:
        if platform.system() != 'Linux':
            raise SystemExit('Compile under Linux or use --source-only')
        subprocess.run(['sh', str(target / 'build.sh')], check=True)
        report['build_host'] = platform.machine()
        report['binary_sha256'] = hashlib.sha256((target / 'smallvm').read_bytes()).hexdigest()
        if args.test:
            subprocess.run([str(target / 'smallvm'), '--self-test'], check=True, timeout=30)
            report['self_test'] = 'PASS'
        (target / 'build-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'prepared': str(target), 'source_commit': COMMIT, 'compiled': not args.source_only, 'self_test': report.get('self_test', 'not run')}, indent=2))
