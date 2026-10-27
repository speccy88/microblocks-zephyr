#!/usr/bin/env python3
"""Run the pinned layout/startup probes natively in a new Pi user directory.

Requires already-authorized passwordless SSH and a verified saved host key.
Copies only source and tests, installs no package or service, uses no root, and
leaves its unique remote directory as reproducible evidence. Not a VM port.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from probe_smallvm_lp64 import COMMIT, FILES, ROOT


def command(args, *, data=None, timeout=90):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
    return result.stdout


def execute(upstream, target, output):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', target):
        raise ValueError('Use a configured SSH alias without shell syntax')
    ssh = shutil.which('ssh'); scp = shutil.which('scp')
    if not ssh or not scp:
        raise RuntimeError('OpenSSH ssh/scp clients are required')
    options = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    remote = 'microblocks-charlie/probes/lp64-' + stamp
    local = output / ('native-' + stamp)
    local.mkdir(parents=True, exist_ok=False)
    expected = {x['path']: x['sha256'] for x in json.loads((ROOT / 'dependencies/smallvm-v417.json').read_text())['files']}
    contents = {}; sources = {}
    for source, name in FILES.items():
        raw = command(['git', '-C', str(upstream), 'show', COMMIT + ':' + source])
        digest = hashlib.sha256(raw).hexdigest()
        if source in expected and digest != expected[source]:
            raise RuntimeError('Pinned source hash mismatch: ' + source)
        contents[name] = raw
        sources[name] = {'source': source, 'sha256': digest}
    for name in ('smallvm_lp64_probe.c', 'gp_lp64_reference_probe.c'):
        raw = (ROOT / 'tests' / name).read_bytes(); contents[name] = raw
        sources[name] = {'source': 'tests/' + name, 'sha256': hashlib.sha256(raw).hexdigest()}
    contents['source-manifest.json'] = (json.dumps({'commit': COMMIT, 'files': sources}, indent=2) + '\n').encode()
    archive = local / 'source.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for name, raw in sorted(contents.items()):
            entry = tarfile.TarInfo(name); entry.size = len(raw); entry.mode = 0o600
            bundle.addfile(entry, io.BytesIO(raw))
    setup = ('set -eu; test "$(uname -m)" = aarch64; test "$(id -u)" -ne 0; '
             'test ! -L "$HOME/microblocks-charlie"; test ! -L "$HOME/microblocks-charlie/probes"; '
             'mkdir -p "$HOME/microblocks-charlie/probes"; test ! -e "$HOME/' + remote + '"; mkdir "$HOME/' + remote + '"')
    command([ssh, *options, target, setup])
    command([scp, *options, str(archive), target + ':' + remote + '/source.tar.gz'])
    script = '''set -eu
cd "$HOME/REMOTE"
tar -xzf source.tar.gz
python3 - <<'PY'
import hashlib,json,pathlib,platform,subprocess
m=json.loads(pathlib.Path('source-manifest.json').read_text())
for name,meta in m['files'].items():
    assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==meta['sha256'], name
assert platform.machine()=='aarch64'
print(json.dumps({'host':subprocess.check_output(['hostname'],text=True).strip(),'machine':platform.machine(),'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],'source_hashes_verified':len(m['files']),'commit':m['commit']}))
PY
gcc -std=c11 -O0 -Wall -Wextra -march=armv8-a -I. smallvm_lp64_probe.c mem.c -o smallvm-lp64-probe >smallvm-build.log 2>&1
./smallvm-lp64-probe
printf '%s\n' '#include "mem.h"' '_Static_assert(sizeof(OBJ)==4,"SMALLVM_REQUIRES_32_BIT_OBJ");' >guard.c
if gcc -std=c11 -march=armv8-a -I. -c guard.c -o guard.o >guard.log 2>&1; then
    echo 'Unexpected compile-guard acceptance' >&2; exit 1
fi
grep -q SMALLVM_REQUIRES_32_BIT_OBJ guard.log
gcc -std=c11 -O0 -Wall -Wextra -march=armv8-a -I. gp_lp64_reference_probe.c -o gp-lp64-reference-probe >gp-build.log 2>&1
./gp-lp64-reference-probe
'''.replace('REMOTE', remote)
    raw = command([ssh, *options, '-T', target, 'sh -s'], data=script.encode())
    (local / 'stdout.txt').write_bytes(raw)
    observations = [json.loads(line) for line in raw.decode().splitlines() if line.startswith('{')]
    if len(observations) != 3 or observations[1]['result'] != 'EXPECTED_REJECTION' or observations[2]['result'] != 'PASS_REFERENCE_ONLY':
        raise RuntimeError('Unexpected native probe result; inspect retained stdout')
    for name in ('smallvm-build.log', 'guard.log', 'gp-build.log'):
        command([scp, *options, target + ':' + remote + '/' + name, str(local / name)])
    report = {'tested_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'remote_directory': remote, 'source_commit': COMMIT, 'sources': sources,
              'native_observations': observations, 'compile_guard_expected_rejection': True,
              'scope': 'Native AArch64 compilation and execution of layout/startup probes only; no SmallVM bytecode or functional VM',
              'service_or_package_changes': False, 'root_used': False}
    (local / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return local, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--target', default='rpi5')
    parser.add_argument('--output', type=Path, default=ROOT / 'build-artifacts/pi5-lp64-probe')
    args = parser.parse_args()
    folder, result = execute(args.upstream.resolve(), args.target, args.output.resolve())
    print(json.dumps({'evidence': str(folder / 'report.json'), 'native_observations': result['native_observations'], 'scope': result['scope']}, indent=2))
