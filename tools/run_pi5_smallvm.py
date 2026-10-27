#!/usr/bin/env python3
"""Stage the pinned LP64 sources and run real SmallVM tests on an authorized Pi.

Uses an existing verified SSH alias with BatchMode and strict host checking.
All remote writes stay in one fresh user-owned project directory. No package,
service, firewall, SSH configuration or existing program is changed.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'linux/arm64'))
from build import prepare, COMMIT


def run(args, data=None, timeout=90, check=True):
    result = subprocess.run(args, input=data, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
    return result


def execute(upstream, target, output, *, sanitize=False, repeats=50):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', target) or not 1 <= repeats <= 1000:
        raise ValueError('Use a configured SSH alias and 1..1000 repetitions')
    ssh = shutil.which('ssh'); scp = shutil.which('scp')
    if not ssh or not scp:
        raise RuntimeError('OpenSSH ssh/scp are required')
    options = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    remote = 'microblocks-charlie/builds/lp64-' + stamp
    local = output / ('native-' + stamp); source = local / 'source'; logs = local / 'results'
    source.mkdir(parents=True, exist_ok=False); logs.mkdir()
    manifest = prepare(upstream, source, sanitize)
    tests = source / 'tests'; tests.mkdir()
    protocol = (ROOT / 'tests/linux_arm64_protocol.py').read_bytes()
    (tests / 'linux_arm64_protocol.py').write_bytes(protocol)
    manifest['protocol_test_sha256'] = hashlib.sha256(protocol).hexdigest()
    (source / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    archive = local / 'source.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for path in sorted(source.rglob('*')):
            if path.is_file():
                bundle.add(path, arcname=path.relative_to(source).as_posix(), recursive=False)
    setup = ('set -eu; umask 077; test "$(uname -m)" = aarch64; test "$(id -u)" -ne 0; '
             'test ! -L "$HOME/microblocks-charlie"; test ! -L "$HOME/microblocks-charlie/builds"; '
             'mkdir -p "$HOME/microblocks-charlie/builds"; test ! -e "$HOME/' + remote + '"; mkdir "$HOME/' + remote + '"')
    run([ssh, *options, target, setup])
    run([scp, *options, str(archive), target + ':' + remote + '/source.tar.gz'])
    script = r'''set -eu
umask 077
cd "$HOME/REMOTE"
tar -xzf source.tar.gz
python3 - <<'PY'
import hashlib,json,pathlib,platform,subprocess
m=json.loads(pathlib.Path('source-manifest.json').read_text())
for name,meta in m['sources'].items():
    assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==meta['prepared_sha256'],name
assert hashlib.sha256(pathlib.Path('tests/linux_arm64_protocol.py').read_bytes()).hexdigest()==m['protocol_test_sha256']
assert platform.machine()=='aarch64'
metadata={'architecture':platform.machine(),'compiler':subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],'source_commit':m['source_commit'],'sanitizers':m['sanitize'],'source_hashes_verified':len(m['sources'])}
pathlib.Path('native-host.json').write_text(json.dumps(metadata,indent=2)+'\n')
PY
sh build.sh >build.log 2>&1
./smallvm --self-test >self-test.json 2>self-test.stderr
python3 tests/linux_arm64_protocol.py --binary "$PWD/smallvm" --repeat REPEATS --evidence protocol.json >protocol.stdout 2>protocol.stderr
sha256sum smallvm >smallvm.sha256
'''.replace('REMOTE', remote).replace('REPEATS', str(repeats))
    result = run([ssh, *options, '-T', target, 'sh -s'], data=script.encode(), timeout=180, check=False)
    (logs / 'remote.stdout').write_bytes(result.stdout)
    (logs / 'remote.stderr').write_bytes(result.stderr)
    missing = []
    for name in ('native-host.json', 'build.log', 'self-test.json', 'self-test.stderr',
                 'protocol.json', 'protocol.stdout', 'protocol.stderr', 'smallvm.sha256'):
        copied = run([scp, *options, target + ':' + remote + '/' + name, str(logs / name)], check=False)
        if copied.returncode:
            missing.append(name)
    if result.returncode:
        raise RuntimeError('Native Pi build/tests failed, exit ' + str(result.returncode) + '; retained remote ' + remote + ', local logs ' + str(logs) + '; unavailable: ' + ','.join(missing))
    if missing:
        raise RuntimeError('Native run finished but evidence retrieval incomplete: ' + ','.join(missing))
    host = json.loads((logs / 'native-host.json').read_text())
    self_test = json.loads((logs / 'self-test.json').read_text().strip().splitlines()[-1])
    protocol_result = json.loads((logs / 'protocol.json').read_text())
    if self_test['result'] != 'PASS' or protocol_result['result'] != 'PASS' or host['architecture'] != 'aarch64':
        raise RuntimeError('Native evidence does not establish target PASS')
    run([scp, *options, target + ':' + remote + '/smallvm', str(local / 'smallvm')])
    binary_sha = hashlib.sha256((local / 'smallvm').read_bytes()).hexdigest()
    if (logs / 'smallvm.sha256').read_text().split()[0] != binary_sha:
        raise RuntimeError('Downloaded binary checksum mismatch')
    report = {'tested_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'result': 'PASS', 'remote_directory': remote, 'source_commit': COMMIT,
              'host': host, 'binary_sha256': binary_sha, 'self_test': self_test,
              'protocol': protocol_result,
              'limitations': ['No graphical IDE test', 'No network VM transport',
                              'No service/installer/OS reboot test', 'No external peripherals', 'No MicroDuck hardware'],
              'system_or_service_changes': False}
    (local / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return local, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--target', default='rpi5')
    parser.add_argument('--output', type=Path, default=ROOT / 'build-artifacts/pi5-smallvm')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--repeat', type=int, default=50)
    args = parser.parse_args()
    folder, report = execute(args.upstream.resolve(), args.target, args.output.resolve(), sanitize=args.sanitize, repeats=args.repeat)
    print(json.dumps({'evidence': str(folder / 'report.json'), 'result': report['result'],
                      'architecture': report['host']['architecture'], 'sanitizers': report['host']['sanitizers'],
                      'binary_sha256': report['binary_sha256'], 'checks': report['protocol']['checks'],
                      'limitations': report['limitations']}, indent=2))
