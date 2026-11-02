# SPDX-License-Identifier: MIT
import asyncio
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux/arm64'))
from browser_update import BrowserUpdater, UpdateError, SOURCE, begin_boot, confirm_boot, review_archive


def elf(machine=183):
    value = bytearray(80); value[:6] = b'\x7fELF\x02\x01'; struct.pack_into('<H', value, 18, machine)
    return bytes(value)


def bundle(path, *, version='pi417-test1', machine=183, vm=417, source=SOURCE, extra=None, duplicate=False, link=False, binary_digest=None):
    binary = elf(machine)
    metadata = {'version': version, 'architecture': 'linux-aarch64', 'vm_version': vm,
        'source_commit': source, 'binary_sha256': binary_digest or hashlib.sha256(binary).hexdigest()}
    entries = [('smallvm', binary), ('manifest.json', json.dumps(metadata).encode()), ('LICENSE', b'fixture')]
    if extra: entries.append(extra)
    if duplicate: entries.append(('LICENSE', b'duplicate'))
    with tarfile.open(path, 'w:gz') as archive:
        for name, content in entries:
            info = tarfile.TarInfo(name); info.size = len(content)
            if link and name == 'smallvm':
                info.type = tarfile.SYMTYPE; info.linkname = '/other'; info.size = 0
                archive.addfile(info)
            else: archive.addfile(info, io.BytesIO(content))
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), metadata


@unittest.skipUnless(sys.platform == 'linux', 'Native Linux update filesystem contracts')
class ReviewTests(unittest.TestCase):
    def test_native_candidate_and_wrong_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.tar.gz'; digest, _ = bundle(path)
            result = review_archive(path, digest)
            self.assertEqual(result['vm_version'], 417)
            with self.assertRaisesRegex(UpdateError, 'SHA-256 mismatch'):
                review_archive(path, '0' * 64)

    def test_unvalidated_versions_architecture_and_source_are_refused(self):
        for options in ({'vm': 421}, {'machine': 62}, {'source': '0' * 40}, {'version': 'latest'}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'package.tar.gz'; digest, _ = bundle(path, **options)
                with self.assertRaises(UpdateError): review_archive(path, digest)

    def test_paths_links_duplicates_and_oversize_headers_are_refused(self):
        for options in ({'extra': ('../escape', b'bad')}, {'duplicate': True}, {'link': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'package.tar.gz'; digest, _ = bundle(path, **options)
                with self.assertRaises(UpdateError): review_archive(path, digest)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'large.tar.gz'
            info = tarfile.TarInfo('smallvm'); info.size = 33 * 1024 * 1024
            path.write_bytes(gzip.compress(info.tobuf() + b'\0' * 1024))
            with self.assertRaises(UpdateError): review_archive(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_binary_manifest_checksum_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.tar.gz'; digest, _ = bundle(path, binary_digest='0' * 64)
            with self.assertRaisesRegex(UpdateError, 'executable checksum mismatch'):
                review_archive(path, digest)

    def test_corrupt_gzip_trailer_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.tar.gz'; digest, _ = bundle(path)
            data = path.read_bytes()
            path.write_bytes(data[:-20] + b'corrupt data')
            with self.assertRaises(UpdateError): review_archive(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_known_legacy_native_build_is_not_a_valid_upgrade(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'package.tar.gz'; digest, metadata = bundle(path)
            with patch('browser_update.REJECTED_NATIVE_SHA256', {metadata['binary_sha256']}):
                with self.assertRaisesRegex(UpdateError, 'predates required headless cleanup'):
                    review_archive(path, digest)


@unittest.skipUnless(sys.platform == 'linux', 'Native Linux update filesystem contracts')
class TransactionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'data').mkdir(); (self.root / 'data/program.ucode').write_bytes(b'original-program')
        self.config = {'schema': 1, 'vm_version': 417, 'binary': 'old/smallvm', 'binary_sha256': 'f' * 64,
            'editor': 'old/editor', 'data': 'data', 'origin': 'http://192.168.2.50', 'backend_port': 8877,
            'additional_origins': ['http://100.100.10.20', 'https://pi.tail-example.ts.net']}
        (self.root / 'service.json').write_text(json.dumps(self.config))
        self.quiesce = AsyncMock(); self.restarts = []
        async def install(archive, metadata):
            target = self.root / 'installed/lib/microblocks' / metadata['version'] / 'smallvm'
            target.parent.mkdir(parents=True); target.write_bytes(elf())
        self.updater = BrowserUpdater(self.root, self.root / 'installer', self.quiesce,
            lambda: self.restarts.append(True), allow_apply=True, install_runner=install)
        self.archive = self.root / 'upload.tar.gz'; self.digest, _ = bundle(self.archive)
        self.metadata = self.updater.prepare(self.archive, self.digest)
        self.send = AsyncMock()

    async def test_review_only_and_exact_confirmation(self):
        self.updater.allow_apply = False
        with self.assertRaisesRegex(UpdateError, 'not authorized'):
            await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        self.updater.allow_apply = True
        for digest, version, confirmed in [('0' * 64, 'pi417-test1', True), (self.digest, 'other', True), (self.digest, 'pi417-test1', False)]:
            with self.assertRaises(UpdateError): await self.updater.apply(digest, version, confirmed, self.send)
        self.quiesce.assert_not_awaited(); self.assertEqual(self.restarts, [])

    async def test_failed_native_validation_preserves_current_selection_and_program(self):
        self.updater.install_runner = AsyncMock(side_effect=UpdateError('native self-test failed'))
        with self.assertRaises(UpdateError):
            await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        self.assertEqual(json.loads((self.root / 'service.json').read_text()), self.config)
        self.assertEqual((self.root / 'data/program.ucode').read_bytes(), b'original-program')
        self.quiesce.assert_not_awaited(); self.assertEqual(self.restarts, [])

    async def test_required_host_capability_cannot_be_removed_by_an_update(self):
        config = dict(self.config, required_runtime_capabilities=['python-extensions'])
        (self.root / 'service.json').write_text(json.dumps(config))
        self.updater.install_runner = AsyncMock()
        with self.assertRaisesRegex(UpdateError, 'lacks capabilities'):
            await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        self.updater.install_runner.assert_not_awaited(); self.quiesce.assert_not_awaited()
        self.assertEqual(json.loads((self.root / 'service.json').read_text()), config)

    async def test_successful_selection_and_confirmation_after_boot(self):
        await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        self.quiesce.assert_awaited_once(); self.assertEqual(self.restarts, [True])
        selected = json.loads((self.root / 'service.json').read_text())
        self.assertEqual(selected['binary'], 'installed/lib/microblocks/pi417-test1/smallvm')
        self.assertEqual(selected['origin'], self.config['origin'])
        self.assertEqual(selected['additional_origins'], self.config['additional_origins'])
        self.assertEqual((self.root / 'updates/program-before-update.ucode').read_bytes(), b'original-program')
        begin_boot(self.root); confirm_boot(self.root)
        self.assertEqual(self.updater.status()['update']['state'], 'complete')
        self.assertFalse((self.root / 'updates/pending.json').exists())

    async def test_failed_candidate_boot_restores_previous_runtime_and_program(self):
        await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        begin_boot(self.root)
        (self.root / 'data/program.ucode').write_bytes(b'candidate-change')
        begin_boot(self.root)
        self.assertEqual(json.loads((self.root / 'service.json').read_text()), self.config)
        self.assertEqual((self.root / 'data/program.ucode').read_bytes(), b'original-program')
        self.assertEqual(self.updater.status()['update']['state'], 'rolled_back')

    async def test_rollback_restores_an_initially_empty_program_directory(self):
        (self.root / 'data/program.ucode').unlink()
        await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        begin_boot(self.root); (self.root / 'data/program.ucode').write_bytes(b'candidate-default')
        begin_boot(self.root)
        self.assertFalse((self.root / 'data/program.ucode').exists())

    async def test_busy_controller_failure_keeps_selection_and_unlocks_updates(self):
        self.updater.quiesce = AsyncMock(side_effect=UpdateError('Disconnect the editor'))
        with self.assertRaises(UpdateError): await self.updater.apply(self.digest, 'pi417-test1', True, self.send)
        self.assertFalse(self.updater.applying)
        self.assertEqual(json.loads((self.root / 'service.json').read_text()), self.config)

    async def test_complete_bounded_websocket_upload_without_native_execution(self):
        path = self.root / 'second.tar.gz'; digest, _ = bundle(path, version='pi417-test2'); raw = path.read_bytes()
        commands = iter([json.dumps({'action': 'upload', 'size': len(raw), 'sha256': digest}),
            *[raw[i:i+4096] for i in range(0, len(raw), 4096)], json.dumps({'action': 'finish'})])
        socket = type('Socket', (), {})(); socket.recv = AsyncMock(side_effect=lambda: next(commands)); socket.send = AsyncMock()
        await self.updater.handle(socket)
        messages = [json.loads(call.args[0]) for call in socket.send.call_args_list]
        self.assertEqual(messages[-1]['state'], 'prepared'); self.assertEqual(messages[-1]['version'], 'pi417-test2')
        self.quiesce.assert_not_awaited(); self.assertEqual(self.restarts, [])
        self.assertFalse(list((self.root / 'updates').glob('.incoming-*')))


class BrowserProtocolTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for browser protocol tests')
    def test_version_policy_and_browser_protocol(self):
        script = Path(__file__).with_name('pi-updates.test.cjs')
        subprocess.run(['node', '--test', str(script)], check=True, capture_output=True, text=True, timeout=30)


if __name__ == '__main__': unittest.main(verbosity=2)
