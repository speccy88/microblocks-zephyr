#!/usr/bin/env python3
"""Foreground native VM and loopback editor bridge, with explicit data resume.

Starts and stops only its own children. Does not install a service or alter SSH.
Run with the project Python environment containing pinned websockets.
"""
# SPDX-License-Identifier: MIT
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import urllib.request
import uuid


def private_file(meta):
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077 or meta.st_nlink != 1:
        raise RuntimeError('Session state must be a private current-user-owned regular file')


def acquire_directory(data, resume):
    if not resume:
        try:
            data.mkdir(mode=0o700)
        except FileExistsError as error:
            raise RuntimeError('Data already exists; choose --resume explicitly') from error
    directory = lock = None
    try:
        directory = os.open(data, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        meta = os.fstat(directory)
        if meta.st_uid != os.geteuid() or meta.st_mode & 0o077:
            raise RuntimeError('Data must be private and owned by the current user')
        canonical = data.resolve(strict=True)
        actual = canonical.stat()
        if (meta.st_dev, meta.st_ino) != (actual.st_dev, actual.st_ino):
            raise RuntimeError('Data directory identity changed')
        lock = os.open('.session.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
        private_file(os.fstat(lock))
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Another supervisor owns this data directory') from error
        try:
            private_file(os.stat('session.json', dir_fd=directory, follow_symlinks=False))
        except FileNotFoundError:
            pass
        return canonical, directory, lock
    except BaseException:
        for fd in (lock, directory):
            if fd is not None:
                os.close(fd)
        raise


def record_status(directory, report):
    name = '.session-info-' + uuid.uuid4().hex + '.tmp'
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write((json.dumps(report, indent=2) + '\n').encode())
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, 'session.json', src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass


def child_discovery(directory, name, pid):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    except FileNotFoundError:
        return None
    try:
        meta = os.fstat(fd); private_file(meta)
        if not 1 <= meta.st_size <= 4096:
            raise RuntimeError('Invalid discovery record size')
        raw = os.read(fd, 4097)
        if len(raw) != meta.st_size:
            raise RuntimeError('Discovery changed while reading')
        record = json.loads(raw)
    finally:
        os.close(fd)
    if (not isinstance(record, dict) or type(record.get('pid')) is not int or record['pid'] != pid
            or record.get('transport') != 'pty' or record.get('vm_version') != 417 or record.get('network_listener') is not False):
        raise RuntimeError('Discovery does not belong to the newly spawned VM')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--microduck-socket', type=Path)
    parser.add_argument('--port', type=int, default=8876)
    args = parser.parse_args()
    binary, editor, data = args.binary.resolve(strict=True), args.editor.resolve(strict=True), args.data.absolute()
    if not 1024 <= args.port <= 65535:
        raise SystemExit('Use an unprivileged loopback port')
    with binary.open('rb') as stream:
        if stream.read(6) != b'\x7fELF\x02\x01':
            raise RuntimeError('Select the actual native 64-bit ELF, not a shell launcher')
    os.umask(0o077)
    data, directory, lock = acquire_directory(data, args.resume)
    run_id = uuid.uuid4().hex
    info_name = 'pty-' + run_id + '.json'
    vm_log, bridge_log = 'vm-' + run_id + '.log', 'bridge-' + run_id + '.log'
    report = {'state': 'starting', 'session_id': run_id, 'supervisor_pid': os.getpid(),
              'resume': args.resume, 'bind': '127.0.0.1', 'port': args.port, 'binary': str(binary),
              'data_directory': str(data), 'editor_directory': str(editor), 'service_installed': False,
              'pty_info': str(data / info_name), 'vm_log': str(data / vm_log), 'bridge_log': str(data / bridge_log)}
    stopped = False
    def stop(signum, frame):
        nonlocal stopped
        stopped = True
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, stop)
    children = []
    logs = []
    failed = False
    try:
        def new_log(name):
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
            log = os.fdopen(fd, 'w+b', buffering=0); logs.append(log)
            return log
        log, bridge_output = new_log(vm_log), new_log(bridge_log)
        record_status(directory, report)
        vm_args = [str(binary), '--data-dir', str(data), '--pty-info', report['pty_info']]
        if args.microduck_socket is not None:
            vm_args += ['--microduck-socket', str(args.microduck_socket.absolute())]
        vm = subprocess.Popen(vm_args, stdout=log, stderr=subprocess.STDOUT)
        children.append(vm); report['vm_pid'] = vm.pid
        until = time.monotonic() + 10
        while True:
            if stopped:
                return
            if vm.poll() is not None or time.monotonic() > until:
                raise RuntimeError('New VM did not become ready; inspect its run log')
            if child_discovery(directory, info_name, vm.pid) is not None:
                break
            time.sleep(.02)
        bridge = subprocess.Popen([sys.executable, str(Path(__file__).with_name('bridge.py')),
            '--editor', str(editor), '--pty-info', report['pty_info'],
            '--vm-executable', str(binary), '--http-port', str(args.port)], stdout=bridge_output, stderr=subprocess.STDOUT)
        children.append(bridge); report['bridge_pid'] = bridge.pid
        until = time.monotonic() + 10
        marker = f'Local SmallVM editor: http://127.0.0.1:{args.port}/'.encode()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while True:
            if stopped:
                return
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Session child exited; inspect its run log')
            if time.monotonic() > until:
                raise RuntimeError('Own bridge did not become ready')
            if marker in os.pread(bridge_output.fileno(), 65536, 0):
                try:
                    with opener.open(f'http://127.0.0.1:{args.port}/', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
            time.sleep(.05)
        report['state'] = 'ready'; record_status(directory, report)
        print(json.dumps(report), flush=True)
        while not stopped:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Session child exited; inspect logs')
            time.sleep(.25)
    except BaseException:
        failed = True
        raise
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
        report['state'] = 'failed' if failed else 'stopped'
        report['children_returncodes'] = [child.returncode for child in children]
        try:
            record_status(directory, report)
        finally:
            os.close(lock); os.close(directory)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        raise SystemExit('Foreground session refused: ' + str(error))
