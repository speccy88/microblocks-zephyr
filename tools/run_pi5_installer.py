#!/usr/bin/env python3
"""Package a separately tested native binary and test installation on the Pi.

Only a fresh private ~/microblocks-charlie/install-tests directory is changed.
No service, reboot, release, credential or unrelated installation is changed.
"""
# SPDX-License-Identifier: MIT
import argparse
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from run_pi5_smallvm import run, ROOT


def execute(binary, upstream, target):
    import re
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', target):
        raise ValueError('Use a configured SSH alias')
    spec = importlib.util.spec_from_file_location('package_arm64', ROOT / 'linux/arm64/package.py')
    pack = importlib.util.module_from_spec(spec); spec.loader.exec_module(pack)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    local = ROOT / 'build-artifacts/pi5-installer' / stamp
    local.mkdir(parents=True)
    versions = ['0.1.0-local1', '0.1.0-local2']
    license_bytes = subprocess.check_output(['git', '-C', str(upstream), 'show', pack.SOURCE_COMMIT + ':LICENSE'])
    for version in versions:
        pack.package(binary.read_bytes(), license_bytes, local / (version + '.tar.gz'), version)
    files = {'install.sh': ROOT / 'scripts/install-smallvm-linux-arm64.sh',
             'uninstall.sh': ROOT / 'scripts/uninstall-smallvm-linux-arm64.sh',
             'linux_arm64_install_live.py': ROOT / 'tests/linux_arm64_install_live.py',
             'linux_arm64_protocol.py': ROOT / 'tests/linux_arm64_protocol.py'}
    for name, source in files.items():
        (local / name).write_bytes(source.read_bytes())
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in local.iterdir() if p.is_file()}
    (local / 'input-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    options = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
    remote = 'microblocks-charlie/install-tests/' + stamp
    run(['ssh', *options, target, 'set -eu; umask 077; test ! -L "$HOME/microblocks-charlie/install-tests"; mkdir -p "$HOME/microblocks-charlie/install-tests"; mkdir "$HOME/' + remote + '"'])
    for path in local.iterdir():
        if path.is_file():
            run(['scp', *options, str(path), target + ':' + remote + '/' + path.name])
    script = r'''set -eu
cd "$HOME/REMOTE"
python3 - <<'PY'
import pathlib,hashlib,json
for name,digest in json.loads(pathlib.Path('input-hashes.json').read_text()).items():
 assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest,name
PY
python3 linux_arm64_install_live.py --base "$PWD" --version-one 0.1.0-local1 --version-two 0.1.0-local2
'''.replace('REMOTE', remote)
    result = run(['ssh', *options, '-T', target, 'sh -s'], data=script.encode(), timeout=180, check=False)
    (local / 'remote.stdout').write_bytes(result.stdout); (local / 'remote.stderr').write_bytes(result.stderr)
    for name in ('installer-evidence.json', 'lifecycle.log'):
        run(['scp', *options, target + ':' + remote + '/' + name, str(local / name)], check=False)
    if result.returncode:
        raise RuntimeError('Live installer test failed; inspect ' + str(local))
    report = json.loads((local / 'installer-evidence.json').read_text())
    assert report['result'] == 'PASS'
    print(json.dumps({'evidence': str(local / 'installer-evidence.json'), **report}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--target', default='rpi5')
    args = parser.parse_args()
    execute(args.binary.resolve(), args.upstream.resolve(), args.target)
