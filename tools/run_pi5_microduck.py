#!/usr/bin/env python3
"""Run only the new MicroDuck adapter tests on an already tested native Pi VM.

Real AArch64 interpreter, sockets and gateway; simulated robot services only.
Uses new private test directories. No credentials, service, robot or numeric
acceptance suite is accessed, changed or executed.
"""
# SPDX-License-Identifier: MIT
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
from run_pi5_smallvm import ROOT, run


def execute(native_evidence, target):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', target):
        raise ValueError('Use a configured SSH alias')
    native = json.loads(native_evidence.read_text())
    binary_folder = native.get('remote_directory', '')
    if native.get('result') != 'PASS' or native['host']['architecture'] != 'aarch64' or not re.fullmatch(r'microblocks-charlie/builds/lp64-[0-9TZ]+', binary_folder):
        raise ValueError('Supply a successful native Pi build report')
    source = json.loads((native_evidence.parent / 'source/source-manifest.json').read_text())
    for name in ('platform/microduck.c', 'platform/microduck.h'):
        meta = source['sources'][name]
        if hashlib.sha256((ROOT / meta['port_source']).read_bytes()).hexdigest() != meta['prepared_sha256']:
            raise ValueError('Native binary source differs from the current adapter: ' + name)
    binary_sha = native['binary_sha256']
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    local = ROOT / 'build-artifacts/pi5-microduck' / stamp
    local.mkdir(parents=True)
    relative = ['tests/test_linux_microduck_vm.py', 'tests/linux_arm64_protocol.py',
                'linux/microduck/gateway.py', 'linux/microduck/protocol.py']
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in relative}
    (local / 'input-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    options = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
    remote = 'microblocks-charlie/microduck-tests/' + stamp
    setup = 'set -eu; umask 077; test "$(uname -m)" = aarch64; test ! -L "$HOME/microblocks-charlie/microduck-tests"; mkdir -p "$HOME/microblocks-charlie/microduck-tests"; mkdir "$HOME/' + remote + '"; mkdir "$HOME/' + remote + '/tests"; mkdir -p "$HOME/' + remote + '/linux/microduck"'
    run(['ssh', *options, target, setup])
    for name in relative:
        run(['scp', *options, str(ROOT / name), target + ':' + remote + '/' + name])
    run(['scp', *options, str(local / 'input-hashes.json'), target + ':' + remote + '/input-hashes.json'])
    script = r'''set -eu
umask 077
cd "$HOME/REMOTE"
export SMALLVM_MICRODUCK_BINARY="$HOME/BINARY_FOLDER/smallvm"
python3 - <<'PY'
import hashlib,json,os,pathlib,platform,sys,unittest
for name,digest in json.loads(pathlib.Path('input-hashes.json').read_text()).items():
 assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest,name
binary=pathlib.Path(os.environ['SMALLVM_MICRODUCK_BINARY'])
assert hashlib.sha256(binary.read_bytes()).hexdigest()=='BINARY_SHA'
assert platform.machine()=='aarch64'
suite=unittest.defaultTestLoader.discover('tests',pattern='test_linux_microduck_vm.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
passed=result.wasSuccessful() and result.testsRun==10 and not result.skipped
evidence={'result':'PASS' if passed else 'FAIL','architecture':platform.machine(),'tests_run':result.testsRun,
 'skipped':len(result.skipped),'failures':len(result.failures),'errors':len(result.errors),
 'binary_sha256':'BINARY_SHA','binary_sanitizers':SANITIZERS,
 'scope':'actual native AArch64 SmallVM, official PTY bytecode, C socket adapter and Python gateway; robot services simulated',
 'physical_microduck_tested':False,'numeric_acceptance_suite_executed':False,'service_changes':False}
pathlib.Path('microduck-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
sys.exit(0 if passed else 1)
PY
'''.replace('REMOTE', remote).replace('BINARY_FOLDER', binary_folder).replace('BINARY_SHA', binary_sha).replace('SANITIZERS', str(bool(native['host']['sanitizers'])))
    result = run(['ssh', *options, '-T', target, 'sh -s'], data=script.encode(), timeout=180, check=False)
    (local / 'tests.stdout').write_bytes(result.stdout)
    (local / 'tests.stderr').write_bytes(result.stderr)
    run(['scp', *options, target + ':' + remote + '/microduck-evidence.json', str(local / 'microduck-evidence.json')], check=False)
    if result.returncode:
        raise RuntimeError('MicroDuck adapter feature tests failed; inspect ' + str(local))
    report = json.loads((local / 'microduck-evidence.json').read_text())
    assert report['result'] == 'PASS'
    print(json.dumps({'evidence': str(local / 'microduck-evidence.json'), **report}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-evidence', type=Path, required=True)
    parser.add_argument('--target', default='rpi5')
    args = parser.parse_args()
    execute(args.native_evidence.resolve(), args.target)
