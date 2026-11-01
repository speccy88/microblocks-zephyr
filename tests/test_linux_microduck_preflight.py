#!/usr/bin/env python3
"""Read-only inspection with real private filesystem fixtures, never robot I/O."""
# SPDX-License-Identifier: MIT
from contextlib import ExitStack, redirect_stdout
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('microduck_preflight_test')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
preflight = importlib.import_module(package.__name__ + '.preflight')
gateway = importlib.import_module(package.__name__ + '.gateway')
protocol = importlib.import_module(package.__name__ + '.protocol')
LINUX = sys.platform == 'linux' and hasattr(socket, 'AF_UNIX')


def fixture_host():
    host = {'system': 'Linux', 'machine': 'aarch64', 'pointer_bits': 64,
            'python': [3, 11, 0], 'effective_uid': 1000, 'glibc_version': '2.39'}
    checks = [preflight.check(name, 'PASS', 'SIMULATED_HOST_FIELD') for name in
              ('linux', 'arm64', 'python', 'unprivileged_user', 'unix_primitives', 'glibc')]
    return host, checks


class PreflightHost(unittest.TestCase):
    @unittest.skipUnless(LINUX, 'Linux prerequisite observations')
    def test_glibc_arm64_python_and_unprivileged_prerequisites(self):
        with patch.object(preflight.platform, 'system', return_value='Linux'), patch.object(preflight.platform, 'machine', return_value='aarch64'), patch.object(preflight.platform, 'libc_ver', return_value=('glibc', '2.34')), patch.object(preflight.os, 'geteuid', return_value=1000):
            host, checks = preflight.host_observation()
        self.assertEqual(host['glibc_version'], '2.34')
        self.assertTrue(all(row['status'] == 'PASS' for row in checks))

    @unittest.skipUnless(LINUX, 'Linux prerequisite observations')
    def test_old_unknown_or_malformed_libc_is_not_compatible_by_default(self):
        for libc, version, expected in [('glibc', '2.33', 'FAIL'), ('glibc', '', 'UNKNOWN'), ('musl', '1.2.3', 'UNKNOWN'), ('glibc', 'SECRET-INVALID', 'UNKNOWN')]:
            with self.subTest(version=version), patch.object(preflight.platform, 'libc_ver', return_value=(libc, version)):
                host, checks = preflight.host_observation()
            self.assertEqual(next(row for row in checks if row['name'] == 'glibc')['status'], expected)
            self.assertNotIn('SECRET', json.dumps(host))

    @unittest.skipUnless(LINUX, 'Linux prerequisite observations')
    def test_wrong_architecture_root_and_missing_primitives_are_blockers(self):
        with patch.object(preflight.platform, 'machine', return_value='x86_64'), patch.object(preflight.os, 'geteuid', return_value=0):
            _, checks = preflight.host_observation()
        self.assertEqual(next(row for row in checks if row['name'] == 'arm64')['status'], 'FAIL')
        self.assertEqual(next(row for row in checks if row['name'] == 'unprivileged_user')['status'], 'FAIL')
        host, checks = fixture_host()
        host['system'] = 'Windows'
        with patch.object(preflight, 'host_observation', return_value=(host, checks)), patch.object(preflight, 'load_config', side_effect=AssertionError('Must not read config')):
            result = preflight.inspect('/do-not-read', '/do-not-stat')
        self.assertEqual(result['config']['status'], 'NOT_CHECKED')
        self.assertEqual(result['runtime_directory']['status'], 'NOT_CHECKED')

    def test_cli_json_never_claims_robot_readiness_or_sends_a_request(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'linux/microduck/preflight.py')], capture_output=True, text=True, timeout=15)
        self.assertIn(result.returncode, (0, 2))
        report = json.loads(result.stdout)
        self.assertIn(report['result'], ('INCOMPLETE', 'BLOCKED'))
        self.assertIsNone(report['robot_ready'])
        self.assertFalse(report['mutation_authorized'])
        self.assertEqual(report['daemon_requests_sent'], 0)
        self.assertEqual(result.stderr, '')

    def test_unknown_cli_arguments_are_fixed_json_without_echoing_secret_values(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'linux/microduck/preflight.py'), '--unknown', 'SECRET-INPUT'], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['code'], 'INSPECTION_UNAVAILABLE')
        self.assertNotIn('SECRET-INPUT', result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')


@unittest.skipUnless(LINUX, 'Private Linux Unix/filesystem fixtures')
class ReadOnlyPreflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mb-preflight-', dir='/tmp')
        self.root = Path(self.temp.name)
        self.sockets = []

    def tearDown(self):
        for sock in self.sockets:
            sock.close()
        self.temp.cleanup()

    def service(self, name='robot'):
        path = self.root / (name + '.sock')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(path))  # Metadata fixture only: never listen or accept.
        os.chmod(path, 0o660)
        self.sockets.append(sock)
        return {'path': str(path), 'uid': os.geteuid()}

    def config(self, upstreams, raw=None):
        path = self.root / 'config.json'
        path.write_bytes(raw if raw is not None else json.dumps({'version': 1, 'upstreams': upstreams}).encode())
        os.chmod(path, 0o600)
        return path

    def inspect(self, *args, **kwargs):
        with patch.object(preflight, 'host_observation', return_value=fixture_host()):
            return preflight.inspect(*args, **kwargs)

    def test_omitted_inputs_are_not_checked_and_even_a_compatible_host_is_incomplete(self):
        result = self.inspect()
        self.assertEqual(result['result'], 'INCOMPLETE')
        self.assertEqual(result['config']['status'], 'NOT_CHECKED')
        self.assertEqual(result['runtime_directory']['status'], 'NOT_CHECKED')
        self.assertEqual(result['upstreams'], {})
        self.assertEqual(result['expected_api_version'], 44)
        self.assertIsNone(result['daemon_api_version_observed'])
        self.assertFalse(result['connected_peer_uids_verified'])

    def test_valid_metadata_uses_no_connection_process_or_write_and_remains_incomplete(self):
        config = self.config({name: self.service(name) for name in ('robot', 'config', 'updater')})
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        before = {path.name: (path.lstat().st_ino, path.lstat().st_mode) for path in self.root.iterdir()}
        content = config.read_bytes()
        original_open = os.open

        def readonly_open(path, flags, *args, **kwargs):
            self.assertEqual(flags & os.O_ACCMODE, os.O_RDONLY)
            self.assertFalse(flags & (os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            return original_open(path, flags, *args, **kwargs)

        forbidden = AssertionError('Inspection must not connect, execute or write')
        with ExitStack() as stack:
            stack.enter_context(patch.object(preflight.os, 'open', side_effect=readonly_open))
            for target, name in [(socket, 'socket'), (socket, 'create_connection'), (subprocess, 'run'), (os, 'chmod'), (os, 'mkdir'), (os, 'unlink'), (Path, 'write_text'), (Path, 'write_bytes'), (protocol, 'connect_checked'), (gateway.Gateway, 'start')]:
                stack.enter_context(patch.object(target, name, side_effect=forbidden))
            result = self.inspect(config, runtime)
        self.assertEqual(result['result'], 'INCOMPLETE')
        self.assertEqual(result['config']['status'], 'PASS')
        self.assertEqual(result['runtime_directory']['status'], 'PASS')
        self.assertFalse(result['runtime_directory']['write_probe_performed'])
        self.assertGreater(result['runtime_directory']['available_bytes'], 0)
        self.assertEqual(set(result['upstreams']), {'robot', 'config', 'updater'})
        for row in result['upstreams'].values():
            self.assertEqual(row['status'], 'PASS')
            self.assertEqual(row['socket_file_uid'], os.geteuid())
            self.assertIsNone(row['connected_peer_uid'])
            self.assertFalse(row['peer_verified'])
        self.assertEqual(config.read_bytes(), content)
        self.assertEqual(before, {path.name: (path.lstat().st_ino, path.lstat().st_mode) for path in self.root.iterdir()})
        self.assertFalse(result['physical_microduck_tested'])
        self.assertFalse(result['system_changed'])

    def test_individual_service_configuration_is_supported_without_inventing_other_peers(self):
        result = self.inspect(self.config({'robot': self.service()}))
        self.assertEqual(set(result['upstreams']), {'robot'})
        self.assertEqual(result['result'], 'INCOMPLETE')

    def test_nonprivate_and_foreign_configuration_is_refused_without_repair(self):
        config = self.config({'robot': self.service()})
        os.chmod(config, 0o644)
        self.assertEqual(self.inspect(config)['config']['status'], 'FAIL')
        self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o644)
        os.chmod(config, 0o600)
        meta = config.stat()
        with patch.object(gateway.os, 'fstat', return_value=types.SimpleNamespace(st_mode=meta.st_mode, st_uid=meta.st_uid + 1, st_size=meta.st_size)):
            self.assertEqual(self.inspect(config)['config']['status'], 'FAIL')

    def test_schema_uid_and_path_bounds_reject_unknown_or_unsafe_configuration(self):
        peer = self.service()
        invalid = [{}, {'other': peer}, {'robot': {'path': peer['path'], 'uid': True}}, {'robot': {'path': peer['path'], 'uid': -1}}, {'robot': {'path': peer['path'], 'uid': 2**32}}, {'robot': {'path': 'relative.sock', 'uid': os.geteuid()}}, {'robot': {'path': peer['path'], 'uid': os.geteuid(), 'extra': 'SECRET'}}]
        for value in invalid:
            with self.subTest(value=value):
                result = self.inspect(self.config(value))
                self.assertEqual(result['config']['status'], 'FAIL')
                self.assertEqual(result['upstreams'], {})
                self.assertNotIn('SECRET', json.dumps(result))

    def test_malformed_duplicate_nonfinite_and_oversized_input_is_bounded(self):
        for raw in [b'{"version":1,"version":1,"upstreams":{}}', b'{"version":NaN}', b'\xff', b'[]', b'x' * 8193]:
            with self.subTest(raw=raw[:24]):
                result = self.inspect(self.config({}, raw=raw))
                self.assertEqual(result['config']['status'], 'FAIL')
                self.assertLess(len(json.dumps(result)), 16384)

    def test_symlink_and_fifo_configurations_are_refused_without_blocking(self):
        config = self.config({'robot': self.service()})
        link = self.root / 'config-link'
        link.symlink_to(config)
        fifo = self.root / 'config-fifo'
        os.mkfifo(fifo, 0o600)
        for path in (link, fifo):
            self.assertEqual(self.inspect(path)['config']['status'], 'FAIL')

    def test_configuration_contents_and_sensitive_path_text_are_never_echoed(self):
        path = self.root / 'SECRET-CONFIG-NAME'
        path.write_text('{"password":"SECRET-CONTENT"}')
        os.chmod(path, 0o600)
        text = json.dumps(self.inspect(path, self.root / 'SECRET-RUNTIME-NAME'))
        self.assertNotIn('SECRET', text)
        self.assertNotIn(str(self.root), text)

    def test_missing_regular_or_symlink_upstream_is_not_a_trusted_socket(self):
        real = self.service()
        regular = self.root / 'ordinary-file'
        regular.write_text('fixture')
        link = self.root / 'socket-link'
        link.symlink_to(real['path'])
        for path in (self.root / 'missing.sock', regular, link):
            result = self.inspect(self.config({'robot': {'path': str(path), 'uid': os.geteuid()}}))
            self.assertEqual(result['upstreams']['robot']['status'], 'FAIL')
            self.assertEqual(result['result'], 'BLOCKED')

    def test_wrong_socket_uid_or_modes_are_blockers_without_permission_changes(self):
        peer = self.service()
        self.assertEqual(self.inspect(self.config({'robot': {**peer, 'uid': peer['uid'] + 1}}))['upstreams']['robot']['status'], 'FAIL')
        os.chmod(peer['path'], 0o667)
        self.assertEqual(self.inspect(self.config({'robot': peer}))['upstreams']['robot']['status'], 'FAIL')
        self.assertEqual(stat.S_IMODE(Path(peer['path']).stat().st_mode), 0o667)
        os.chmod(peer['path'], 0o660)
        os.chmod(self.root, 0o720)
        self.assertEqual(self.inspect(self.config({'robot': peer}))['upstreams']['robot']['status'], 'FAIL')
        os.chmod(self.root, 0o700)

    def test_alias_parents_are_refused_without_resolving_away_the_warning(self):
        peer = self.service()
        config = self.config({'robot': peer})
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.inspect(alias / config.name)['config']['status'], 'FAIL')
        result = self.inspect(self.config({'robot': {**peer, 'path': str(alias / 'robot.sock')}}))
        self.assertEqual(result['upstreams']['robot']['status'], 'FAIL')

    def test_private_runtime_observation_detects_readonly_mount_without_a_write_probe(self):
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        space = types.SimpleNamespace(f_bavail=2, f_frsize=4096, f_flag=getattr(os, 'ST_RDONLY', 1))
        with patch.object(preflight.os, 'statvfs', return_value=space):
            result = self.inspect(runtime_dir=runtime)
        self.assertEqual(result['runtime_directory']['code'], 'RUNTIME_FILESYSTEM_READONLY')
        self.assertEqual(result['runtime_directory']['available_bytes'], 8192)
        self.assertFalse(result['runtime_directory']['write_probe_performed'])
        self.assertEqual(result['result'], 'BLOCKED')

    def test_runtime_missing_type_owner_mode_or_alias_cannot_become_ready(self):
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        alias = self.root / 'runtime-alias'
        alias.symlink_to(runtime, target_is_directory=True)
        regular = self.root / 'file'
        regular.write_text('fixture')
        for path in (self.root / 'missing', regular, alias):
            self.assertEqual(self.inspect(runtime_dir=path)['runtime_directory']['status'], 'FAIL')
        os.chmod(runtime, 0o755)
        self.assertEqual(self.inspect(runtime_dir=runtime)['runtime_directory']['status'], 'FAIL')
        os.chmod(runtime, 0o700)
        with patch.object(preflight.os, 'geteuid', return_value=os.geteuid() + 1):
            self.assertEqual(preflight.inspect_runtime(runtime)['status'], 'FAIL')

    def test_unknown_or_invalid_space_is_not_silently_reported_as_zero(self):
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        for side_effect in (PermissionError('SECRET'), None):
            with self.subTest(error=side_effect), patch.object(preflight.os, 'statvfs', side_effect=side_effect, return_value=types.SimpleNamespace(f_bavail=-1, f_frsize=4096, f_flag=0)):
                row = self.inspect(runtime_dir=runtime)['runtime_directory']
            self.assertEqual(row['status'], 'UNKNOWN')
            self.assertIsNone(row['available_bytes'])
            self.assertNotIn('SECRET', json.dumps(row))

    def test_changed_inode_metadata_is_refused_as_an_observation_not_repaired(self):
        peer = self.service()
        config = self.config({'robot': peer})
        identity = protocol.socket_identity(peer['path'], peer['uid'])
        with patch.object(preflight, 'socket_identity', side_effect=[identity, (identity[0], identity[1] + 1)]):
            row = self.inspect(config)['upstreams']['robot']
        self.assertEqual(row['code'], 'SOCKET_METADATA_CHANGED')
        self.assertFalse(row['peer_verified'])

    def test_cli_does_not_create_bytecode_caches_or_any_output_files(self):
        snapshot = self.root / 'source'
        snapshot.mkdir(mode=0o700)
        for name in ('preflight.py', 'gateway.py', 'protocol.py'):
            shutil.copyfile(ROOT / 'linux/microduck' / name, snapshot / name)
        before = sorted(path.name for path in snapshot.iterdir())
        result = subprocess.run([sys.executable, str(snapshot / 'preflight.py')], cwd=snapshot, capture_output=True, text=True, timeout=15)
        self.assertIn(result.returncode, (0, 2))
        self.assertIn(json.loads(result.stdout)['result'], ('INCOMPLETE', 'BLOCKED'))
        self.assertEqual(result.stderr, '')
        self.assertEqual(before, sorted(path.name for path in snapshot.iterdir()))

    def test_zero_cli_exit_is_only_incomplete_and_no_input_path_is_echoed(self):
        output = io.StringIO()
        with patch.object(preflight, 'host_observation', return_value=fixture_host()), redirect_stdout(output):
            code = preflight.main([])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report['result'], 'INCOMPLETE')
        self.assertIsNone(report['robot_ready'])
        self.assertFalse(report['mutation_authorized'])
        output = io.StringIO()
        with patch.object(preflight, 'host_observation', return_value=fixture_host()), redirect_stdout(output):
            code = preflight.main(['--config', str(self.root / 'SECRET-MISSING')])
        self.assertEqual(code, 2)
        self.assertNotIn('SECRET', output.getvalue())


if __name__ == '__main__':
    unittest.main()
