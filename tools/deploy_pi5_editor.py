#!/usr/bin/env python3
"""Copy verified real editor/VM/bridge to a fresh private Pi development folder.

Does not start a listener or service. Prints the foreground session command.
"""
# SPDX-License-Identifier: MIT
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import tarfile
from run_pi5_smallvm import ROOT, run


def execute(binary, editor, target):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,63}', target):
        raise ValueError('Use a configured SSH alias')
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    local = ROOT / 'build-artifacts/pi5-editor' / stamp
    local.mkdir(parents=True)
    manifest = json.loads((editor / 'build-manifest.json').read_text())
    port = manifest['loopback_bridge_port']
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Invalid editor loopback port')
    for name, meta in manifest['files'].items():
        path = editor / name
        if path.is_symlink() or not path.resolve().is_relative_to(editor) or hashlib.sha256(path.read_bytes()).hexdigest() != meta['sha256']:
            raise ValueError('Editor asset changed: ' + name)
    files = {'smallvm': binary, 'bridge.py': ROOT / 'linux/arm64/bridge.py',
             'session.py': ROOT / 'linux/arm64/session.py'}
    if manifest['profile'] == 'microduck':
        for name in ('gateway.py', 'protocol.py', 'simulator.py'):
            files['microduck/' + name] = ROOT / 'linux/microduck' / name
    files.update({'editor/' + p.relative_to(editor).as_posix(): p for p in editor.rglob('*') if p.is_file()})
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}
    (local / 'input-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    archive = local / 'editor.tar.gz'
    with tarfile.open(archive, 'w:gz') as bundle:
        for name, path in sorted(files.items()):
            if path.is_symlink():
                raise ValueError('No asset symlinks allowed')
            bundle.add(path, arcname=name, recursive=False)
        bundle.add(local / 'input-hashes.json', arcname='input-hashes.json')
    options = ['-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
    remote = 'microblocks-charlie/editor-sessions/' + stamp
    run(['ssh', *options, target, 'set -eu; umask 077; test ! -L "$HOME/microblocks-charlie/editor-sessions"; mkdir -p "$HOME/microblocks-charlie/editor-sessions"; mkdir "$HOME/' + remote + '"'])
    run(['scp', *options, str(archive), target + ':' + remote + '/editor.tar.gz'])
    script = r'''set -eu
umask 077
cd "$HOME/REMOTE"
tar -xzf editor.tar.gz
python3 - <<'PY'
import pathlib,hashlib,json
for name,digest in json.loads(pathlib.Path('input-hashes.json').read_text()).items():
 assert hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()==digest,name
pathlib.Path('smallvm').chmod(0o700)
PY
'''.replace('REMOTE', remote)
    run(['ssh', *options, '-T', target, 'sh -s'], data=script.encode())
    report = {'remote_directory': remote, 'target': target,
              'verified_input_files': len(hashes), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'binary_sha256': hashes['smallvm'], 'listener_started': False,
              'remote_command': 'cd "$HOME/' + remote + '" && exec "$HOME/microblocks-charlie/bridge-venv/bin/python" -u session.py --binary "$PWD/smallvm" --editor "$PWD/editor" --data "$PWD/data" --port ' + str(port)}
    if manifest['profile'] == 'microduck':
        report['simulation_command'] = 'cd "$HOME/' + remote + '" && exec python3 -u microduck/simulator.py --directory "$PWD/simulation"'
        report['simulated_gateway_argument'] = ' --microduck-socket "$HOME/' + remote + '/simulation/gateway.sock"'
    (local / 'deployment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'evidence': str(local / 'deployment.json'), **report}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--target', default='rpi5')
    args = parser.parse_args()
    execute(args.binary.resolve(), args.editor.resolve(), args.target)
