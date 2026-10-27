#!/usr/bin/env python3
"""Exercise the real installer in verification mode; never run fixture binaries.

Run under Linux: python3 -m unittest discover -s tests -p test_linux_arm64_installer.py
Fixtures have a syntactically valid ELF header, not a working SmallVM binary.
"""
# SPDX-License-Identifier: MIT
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'scripts/install-smallvm-linux-arm64.sh'
VERSION = 'linux-arm64-v417-test1'
COMMIT = '2071df569623ba9cdcd6f8106b61796e047df38b'


class InstallerFixture(unittest.TestCase):
    def setUp(self):
        # Use the native Linux temporary filesystem. Windows-mounted DrvFS
        # may report 0777 regardless of chmod, which cannot test privacy modes.
        self.temporary = tempfile.TemporaryDirectory(prefix='smallvm-installer-test-')
        self.work = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, *, version=VERSION, payload=b'', architecture='linux-aarch64', commit=COMMIT, machine=183, extra=None, omit=None, duplicate=False, symlink=False):
        binary = bytearray(64)
        binary[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', binary, 18, machine)
        files = {
            'smallvm': bytes(binary) + payload,
            'manifest.json': json.dumps({'version': version, 'architecture': architecture, 'source_commit': commit}).encode(),
            'LICENSE': b'MPL-2.0 test fixture; no executable implementation\n',
        }
        if extra:
            files.update(extra)
        if omit:
            files.pop(omit)
        path = self.work / 'release.tar.gz'
        with tarfile.open(path, 'w:gz') as bundle:
            for name, data in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                bundle.addfile(member, io.BytesIO(data))
            if duplicate:
                member = tarfile.TarInfo('LICENSE'); member.size = 0
                bundle.addfile(member, io.BytesIO())
            if symlink:
                member = tarfile.TarInfo('NOTICE'); member.type = tarfile.SYMTYPE; member.linkname = '/etc/passwd'
                bundle.addfile(member)
        return path

    def run_installer(self, archive, *, digest=None, version=VERSION, extra=()):
        digest = digest or hashlib.sha256(archive.read_bytes()).hexdigest()
        return subprocess.run(['bash', str(SCRIPT), '--verify-only', '--archive', str(archive),
                               '--version', version, '--sha256', digest,
                               '--prefix', str(self.work / 'prefix'), '--data-dir', str(self.work / 'programs'),
                               *extra], text=True, capture_output=True)


@unittest.skipUnless(shutil.which('bash') and __import__('sys').platform == 'linux', 'requires Linux bash')
class InstallerVerification(InstallerFixture):
    def test_valid_package_verified_without_execution_or_installation(self):
        result = self.run_installer(self.archive())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('executable not run', result.stdout)
        self.assertFalse((self.work / 'prefix').exists())
        self.assertFalse((self.work / 'programs').exists())

    def test_checksum_failure(self):
        result = self.run_installer(self.archive(), digest='0' * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('checksum mismatch', result.stderr)

    def test_archive_traversal_rejected(self):
        result = self.run_installer(self.archive(extra={'../escaped': b'bad'}))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work.parent / 'escaped').exists())

    def test_symlink_rejected(self):
        self.assertNotEqual(self.run_installer(self.archive(symlink=True)).returncode, 0)

    def test_duplicate_rejected(self):
        self.assertNotEqual(self.run_installer(self.archive(duplicate=True)).returncode, 0)

    def test_missing_license_rejected(self):
        self.assertNotEqual(self.run_installer(self.archive(omit='LICENSE')).returncode, 0)

    def test_wrong_elf_architecture_rejected(self):
        result = self.run_installer(self.archive(machine=62))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AArch64', result.stderr)

    def test_wrong_manifest_architecture_rejected(self):
        self.assertNotEqual(self.run_installer(self.archive(architecture='linux-x86_64')).returncode, 0)

    def test_unreviewed_source_rejected(self):
        self.assertNotEqual(self.run_installer(self.archive(commit='f' * 40)).returncode, 0)

    def test_latest_rejected(self):
        self.assertNotEqual(self.run_installer(self.archive(), version='latest').returncode, 0)

    def test_version_shell_injection_rejected(self):
        result = self.run_installer(self.archive(), version='v417;touch bad')
        self.assertNotEqual(result.returncode, 0)

    def test_repeated_verification_preserves_existing_program(self):
        program_dir = self.work / 'programs'; program_dir.mkdir()
        program = program_dir / 'ublockscode'; program.write_bytes(b'original program')
        archive = self.archive()
        for _ in range(2):
            result = self.run_installer(archive)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(program.read_bytes(), b'original program')

    def test_missing_hash_rejected(self):
        result = subprocess.run(['bash', str(SCRIPT), '--verify-only', '--version', VERSION], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_service_expansion_characters_rejected(self):
        archive = self.archive()
        for path in ['/tmp/$EXPANSION', '/tmp/path\rcontrol', '/tmp/path\tcontrol', '/tmp/percent%name']:
            result = self.run_installer(archive, extra=('--prefix', path))
            self.assertNotEqual(result.returncode, 0, path)
            self.assertIn('Unsupported characters', result.stderr)

    def test_shell_syntax(self):
        for name in ['install-smallvm-linux-arm64.sh', 'uninstall-smallvm-linux-arm64.sh']:
            result = subprocess.run(['bash', '-n', str(REPO / 'scripts' / name)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(shutil.which('bash') and __import__('sys').platform == 'linux' and os.geteuid() != 0,
                     'requires unprivileged Linux bash')
class InstallerLifecycle(InstallerFixture):
    """Real filesystem lifecycle, mocked architecture/binary test/systemd only."""
    def setUp(self):
        super().setUp()
        fakebin = self.work / 'fakebin'; fakebin.mkdir()
        for name, script in {
            'uname': '#!/bin/sh\ncase "$1" in -m) echo aarch64;; -s) echo Linux;; *) exit 1;; esac\n',
            'timeout': '#!/bin/sh\n# The ELF fixture is never executed.\nexit "${TEST_SELFTEST_EXIT:-0}"\n',
            'systemctl': '#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_SYSTEMCTL_LOG"\nexit 0\n',
        }.items():
            path = fakebin / name; path.write_text(script); path.chmod(0o700)
        self.environment = dict(os.environ)
        self.environment.update(PATH=str(fakebin) + os.pathsep + os.environ['PATH'],
                                HOME=str(self.work / 'home'), XDG_CONFIG_HOME=str(self.work / 'config'),
                                TEST_SYSTEMCTL_LOG=str(self.work / 'systemctl.log'))

    def install(self, archive, *, version=VERSION, service=False):
        arguments = ['bash', str(SCRIPT), '--archive', str(archive), '--version', version,
                     '--sha256', hashlib.sha256(archive.read_bytes()).hexdigest(),
                     '--prefix', str(self.work / 'prefix'), '--data-dir', str(self.work / 'programs')]
        if service:
            arguments.append('--service')
        return subprocess.run(arguments, text=True, capture_output=True, env=self.environment)

    def test_mock_target_install_reinstall_and_uninstall_preserves_program(self):
        archive = self.archive()
        for _ in range(2):
            result = self.install(archive)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        program = self.work / 'programs/ublockscode'; program.write_bytes(b'original program')
        launcher = self.work / 'prefix/bin/smallvm'
        self.assertIn(VERSION, launcher.read_text())
        result = subprocess.run(['bash', str(REPO / 'scripts/uninstall-smallvm-linux-arm64.sh'),
                                 '--prefix', str(self.work / 'prefix')], capture_output=True, text=True,
                                env=self.environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(launcher.exists())
        self.assertEqual(program.read_bytes(), b'original program')
        self.assertTrue((self.work / f'prefix/lib/microblocks/{VERSION}/smallvm').exists())

    def test_mock_target_upgrade_retains_old_binary_and_program(self):
        result = self.install(self.archive())
        self.assertEqual(result.returncode, 0, result.stderr)
        program = self.work / 'programs/ublockscode'; program.write_bytes(b'keep')
        newer = VERSION + '-2'
        result = self.install(self.archive(version=newer, payload=b'new candidate'), version=newer)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(newer, (self.work / 'prefix/bin/smallvm').read_text())
        self.assertEqual(program.read_bytes(), b'keep')
        self.assertTrue((self.work / f'prefix/lib/microblocks/{VERSION}/smallvm').exists())

    def test_launcher_supplies_private_data_path_and_keeps_selftest_isolated(self):
        result = self.install(self.archive())
        self.assertEqual(result.returncode, 0, result.stderr)
        executable = self.work / f'prefix/lib/microblocks/{VERSION}/smallvm'
        # Capture actual exec arguments without running the AArch64 ELF fixture.
        executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        executable.chmod(0o700)
        launcher = self.work / 'prefix/bin/smallvm'
        normal = subprocess.run([str(launcher), '--help'], capture_output=True, text=True)
        self.assertEqual(normal.returncode, 0, normal.stderr)
        self.assertEqual(normal.stdout.splitlines(), ['--data-dir', str(self.work / 'programs'), '--help'])
        isolated = subprocess.run([str(launcher), '--self-test'], capture_output=True, text=True)
        self.assertEqual(isolated.returncode, 0, isolated.stderr)
        self.assertEqual(isolated.stdout.splitlines(), ['--self-test'])
        self.assertEqual(stat.S_IMODE((self.work / 'programs').stat().st_mode), 0o700)

    def test_symlink_data_directory_refused_without_touching_target(self):
        target = self.work / 'other-data'; target.mkdir()
        keep = target / 'keep'; keep.write_bytes(b'preserve')
        (self.work / 'programs').symlink_to(target, target_is_directory=True)
        result = self.install(self.archive())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('symlink', result.stderr)
        self.assertEqual(keep.read_bytes(), b'preserve')

    def test_mock_target_selftest_failure_preserves_active_launcher(self):
        result = self.install(self.archive())
        self.assertEqual(result.returncode, 0, result.stderr)
        launcher = self.work / 'prefix/bin/smallvm'; original = launcher.read_bytes()
        self.environment['TEST_SELFTEST_EXIT'] = '1'
        newer = VERSION + '-2'
        result = self.install(self.archive(version=newer), version=newer)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(launcher.read_bytes(), original)
        self.assertFalse((self.work / f'prefix/lib/microblocks/{newer}').exists())

    def test_mock_target_unrelated_launcher_preserved(self):
        launcher = self.work / 'prefix/bin/smallvm'; launcher.parent.mkdir(parents=True)
        launcher.write_bytes(b'unrelated program')
        result = self.install(self.archive())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(launcher.read_bytes(), b'unrelated program')
        self.assertFalse((self.work / 'prefix/lib/microblocks').exists())

    def test_mock_target_service_is_opt_in_and_user_scoped(self):
        result = self.install(self.archive(), service=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = self.work / 'config/systemd/user/microblocks-smallvm.service'
        self.assertTrue(unit.exists())
        log = (self.work / 'systemctl.log').read_text()
        self.assertIn('--user enable --now microblocks-smallvm.service', log)
        self.assertIn('--user restart microblocks-smallvm.service', log)
        self.assertNotIn('sudo', log)

    def test_existing_release_manifest_corruption_refuses_reinstall(self):
        archive = self.archive()
        result = self.install(archive)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.work / f'prefix/lib/microblocks/{VERSION}/manifest.json'
        manifest.write_text('{}')
        result = self.install(archive)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('identity', result.stderr)
        self.assertEqual(manifest.read_text(), '{}')

    def test_other_prefix_service_is_not_replaced_or_uninstalled(self):
        result = self.install(self.archive(), service=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = self.work / 'config/systemd/user/microblocks-smallvm.service'
        original = unit.read_bytes()
        # The selected service now belongs to a distinct prefix.
        unit.write_text(unit.read_text().replace(str(self.work / 'prefix'), str(self.work / 'different-prefix')))
        foreign = unit.read_bytes()
        result = self.install(self.archive(), service=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(unit.read_bytes(), foreign)
        before = (self.work / 'systemctl.log').read_bytes()
        result = subprocess.run(['bash', str(REPO / 'scripts/uninstall-smallvm-linux-arm64.sh'),
                                 '--prefix', str(self.work / 'prefix')], capture_output=True, text=True,
                                env=self.environment)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(unit.read_bytes(), foreign)
        self.assertEqual((self.work / 'systemctl.log').read_bytes(), before)

    def test_uninstall_unmanaged_prefix_refused(self):
        prefix = self.work / 'unmanaged'; prefix.mkdir()
        keep = prefix / 'keep'; keep.write_bytes(b'keep')
        result = subprocess.run(['bash', str(REPO / 'scripts/uninstall-smallvm-linux-arm64.sh'),
                                 '--prefix', str(prefix)], capture_output=True, env=self.environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(keep.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
