#!/usr/bin/env python3
"""Opt-in real Pi candidate install and foreground resume acceptance.

Run on the authorized Pi in a fresh private staged project directory. Uses a
private install prefix and only its own children. No services, SSH changes,
external listener, robot gateway, GPIO or reboot. Retains files for review.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def run(binary, digest, bridge_python, node, epoch):
    if platform.system() != 'Linux' or platform.machine() != 'aarch64' or os.geteuid() == 0:
        raise RuntimeError('Requires the authorized unprivileged native AArch64 Pi')
    if not ROOT.name.startswith('microblocks-standalone-') or ROOT.parent != Path.home() or ROOT.stat().st_mode & 0o077:
        raise RuntimeError('Use a fresh private owned project directory directly in the Pi home')
    os.umask(0o077)
    if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Reviewed VM SHA-256 mismatch')
    prefix, data = ROOT / 'prefix', ROOT / 'programs'
    if any(path.exists() for path in [prefix, data, ROOT / 'acceptance.json']):
        raise RuntimeError('Inspect an earlier attempt instead of rerunning this acceptance directory')
    spec = importlib.util.spec_from_file_location('candidate_package', ROOT / 'linux/arm64/package.py')
    package = importlib.util.module_from_spec(spec); spec.loader.exec_module(package)
    version = 'pi5-standalone-v417-20261028'
    archive = ROOT / ('smallvm-linux-arm64-' + version + '.tar.gz')
    archive_sha = package.package(binary.read_bytes(), (ROOT / 'upstream-LICENSE').read_bytes(), archive, version, epoch=epoch)
    report = {'passed': False, 'hostname': platform.node(), 'architecture': platform.machine(),
              'binary_sha256': digest, 'candidate_sha256': archive_sha, 'version': version,
              'private_prefix': str(prefix), 'persistent_data': str(data), 'graphical': False,
              'robot_services_used': False, 'service_installed': False, 'os_rebooted': False,
              'network_or_security_configuration_changed': False, 'published_release': False}
    children, logs = [], []
    def command_log(name, argv, env=None, timeout=60):
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        (ROOT / (name + '.stdout')).write_text(result.stdout)
        (ROOT / (name + '.stderr')).write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect retained stdout/stderr')
        return result.stdout
    def running_vms():
        found = subprocess.run(['pgrep', '-x', 'smallvm'], capture_output=True, text=True)
        if found.returncode not in (0, 1):raise RuntimeError('Cannot inventory existing VMs')
        return set(int(value) for value in found.stdout.split())
    before = running_vms(); report['preexisting_vm_pids'] = sorted(before)
    def stop(child):
        if child.poll() is None:
            child.send_signal(signal.SIGTERM)
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        if child.returncode != 0:raise RuntimeError('Owned foreground session did not exit cleanly')
    def launch(index, actual_binary, port):
        log = (ROOT / ('supervisor-' + str(index) + '.log')).open('x'); logs.append(log)
        child = subprocess.Popen([str(bridge_python), str(ROOT / 'linux/arm64/session.py'),
            '--binary', str(actual_binary), '--editor', str(ROOT / 'editor'), '--data', str(data),
            '--resume', '--port', str(port)], stdout=log, stderr=subprocess.STDOUT)
        children.append(child); until = time.monotonic() + 15
        while time.monotonic() < until:
            if child.poll() is not None:raise RuntimeError('Owned supervisor startup failed')
            try:
                value = json.loads((data / 'session.json').read_text())
                if value.get('supervisor_pid') == child.pid and value.get('state') == 'ready':return child, value
            except (FileNotFoundError, json.JSONDecodeError):pass
            time.sleep(.02)
        raise RuntimeError('Owned session readiness timed out')
    try:
        command_log('install', ['bash', str(ROOT / 'scripts/install-smallvm-linux-arm64.sh'),
            '--archive', str(archive), '--version', version, '--sha256', archive_sha,
            '--prefix', str(prefix), '--data-dir', str(data)])
        report['installed_launcher_self_test'] = json.loads(command_log('installed-self-test', [str(prefix / 'bin/smallvm'), '--self-test']).strip().splitlines()[-1])
        actual = prefix / 'lib/microblocks' / version / 'smallvm'
        if hashlib.sha256(actual.read_bytes()).hexdigest() != digest:raise RuntimeError('Installed binary changed')
        env = os.environ.copy(); env['SMALLVM_MICRODUCK_BINARY'] = str(actual)
        command_log('focused-session-tests', [str(bridge_python), '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_linux_arm64_session.py', '-v'], env=env)
        with socket.socket() as available:available.bind(('127.0.0.1', 0));port = available.getsockname()[1]
        report['port'] = port
        first, initial = launch(1, actual, port)
        report['initial_session'] = initial
        first_probe = command_log('js-upload-reconnect', [node, str(ROOT / 'tests/js-standalone-session.cjs'), str(ROOT / 'editor'), f'http://127.0.0.1:{port}/', 'upload'])
        report['js_upload_reconnect'] = json.loads(first_probe.strip().splitlines()[-1])
        stop(first)
        saved = hashlib.sha256((data / 'program.ucode').read_bytes()).hexdigest()
        old_logs = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in data.glob('*.log')}
        second, resumed = launch(2, actual, port)
        report['resumed_session'] = resumed
        if initial['pty_info'] == resumed['pty_info']:raise RuntimeError('Resume reused discovery path')
        if hashlib.sha256((data / 'program.ucode').read_bytes()).hexdigest() != saved:raise RuntimeError('Resume changed saved program')
        second_probe = command_log('js-resume-readback', [node, str(ROOT / 'tests/js-standalone-session.cjs'), str(ROOT / 'editor'), f'http://127.0.0.1:{port}/', 'readback'])
        report['js_resume_readback'] = json.loads(second_probe.strip().splitlines()[-1])
        if hashlib.sha256((data / 'program.ucode').read_bytes()).hexdigest() != saved:raise RuntimeError('Readback changed stored code')
        for path, expected in old_logs.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:raise RuntimeError('Resume changed earlier logs')
        stop(second)
        report.update(passed=True, retained_program_sha256=saved, earlier_logs_preserved=True,
                      fresh_discovery_per_launch=True, install_service_option_used=False)
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
        for log in logs:log.close()
        after = running_vms()
        report['preexisting_vms_still_alive'] = before <= after
        report['children_stopped'] = all(child.poll() is not None for child in children)
        report['remaining_vm_pids'] = sorted(after)
        if not report['preexisting_vms_still_alive']:report['passed'] = False
        (ROOT / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    if not report['passed']:raise RuntimeError('Standalone acceptance incomplete; inspect retained receipt')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--bridge-python', required=True, type=Path)
    parser.add_argument('--node', default='node')
    parser.add_argument('--epoch', required=True, type=int)
    args = parser.parse_args()
    print(json.dumps(run(args.binary.resolve(), args.sha256, args.bridge_python.absolute(), args.node, args.epoch), indent=2))
