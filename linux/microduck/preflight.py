#!/usr/bin/env python3
"""Observe local commissioning prerequisites without connecting or changing anything."""
# SPDX-License-Identifier: MIT
import sys

if __name__ == '__main__':
    sys.dont_write_bytecode = True

import argparse
import json
import os
from pathlib import Path
import platform
import re
import socket
import stat
import struct

try:
    from .gateway import Gateway, load_config
    from .protocol import API_VERSION, SOURCE_COMMIT, RpcError, socket_identity
except ImportError:
    from gateway import Gateway, load_config
    from protocol import API_VERSION, SOURCE_COMMIT, RpcError, socket_identity


def check(name, status, code):
    return {'name': name, 'status': status, 'code': code}


def host_observation():
    system = platform.system()
    machine = platform.machine().lower()
    uid = os.geteuid() if hasattr(os, 'geteuid') else None
    try:
        libc, version = platform.libc_ver()
    except (OSError, ValueError):
        libc, version = '', ''
    match = re.fullmatch(r'(\d+)\.(\d+)(?:\.\d+)?', version) if isinstance(version, str) and len(version) <= 32 else None
    glibc = version if libc == 'glibc' and match else None
    features = all(hasattr(os, key) for key in ('geteuid', 'O_NOFOLLOW', 'O_CLOEXEC', 'O_NONBLOCK')) and all(hasattr(socket, key) for key in ('AF_UNIX', 'SO_PEERCRED'))
    host = {'system': system if system in ('Linux', 'Windows', 'Darwin') else 'other',
            'machine': machine if machine in ('aarch64', 'arm64', 'x86_64', 'amd64', 'armv7l', 'i686', 'i386') else 'other',
            'pointer_bits': struct.calcsize('P') * 8, 'python': list(sys.version_info[:3]),
            'effective_uid': uid, 'glibc_version': glibc}
    checks = [check('linux', 'PASS' if system == 'Linux' else 'FAIL', 'LINUX_REQUIRED'),
              check('arm64', 'PASS' if machine in ('aarch64', 'arm64') and host['pointer_bits'] == 64 else 'FAIL', 'ARM64_64BIT_REQUIRED'),
              check('python', 'PASS' if sys.version_info >= (3, 11) else 'FAIL', 'PYTHON_3_11_REQUIRED'),
              check('unprivileged_user', 'PASS' if type(uid) is int and uid > 0 else 'FAIL', 'UNPRIVILEGED_USER_REQUIRED'),
              check('unix_primitives', 'PASS' if features else 'FAIL', 'UNIX_CREDENTIAL_APIS_REQUIRED')]
    checks.append(check('glibc', 'UNKNOWN' if glibc is None else 'PASS' if (int(match[1]), int(match[2])) >= (2, 34) else 'FAIL',
                        'GLIBC_UNOBSERVED' if glibc is None else 'GLIBC_2_34_REQUIRED'))
    return host, checks


def input_path(value):
    if not isinstance(value, (str, Path)):
        raise ValueError('Invalid path type')
    path = Path(value).absolute()
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError('Noncanonical parent')
    return path


def inspect_socket(upstream):
    row = {'configured_uid': upstream.uid, 'connected_peer_uid': None, 'peer_verified': False}
    try:
        identity = socket_identity(upstream.path, upstream.uid)
        meta = upstream.path.lstat()
        current = socket_identity(upstream.path, upstream.uid)
        if identity != current or identity != (meta.st_dev, meta.st_ino) or not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != upstream.uid or meta.st_mode & 0o007:
            return {**row, 'status': 'FAIL', 'code': 'SOCKET_METADATA_CHANGED'}
        return {**row, 'status': 'PASS', 'code': 'SOCKET_FILE_METADATA_MATCHES',
                'socket_file_uid': meta.st_uid, 'mode': f'{stat.S_IMODE(meta.st_mode):04o}',
                'device': meta.st_dev, 'inode': meta.st_ino}
    except FileNotFoundError:
        return {**row, 'status': 'FAIL', 'code': 'SOCKET_MISSING'}
    except PermissionError:
        return {**row, 'status': 'FAIL', 'code': 'SOCKET_METADATA_ACCESS_DENIED'}
    except RpcError:
        return {**row, 'status': 'FAIL', 'code': 'SOCKET_METADATA_REFUSED'}
    except (OSError, ValueError, RuntimeError):
        return {**row, 'status': 'FAIL', 'code': 'SOCKET_METADATA_UNAVAILABLE'}


def inspect_runtime(value):
    try:
        path = input_path(value)
        meta = path.lstat()
        if path.resolve(strict=True) != path or not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077 or meta.st_mode & 0o700 != 0o700:
            return {'status': 'FAIL', 'code': 'RUNTIME_DIRECTORY_REFUSED'}
        row = {'status': 'PASS', 'code': 'RUNTIME_DIRECTORY_METADATA_MATCHES', 'uid': meta.st_uid,
               'mode': f'{stat.S_IMODE(meta.st_mode):04o}', 'available_bytes': None, 'write_probe_performed': False}
        try:
            space = os.statvfs(path)
            if type(space.f_bavail) is not int or type(space.f_frsize) is not int or space.f_bavail < 0 or space.f_frsize <= 0:
                row.update(status='UNKNOWN', code='RUNTIME_SPACE_UNOBSERVED')
            else:
                row['available_bytes'] = space.f_bavail * space.f_frsize
            if space.f_flag & getattr(os, 'ST_RDONLY', 1):
                row.update(status='FAIL', code='RUNTIME_FILESYSTEM_READONLY')
        except OSError:
            row.update(status='UNKNOWN', code='RUNTIME_FILESYSTEM_UNOBSERVED')
        return row
    except FileNotFoundError:
        return {'status': 'FAIL', 'code': 'RUNTIME_DIRECTORY_MISSING'}
    except (OSError, ValueError, TypeError, RuntimeError):
        return {'status': 'FAIL', 'code': 'RUNTIME_DIRECTORY_UNAVAILABLE'}


def inspect(config=None, runtime_dir=None):
    host, checks = host_observation()
    available = host['system'] == 'Linux' and next(item for item in checks if item['name'] == 'unix_primitives')['status'] == 'PASS'
    config_result = {'status': 'NOT_CHECKED', 'code': 'CONFIG_NOT_PROVIDED'}
    runtime = {'status': 'NOT_CHECKED', 'code': 'RUNTIME_NOT_PROVIDED'}
    upstreams = {}
    if config is not None:
        if not available:
            config_result = {'status': 'NOT_CHECKED', 'code': 'LINUX_PRIMITIVES_UNAVAILABLE'}
        else:
            try:
                service = Gateway(load_config(input_path(config)))  # Constructor only: no start, connect or request.
                config_result = {'status': 'PASS', 'code': 'CONFIG_PRIVATE_SCHEMA_MATCHES'}
                upstreams = {name: inspect_socket(value) for name, value in sorted(service.upstreams.items())}
            except FileNotFoundError:
                config_result = {'status': 'FAIL', 'code': 'CONFIG_UNAVAILABLE'}
            except (ValueError, OSError, RpcError, TypeError, RuntimeError):
                config_result = {'status': 'FAIL', 'code': 'CONFIG_INVALID_OR_UNTRUSTED'}
    if runtime_dir is not None:
        runtime = inspect_runtime(runtime_dir) if available else {'status': 'NOT_CHECKED', 'code': 'LINUX_PRIMITIVES_UNAVAILABLE'}
    statuses = [item['status'] for item in checks] + [config_result['status'], runtime['status']] + [item['status'] for item in upstreams.values()]
    return {'schema_version': 1, 'result': 'BLOCKED' if 'FAIL' in statuses else 'INCOMPLETE',
            'scope': 'local host/filesystem observations only; no robot I/O or daemon request',
            'host': host, 'checks': checks, 'config': config_result, 'runtime_directory': runtime, 'upstreams': upstreams,
            'expected_api_version': API_VERSION, 'source_commit': SOURCE_COMMIT, 'daemon_api_version_observed': None,
            'connected_peer_uids_verified': False, 'robot_ready': None, 'mutation_authorized': False,
            'physical_microduck_tested': False, 'daemon_requests_sent': 0, 'system_changed': False,
            'not_checked': ['connected peer credentials', 'daemon API and authoritative caller permissions',
                            'runtime I/O, ACL and security-module permission', 'shipping hardware and physical behavior',
                            'motion authorization, service startup and reboot']}


class BoundedParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('Unsupported CLI arguments')


def main(argv=None):
    parser = BoundedParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--runtime-dir', type=Path)
    try:
        args = parser.parse_args(argv)
        report = inspect(args.config, args.runtime_dir)
        data = json.dumps(report, ensure_ascii=True, allow_nan=False, sort_keys=True, indent=2)
        if len(data.encode('utf-8')) > 16384:
            raise ValueError('Report bound')
    except (OSError, ValueError, TypeError, RuntimeError, AttributeError):
        report = {'schema_version': 1, 'result': 'BLOCKED', 'code': 'INSPECTION_UNAVAILABLE',
                  'robot_ready': None, 'mutation_authorized': False, 'daemon_requests_sent': 0, 'system_changed': False}
        data = json.dumps(report, sort_keys=True)
    print(data)
    return 2 if report['result'] == 'BLOCKED' else 0


if __name__ == '__main__':
    raise SystemExit(main())
