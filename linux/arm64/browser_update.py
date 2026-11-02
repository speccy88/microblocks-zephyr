"""Native v417 package review and guarded managed-runtime update transactions.

No firmware flashing, arbitrary URLs, shell fragments or system service changes.
Review does not execute the package. Apply stays disabled unless the managed
installation explicitly enables it, and always requires exact version/digest.
"""
# SPDX-License-Identifier: MPL-2.0
import asyncio
import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tarfile
import uuid
import zlib

MAX_UPLOAD = 64 * 1024 * 1024
SOURCE = '2071df569623ba9cdcd6f8106b61796e047df38b'
SHA = re.compile(r'[a-f0-9]{64}')
VERSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
REJECTED_NATIVE_SHA256 = frozenset({
    'feea4dc52f7a4e083c6144bfa569518bd801cc62341dca04500464b3c4ac7b21',
    'dd9411fa2555bd76ada18b9a5cde9e11676a46f654755ffa97806cf8fab4dd7b',
})


class UpdateError(RuntimeError):
    pass


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise UpdateError('Duplicate JSON field')
        result[key] = value
    return result


def message(raw):
    if not isinstance(raw, str) or len(raw) > 4096:
        raise UpdateError('Bounded update command required')
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise UpdateError('Update command object required')
    return value


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    try:
        with temporary.open('x', encoding='utf-8') as out:
            json.dump(value, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def review_archive(path, expected):
    path = Path(path)
    if not isinstance(expected, str) or not SHA.fullmatch(expected):
        raise UpdateError('Independent SHA-256 must contain 64 lowercase hexadecimal characters')
    meta = path.lstat()
    if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or not 64 <= meta.st_size <= MAX_UPLOAD:
        raise UpdateError('Release archive must be a bounded regular file')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise UpdateError('Archive SHA-256 mismatch; installed runtime is unchanged')
    try:
        expanded = 0
        with gzip.open(path, 'rb') as compressed:
            for chunk in iter(lambda: compressed.read(65536), b''):
                expanded += len(chunk)
                if expanded > MAX_UPLOAD + 65536:
                    raise UpdateError('Expanded archive size exceeded')
        with tarfile.open(path, 'r:gz') as archive:
            members = []
            for member in archive:
                if member.name not in {'smallvm', 'manifest.json', 'LICENSE', 'NOTICE'} or not member.isfile() or member.size > 32 * 1024 * 1024:
                    raise UpdateError('Unexpected archive contents, links or sizes')
                members.append(member)
                if len(members) > 4:
                    raise UpdateError('Unexpected archive member count')
            names = [member.name for member in members]
            if (len(names) != len(set(names)) or not {'smallvm', 'manifest.json', 'LICENSE'} <= set(names)
                    or not set(names) <= {'smallvm', 'manifest.json', 'LICENSE', 'NOTICE'}
                    or len(members) > 4 or any(not m.isfile() or m.size > 32 * 1024 * 1024 for m in members)
                    or sum(m.size for m in members) > MAX_UPLOAD):
                raise UpdateError('Unexpected archive contents, links or sizes')
            info = archive.getmember('manifest.json')
            if not 1 <= info.size <= 16384:
                raise UpdateError('Manifest size exceeded')
            metadata = json.loads(archive.extractfile(info).read(), object_pairs_hook=unique)
            version = metadata.get('version')
            if not isinstance(version, str) or not VERSION.fullmatch(version) or version == 'latest':
                raise UpdateError('A fixed native release version is required')
            capabilities = metadata.get('capabilities', [])
            if (not isinstance(capabilities, list) or len(capabilities) > 32
                    or any(not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9._-]{0,63}', value) for value in capabilities)
                    or len(capabilities) != len(set(capabilities))):
                raise UpdateError('Invalid native capability manifest')
            if (metadata.get('architecture') != 'linux-aarch64' or metadata.get('vm_version') != 417
                    or metadata.get('source_commit') != SOURCE):
                raise UpdateError('This Pi port accepts tested native ARM64 v417 packages; upstream v421 is not validated here')
            stream = archive.extractfile('smallvm')
            header = stream.read(64)
            if len(header) < 64 or header[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', header, 18)[0] != 183:
                raise UpdateError('Native little-endian ARM64 ELF required; board flash images are not supported')
            binary_hash = hashlib.sha256(header)
            for chunk in iter(lambda: stream.read(65536), b''):
                binary_hash.update(chunk)
            if metadata.get('binary_sha256') != binary_hash.hexdigest():
                raise UpdateError('Native executable checksum mismatch')
            if binary_hash.hexdigest() in REJECTED_NATIVE_SHA256:
                raise UpdateError('This older native build predates required headless cleanup; keep the corrected Pi runtime')
    except (tarfile.TarError, OSError, ValueError, TypeError, AttributeError, EOFError, zlib.error) as error:
        if isinstance(error, UpdateError):
            raise
        raise UpdateError('Cannot read a valid native release archive') from error
    provenance = metadata.get('provenance', {})
    port_commit = provenance.get('port_commit') if isinstance(provenance, dict) else None
    if port_commit is not None and (not isinstance(port_commit, str) or not re.fullmatch(r'[a-f0-9]{40}', port_commit)):
        raise UpdateError('Invalid port commit provenance')
    return {'port_commit': port_commit, 'version': version, 'sha256': expected, 'binary_sha256': binary_hash.hexdigest(),
        'vm_version': 417, 'architecture': 'linux-aarch64', 'bytes': meta.st_size, 'capabilities': capabilities}


def begin_boot(root):
    """Rollback once if a newly selected binary never reached service readiness."""
    root = Path(root)
    pending = root / 'updates/pending.json'
    if not pending.exists():
        return
    journal = json.loads(pending.read_text())
    if journal.get('boot_attempted'):
        atomic_json(root / 'service.json', journal['previous_config'])
        backup = root / 'updates/program-before-update.ucode'
        if journal.get('program_existed'):
            if hashlib.sha256(backup.read_bytes()).hexdigest() != journal['program_sha256']:
                raise UpdateError('Recovery program backup checksum mismatch')
            target = root / 'data/program.ucode'
            temporary = target.with_name('.program-rollback.ucode')
            shutil.copyfile(backup, temporary); os.replace(temporary, target)
        else:
            (root / 'data/program.ucode').unlink(missing_ok=True)
        atomic_json(root / 'updates/state.json', {'state': 'rolled_back',
            'error': 'Candidate failed to become ready; previous runtime and program restored',
            'version': journal['version'], 'sha256': journal['sha256']})
        pending.unlink()
    else:
        journal['boot_attempted'] = True
        atomic_json(pending, journal)


def confirm_boot(root):
    root = Path(root)
    pending = root / 'updates/pending.json'
    if pending.exists():
        journal = json.loads(pending.read_text())
        atomic_json(root / 'updates/state.json', {'state': 'complete', 'version': journal['version'],
            'sha256': journal['sha256'], 'vm_version': 417})
        pending.unlink()


class BrowserUpdater:
    def __init__(self, root, installer, quiesce, restart, *, allow_apply=False, install_runner=None):
        self.root = Path(root)
        self.directory = self.root / 'updates'
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.installer, self.quiesce, self.restart = Path(installer), quiesce, restart
        self.allow_apply = allow_apply
        self.install_runner = install_runner or self.install
        self.lock = asyncio.Lock()
        self.applying = False
        from github_release import GitHubReleases
        self.github = GitHubReleases(self)

    def status(self):
        config = json.loads((self.root / 'service.json').read_text())
        state = {'state': 'idle'}
        if (self.directory / 'state.json').exists():
            state = json.loads((self.directory / 'state.json').read_text())
        return {'target': 'raspberry-pi5', 'current_vm_version': config['vm_version'],
            'current_release': config.get('release_version', 'Pi v417'),
            'supported_vm_versions': [417], 'native_install_enabled': self.allow_apply,
            'upload_enabled': True, 'update': state}

    async def install(self, archive, metadata):
        args = ['bash', str(self.installer), '--version', metadata['version'], '--sha256', metadata['sha256'],
            '--archive', str(archive), '--prefix', str(self.root / 'installed'), '--data-dir', str(self.root / 'data')]
        log = self.directory / 'install.log'
        with log.open('wb') as output:
            child = await asyncio.create_subprocess_exec(*args, stdout=output, stderr=asyncio.subprocess.STDOUT)
            try:
                await asyncio.wait_for(child.wait(), 30)
            except TimeoutError:
                child.kill(); await child.wait()
                raise UpdateError('Native validation timed out; previous runtime remains selected')
        if child.returncode:
            raise UpdateError('Native validation/install failed; previous runtime remains selected')

    def prepare(self, path, digest, *, github=None):
        metadata = review_archive(path, digest)
        destination = self.directory / (digest + '.tar.gz')
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise UpdateError('Existing staged archive changed')
            if Path(path).resolve() != destination.resolve():
                Path(path).unlink()
        else:
            os.replace(path, destination)
        atomic_json(self.directory / 'state.json', {'state': 'prepared', **metadata, **({'github': github} if github else {})})
        return metadata

    async def apply(self, digest, version, confirmed, send):
        if not self.allow_apply:
            raise UpdateError('Native installation is not authorized for this managed runtime; package review is available')
        state = self.status()['update']
        if (confirmed is not True or state.get('state') != 'prepared' or digest != state.get('sha256')
                or version != state.get('version')):
            raise UpdateError('Confirm the exact reviewed version and SHA-256 before installation')
        archive = self.directory / (digest + '.tar.gz')
        metadata = review_archive(archive, digest)
        previous = json.loads((self.root / 'service.json').read_text())
        required = previous.get('required_runtime_capabilities', [])
        if not isinstance(required, list) or not set(required) <= set(metadata['capabilities']):
            raise UpdateError('Candidate lacks capabilities required by the installed host integration')
        if state.get('github', {}).get('baseline_binary_sha256', previous['binary_sha256']) != previous['binary_sha256']:
            raise UpdateError('Le SmallVM a changé; relancez la recherche GitHub avant installation')
        stopped = False
        try:
            await send({'state': 'validating_native'})
            await self.install_runner(archive, metadata)
            candidate = self.root / 'installed/lib/microblocks' / version / 'smallvm'
            if candidate.is_symlink() or hashlib.sha256(candidate.read_bytes()).hexdigest() != metadata['binary_sha256']:
                raise UpdateError('Installed candidate identity changed')
            await send({'state': 'preserving_program'})
            self.applying = True
            await self.quiesce(); stopped = True
            program = self.root / 'data/program.ucode'
            exists = program.exists()
            program_sha = None
            if exists:
                meta = program.lstat()
                if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
                    raise UpdateError('Unexpected managed program data')
                backup = self.directory / 'program-before-update.ucode'
                shutil.copyfile(program, backup)
                program_sha = hashlib.sha256(backup.read_bytes()).hexdigest()
            journal = {'version': version, 'sha256': digest, 'previous_config': previous,
                'program_existed': exists, 'program_sha256': program_sha, 'boot_attempted': False}
            atomic_json(self.directory / 'pending.json', journal)
            replacement = dict(previous, binary=candidate.relative_to(self.root).as_posix(),
                binary_sha256=metadata['binary_sha256'], release_version=version)
            if metadata.get('port_commit'):
                replacement['native_port_commit'] = metadata['port_commit']
            elif metadata['binary_sha256'] != previous['binary_sha256']:
                replacement.pop('native_port_commit', None)
            atomic_json(self.root / 'service.json', replacement)
            atomic_json(self.directory / 'state.json', {'state': 'restarting', **metadata})
            await send({'state': 'restarting', **metadata})
            self.restart()
        except BaseException as error:
            if not stopped:
                self.applying = False
            if stopped:
                atomic_json(self.root / 'service.json', previous)
                (self.directory / 'pending.json').unlink(missing_ok=True)
                self.restart()
            atomic_json(self.directory / 'state.json', {'state': 'failed', 'error': str(error)[:240],
                'version': version, 'sha256': digest})
            raise

    async def handle(self, socket):
        if self.lock.locked():
            await socket.close(1013, 'Another native package operation is in progress'); return
        async with self.lock:
            incoming = None
            async def send(value):
                await socket.send(json.dumps(value, separators=(',', ':')))
            try:
                command = message(await asyncio.wait_for(socket.recv(), 10))
                if command.get('action') == 'github_check':
                    if set(command) != {'action', 'include_prereleases'} or type(command['include_prereleases']) is not bool:
                        raise UpdateError('Choisissez explicitement le canal GitHub')
                    loop = asyncio.get_running_loop()
                    def progress(value):
                        asyncio.run_coroutine_threadsafe(send(value), loop).result(timeout=10)
                    result = await asyncio.to_thread(self.github.check, command['include_prereleases'], progress)
                    await send(result)
                    return
                if command.get('action') == 'github_choose':
                    if set(command) != {'action', 'choice'} or not isinstance(command['choice'], str) or not re.fullmatch(r'[0-9]{1,20}:[0-9]{1,20}', command['choice']):
                        raise UpdateError('Sélection GitHub vérifiée requise')
                    await send(self.github.choose(command['choice']))
                    return
                if command.get('action') == 'apply':
                    if set(command) != {'action', 'sha256', 'version', 'confirmed'}:
                        raise UpdateError('Exact native installation confirmation required')
                    await self.apply(command['sha256'], command['version'], command['confirmed'], send)
                    return
                if (set(command) != {'action', 'size', 'sha256'} or command['action'] != 'upload'
                        or type(command['size']) is not int or not 64 <= command['size'] <= MAX_UPLOAD
                        or not isinstance(command['sha256'], str) or not SHA.fullmatch(command['sha256'])):
                    raise UpdateError('Bounded native release upload and independent SHA-256 required')
                incoming = self.directory / ('.incoming-' + uuid.uuid4().hex)
                received = 0
                await send({'state': 'uploading', 'received': 0, 'total': command['size']})
                with incoming.open('xb') as output:
                    while received < command['size']:
                        chunk = await asyncio.wait_for(socket.recv(), 15)
                        if not isinstance(chunk, bytes) or not 1 <= len(chunk) <= 4096 or received + len(chunk) > command['size']:
                            raise UpdateError('Native upload requires bounded binary chunks')
                        output.write(chunk); received += len(chunk)
                        if received % 65536 == 0 or received == command['size']:
                            await send({'state': 'uploading', 'received': received, 'total': command['size']})
                if message(await asyncio.wait_for(socket.recv(), 10)) != {'action': 'finish'}:
                    raise UpdateError('Native upload finish marker required')
                await send({'state': 'checking_archive'})
                metadata = self.prepare(incoming, command['sha256']); incoming = None
                await send({'state': 'prepared', 'native_install_enabled': self.allow_apply, **metadata})
            except (OSError, RuntimeError, ValueError, TypeError, TimeoutError) as error:
                await send({'state': 'error', 'error': str(error)[:240]})
            finally:
                if incoming is not None:
                    incoming.unlink(missing_ok=True)
