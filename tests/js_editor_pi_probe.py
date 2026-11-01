#!/usr/bin/env python3
"""Run the staged JS adapter against a private real VM on Linux; no hardware I/O.

Supply an existing verified VM executable and bridge Python environment. Only
our child processes and private test data are touched. No service, firewall,
network setting, credentials or board firmware changes are made.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def run(root, binary, expected_sha, bridge_python, node, typed=False, simulated=False):
    actual_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        raise ValueError('VM digest mismatch')
    data = Path(tempfile.mkdtemp(prefix='vm-data-', dir=root))
    os.chmod(data, 0o700)
    with socket.socket() as available:
        available.bind(('127.0.0.1', 0))
        port = available.getsockname()[1]
    processes, logs = [], []
    result = {'architecture': platform.machine(), 'hostname': platform.node(),
        'vm_sha256': actual_sha, 'port': port, 'graphical': False,
        'robot_hardware': False, 'network_settings_changed': False,
        'typed_libraries': typed, 'simulated_sensor_services': simulated}
    try:
        def start(name, command):
            log = (data / (name + '.log')).open('w', encoding='utf-8')
            logs.append(log)
            processes.append(subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT))

        def wait_file(path):
            deadline = time.monotonic() + 5
            while not path.exists():
                if any(p.poll() is not None for p in processes) or time.monotonic() > deadline:
                    raise RuntimeError('Private fixture startup failed: ' + path.name)
                time.sleep(.02)

        gateway_args = []
        if simulated:
            if not typed:
                raise ValueError('Simulated services require the typed-library probe')
            sensors = data / 'sensors'
            start('simulated-sensors', [sys.executable, str(root / 'linux/microduck/sensor_simulator.py'), '--directory', str(sensors)])
            wait_file(sensors / 'tof.sock')
            wait_file(sensors / 'pad.sock')
            def config(name, value):
                p = data / name
                with p.open('x', encoding='utf-8') as stream:
                    os.chmod(p, 0o600)
                    json.dump(value, stream)
                return p
            empty = config('gateway.json', {'version': 1, 'upstreams': {}})
            depth = config('depth.json', {'version': 1, 'daemon': 'tofd', 'path': str(sensors / 'tof.sock'), 'uid': os.geteuid()})
            gamepad = config('gamepad.json', {'version': 1, 'daemon': 'padd', 'path': str(sensors / 'pad.sock'), 'uid': os.geteuid()})
            gateway_socket = data / 'gateway.sock'
            start('readonly-gateway', [sys.executable, str(root / 'linux/microduck/gateway.py'),
                '--socket', str(gateway_socket), '--config', str(empty), '--depth-config', str(depth), '--gamepad-config', str(gamepad)])
            wait_file(gateway_socket)
            gateway_args = ['--microduck-socket', str(gateway_socket)]
        info = data / 'pty.json'
        for name, command in [
            ('vm', [str(binary), '--data-dir', str(data), '--pty-info', str(info), *gateway_args]),
            ('bridge', [str(bridge_python), str(root / 'linux/arm64/bridge.py'),
                '--editor', str(root / 'editor'), '--pty-info', str(info),
                '--vm-executable', str(binary), '--http-port', str(port)])]:
            if name == 'bridge':
                deadline = time.monotonic() + 5
                while not info.exists():
                    if any(p.poll() is not None for p in processes) or time.monotonic() > deadline:
                        raise RuntimeError('Private VM startup failed')
                    time.sleep(.02)
            start(name, command)
        url = f'http://127.0.0.1:{port}/'
        deadline = time.monotonic() + 5
        while True:
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    html = response.read(50000)
                    if b'linux-compat.js' not in html:
                        raise RuntimeError('Wrong editor served')
                break
            except OSError:
                if processes[-1].poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Private bridge startup failed')
                time.sleep(.02)
        script = 'js-typed-libraries.test.cjs' if typed else 'js-editor-compat.test.cjs'
        probe = subprocess.run([node, str(root / 'tests' / script), str(root / 'editor'), url,
            'simulated-sensors' if simulated else 'no-gateway'], capture_output=True, text=True, timeout=60)
        (data / 'node.stdout').write_text(probe.stdout, encoding='utf-8')
        (data / 'node.stderr').write_text(probe.stderr, encoding='utf-8')
        result.update(returncode=probe.returncode, output=probe.stdout, stderr=probe.stderr,
                      node_version=subprocess.check_output([node, '--version'], text=True).strip())
        if probe.returncode:
            raise RuntimeError('JS/Pi probe failed; see receipt and private logs')
        result['passed'] = True
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for log in logs:
            log.close()
        result['children_stopped'] = all(p.poll() is not None for p in processes)
        (root / 'pi-probe-receipt.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--bridge-python', required=True, type=Path)
    parser.add_argument('--node', default='node')
    parser.add_argument('--typed-libraries', action='store_true')
    parser.add_argument('--simulated-sensors', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args.root.resolve(), args.binary.resolve(), args.sha256,
                         args.bridge_python.absolute(), args.node, args.typed_libraries,
                         args.simulated_sensors), indent=2))
