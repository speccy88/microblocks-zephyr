#!/usr/bin/env python3
"""Candidate provenance contracts; synthetic fixtures are never executed."""
# SPDX-License-Identifier: MIT
import copy
import importlib.util
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_candidate', ROOT / 'tools/prepare_linux_arm64_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseContracts(unittest.TestCase):
    def setUp(self):
        data = bytearray(64)
        data[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', data, 18, 183)
        self.binary = bytes(data)
        self.manifest = {'source_commit': release.COMMIT, 'sanitize': False,
                         'sources': {'vm/test.c': {'prepared_sha256': release.digest(b'test')}}}
        self.report = {'result': 'PASS', 'source_commit': release.COMMIT,
                       'host': {'architecture': 'aarch64', 'sanitizers': False, 'source_hashes_verified': 1},
                       'binary_sha256': release.digest(self.binary),
                       'protocol': {'result': 'PASS', 'architecture': 'aarch64', 'binary_sha256': release.digest(self.binary)},
                       'self_test': {'result': 'PASS', 'architecture': 'aarch64'}}

    def test_evidence_rejects_each_broken_binding(self):
        release.verify_evidence(self.binary, self.manifest, self.report)
        for location, key, bad in [('', 'result', 'FAIL'), ('', 'source_commit', '0' * 40),
                                   ('', 'binary_sha256', '0' * 64), ('host', 'architecture', 'x86_64'),
                                   ('host', 'sanitizers', True), ('host', 'source_hashes_verified', 2),
                                   ('protocol', 'result', 'FAIL'), ('protocol', 'architecture', 'x86_64'),
                                   ('protocol', 'binary_sha256', '0' * 64), ('self_test', 'result', 'FAIL')]:
            with self.subTest(location=location, key=key):
                report = copy.deepcopy(self.report)
                (report[location] if location else report)[key] = bad
                with self.assertRaises(ValueError):
                    release.verify_evidence(self.binary, self.manifest, report)
        for key, bad in [('sanitize', True), ('source_commit', '0' * 40), ('sources', {})]:
            with self.assertRaises(ValueError):
                release.verify_evidence(self.binary, dict(self.manifest, **{key: bad}), self.report)
        with self.assertRaises(ValueError):
            release.verify_evidence(b'not executable', self.manifest, self.report)

    def test_source_archive_is_deterministic_and_rejects_unsafe_paths(self):
        entries = {'prepared/test.c': b'test', 'prepared/build.sh': b'build'}
        raw = release.archive_bytes(entries, 42)
        self.assertEqual(raw, release.archive_bytes(dict(reversed(list(entries.items()))), 42))
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            self.assertEqual(archive.getnames(), ['prepared/build.sh', 'prepared/test.c'])
            self.assertEqual(archive.getmember('prepared/build.sh').mode, 0o755)
            self.assertTrue(all(m.uid == 0 and m.mtime == 42 and m.isfile() for m in archive.getmembers()))
        for name in ['/absolute', '../escape', 'prepared/../escape', 'prepared\\escape', './same']:
            with self.assertRaises(ValueError):
                release.archive_bytes({name: b'no'}, 0)

    def test_candidate_binds_source_and_remains_unpublished(self):
        parent = ROOT / 'build-artifacts/linux-arm64-tests'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temp:
            work = Path(temp)
            binary, manifest, report = (work / name for name in ('vm', 'manifest.json', 'report.json'))
            binary.write_bytes(self.binary)
            manifest.write_bytes(release.encoded(self.manifest))
            report.write_bytes(release.encoded(self.report))
            def prepared(upstream, staged, sanitize):
                staged.mkdir()
                (staged / 'LICENSE').write_bytes(b'MPL fixture')
                (staged / 'test.c').write_bytes(b'test')
                (staged / 'build.sh').write_bytes(b'not executable fixture')
                return self.manifest
            recipe = {'scripts/install-smallvm-linux-arm64.sh': b'installer fixture',
                      'scripts/uninstall-smallvm-linux-arm64.sh': b'uninstaller fixture'}
            with patch.object(release, 'git', side_effect=lambda *args: b'1' * 40 if args[0] == 'rev-parse' else b'42'), \
                    patch.object(release, 'committed_inputs', return_value=(recipe, {})), patch.object(release, 'prepare', side_effect=prepared):
                kwargs = dict(binary_path=binary, manifest_path=manifest, report_path=report,
                              upstream=work, version='v417-fixture')
                first = release.prepare_candidate(output=work / 'a', **kwargs)
                second = release.prepare_candidate(output=work / 'b', **kwargs)
                self.assertEqual(first, second)
                self.assertFalse(first['published'])
                self.assertFalse(first['available'])
                for path in (work / 'a').iterdir():
                    self.assertEqual(path.read_bytes(), (work / 'b' / path.name).read_bytes())
                for line in (work / 'a/SHA256SUMS').read_text().splitlines():
                    checksum, name = line.split('  ')
                    self.assertEqual(checksum, release.digest((work / 'a' / name).read_bytes()))
                package = work / 'a/smallvm-linux-arm64-v417-fixture.tar.gz'
                with tarfile.open(package) as archive:
                    metadata = json.load(archive.extractfile('manifest.json'))
                    self.assertEqual(metadata['provenance']['port_commit'], '1' * 40)
                    self.assertEqual(metadata['provenance']['source_archive_sha256'], first['source_archive_sha256'])
                    self.assertIn(first['source_archive_sha256'].encode(), archive.extractfile('NOTICE').read())
                with self.assertRaises(FileExistsError):
                    release.prepare_candidate(output=work / 'a', **kwargs)
                with patch.object(release, 'prepare', return_value={'changed': True}):
                    with self.assertRaises(ValueError):
                        release.prepare_candidate(output=work / 'changed', **kwargs)
                    self.assertFalse((work / 'changed').exists())

    def test_dirty_and_untracked_native_inputs_are_rejected(self):
        # Real source bytes are read, but no Git state or file is changed.
        with patch.object(release, 'git', side_effect=[b'linux/arm64/build.py\0', b'different']):
            with self.assertRaisesRegex(ValueError, 'differs from port commit'):
                release.committed_inputs('1' * 40)
        with patch.object(release, 'git', return_value=b''):
            with self.assertRaisesRegex(ValueError, 'file set differs'):
                release.committed_inputs('1' * 40)


if __name__ == '__main__':
    unittest.main()
