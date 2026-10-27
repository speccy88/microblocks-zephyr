#!/usr/bin/env python3
"""Real unprivileged Pi installation lifecycle in an explicitly fresh directory.

Uses actual ARM64 packages, shell installers and interpreter PTY operations.
Creates no service and leaves the private test prefix/data for inspection.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
from linux_arm64_protocol import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--version-one', required=True)
    parser.add_argument('--version-two', required=True)
    args = parser.parse_args()
    base = args.base.resolve()
    assert platform.machine() == 'aarch64' and os.geteuid() != 0
    assert base.is_dir() and not base.is_symlink()
    prefix = base / 'install'
    data = base / 'programs'
    assert not prefix.exists() and not data.exists(), 'Use a fresh test directory'
    checks = {}
    env = dict(os.environ, XDG_CONFIG_HOME=str(base / 'config'))
    def command(argv, expect_success=True):
        result = subprocess.run(argv, cwd=base, env=env, capture_output=True, text=True, timeout=30)
        with (base / 'lifecycle.log').open('a') as log:
            log.write(json.dumps(argv) + '\n' + result.stdout + result.stderr + '\n')
        assert (result.returncode == 0) == expect_success, result.stdout + result.stderr
        return result
    def install(version, digest=None):
        archive = base / (version + '.tar.gz')
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        return command(['bash', str(base / 'install.sh'), '--version', version,
                        '--sha256', digest or actual, '--archive', str(archive),
                        '--prefix', str(prefix), '--data-dir', str(data)], digest != '0' * 64)
    launcher = prefix / 'bin/smallvm'
    install(args.version_one)
    checks['native_install_self_test'] = True
    assert data.stat().st_mode & 0o777 == 0o700
    interpreter = Runtime(launcher, data, 1)
    reporter = bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
    try:
        crc = interpreter.wire.upload(0, reporter, 2)
        assert interpreter.wire.reporter(0) == 12
    finally:
        interpreter.stop()
    original = (data / 'program.ucode').read_bytes()
    install(args.version_one)
    assert (data / 'program.ucode').read_bytes() == original
    checks['repeat_install_preserves_real_program'] = True
    old_launcher = launcher.read_bytes()
    install(args.version_two, '0' * 64)
    assert launcher.read_bytes() == old_launcher and (data / 'program.ucode').read_bytes() == original
    checks['checksum_failure_preserves_active_install'] = True
    install(args.version_two)
    assert launcher.read_bytes() != old_launcher and (data / 'program.ucode').read_bytes() == original
    interpreter = Runtime(launcher, data, 2)
    try:
        assert interpreter.wire.crc(0) == crc and interpreter.wire.reporter(0) == 12
    finally:
        interpreter.stop()
    checks['upgrade_restores_real_bytecode_and_executes'] = True
    for version in (args.version_one, args.version_two):
        assert (prefix / 'lib/microblocks' / version / 'smallvm').is_file()
    checks['prior_version_retained'] = True
    command(['bash', str(base / 'uninstall.sh'), '--prefix', str(prefix)])
    assert not launcher.exists() and (data / 'program.ucode').read_bytes() == original
    checks['uninstall_preserves_programs_and_binaries'] = True
    assert not (base / 'config/systemd/user/microblocks-smallvm.service').exists()
    report = {'result': 'PASS', 'architecture': platform.machine(), 'checks': checks,
              'service_created': False, 'os_reboot_tested': False,
              'test_directory': str(base)}
    (base / 'installer-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
