#!/usr/bin/env python3
"""Run the iPhone JS adapter against an owned real Linux VM and loopback bridge.

Node models only the native socket bridge; the actual compiler, parser and VM
execute. No physical board, iOS radio or native URLSession claim is made.
"""
# SPDX-License-Identifier: MIT
import argparse
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise RuntimeError('Requires an unprivileged Linux test runner')
    with tempfile.TemporaryDirectory(prefix='iphone-vm-') as temp:
        data = Path(temp) / 'data'
        with socket.socket() as free:
            free.bind(('127.0.0.1', 0)); port = free.getsockname()[1]
        child = subprocess.Popen([sys.executable, str(ROOT / 'linux/arm64/session.py'),
            '--binary', str(args.binary.resolve()), '--editor', str(args.editor.resolve()),
            '--data', str(data), '--port', str(port)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            if not select.select([child.stdout], [], [], 20)[0]:
                raise RuntimeError('Owned real VM session did not become ready')
            line = child.stdout.readline()
            if not line:
                raise RuntimeError(child.stderr.read())
            status = json.loads(line)
            assert status['state'] == 'ready' and status['supervisor_pid'] == child.pid
            result = subprocess.run(['node', str(ROOT / 'tests/iphone-transport.test.cjs'),
                str(args.editor.resolve()), f'http://127.0.0.1:{port}/'],
                capture_output=True, text=True, timeout=40)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            assert report['protocol']['protocol_peer'] == 'real native SmallVM v417 via loopback'
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report))
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=15)
            if child.returncode:
                raise RuntimeError('Owned test supervisor did not exit cleanly')


if __name__ == '__main__':
    main()
