#!/usr/bin/env python3
"""Foreground development session: one real VM and its loopback editor bridge.

Starts and stops only its own children. Does not install a service or alter SSH.
Run with the project Python environment containing pinned websockets.
"""
# SPDX-License-Identifier: MIT
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--microduck-socket', type=Path)
    parser.add_argument('--port', type=int, default=8876)
    args = parser.parse_args()
    binary, editor, data = args.binary.resolve(), args.editor.resolve(), args.data.resolve()
    if not 1024 <= args.port <= 65535 or data.exists():
        raise SystemExit('Use an unprivileged port and a fresh data directory')
    data.mkdir(mode=0o700)
    os.umask(0o077)
    stopped = False
    def stop(signum, frame):
        nonlocal stopped
        stopped = True
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    children = []
    logs = []
    try:
        log = (data / 'vm.log').open('w'); logs.append(log)
        vm_args = [str(binary), '--data-dir', str(data), '--pty-info', str(data / 'pty.json')]
        if args.microduck_socket is not None:
            vm_args += ['--microduck-socket', str(args.microduck_socket.absolute())]
        vm = subprocess.Popen(vm_args, stdout=log, stderr=subprocess.STDOUT)
        children.append(vm)
        until = time.monotonic() + 10
        while not (data / 'pty.json').exists():
            if stopped or vm.poll() is not None or time.monotonic() > until:
                raise RuntimeError('VM did not become ready; inspect vm.log')
            time.sleep(.02)
        log = (data / 'bridge.log').open('w'); logs.append(log)
        bridge = subprocess.Popen([sys.executable, str(Path(__file__).with_name('bridge.py')),
            '--editor', str(editor), '--pty-info', str(data / 'pty.json'),
            '--vm-executable', str(binary), '--http-port', str(args.port)], stdout=log, stderr=subprocess.STDOUT)
        children.append(bridge)
        until = time.monotonic() + 10
        while True:
            if stopped or any(child.poll() is not None for child in children):
                raise RuntimeError('Session child exited; inspect logs')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/index.html', timeout=1) as response:
                    assert response.status == 200
                break
            except OSError:
                if time.monotonic() > until:
                    raise RuntimeError('Bridge did not become ready')
                time.sleep(.05)
        report = {'state': 'ready', 'vm_pid': vm.pid, 'bridge_pid': bridge.pid,
                  'bind': '127.0.0.1', 'port': args.port, 'binary': str(binary),
                  'data_directory': str(data), 'editor_directory': str(editor),
                  'service_installed': False}
        (data / 'session.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report), flush=True)
        while not stopped:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Session child exited; inspect logs')
            time.sleep(.25)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait(timeout=5)
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
