#!/usr/bin/env python3
"""Loopback-only packaged-editor HTTP server and verified SmallVM PTY bridge.

Requires Linux, Python 3.10+, and websockets==15.0.1. No serial-board access,
network discovery, remote listener, SSH, service installation or TLS bypass.
Use an explicitly authorized SSH local forward separately; its local and remote
ports must match because Host and Origin are checked against this listener port.
Only the supplied packaged-editor directory is served. URL queries/fragments,
traversal, symlinks and files outside that directory are refused.

Example: python bridge.py --editor /path/to/editor --pty-info /private/pty.json
         --vm-executable /path/to/smallvm --http-port 8876
The editor must already contain its normal /ws/vm adapter; this server never
rewrites or patches editor assets. It forwards the official binary VM stream.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import asyncio
import fcntl
from http import HTTPStatus
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import stat
import sys
import termios
import time
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

MAX_ASSET = 32 * 1024 * 1024
MAX_MESSAGE = 4096
IO_CHUNK = 2048
LOOPBACK = '127.0.0.1'


class BridgeError(RuntimeError):
    """A bounded diagnostic without VM program contents or credentials."""


def _private_regular(fd):
    meta = os.fstat(fd)
    if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077 or meta.st_nlink != 1:
        raise BridgeError('State file must be a private, current-user-owned regular file')
    return meta


def _process(pid):
    proc = Path('/proc') / str(pid)
    if proc.stat().st_uid != os.geteuid():
        raise BridgeError('VM process belongs to another user')
    status = (proc / 'status').read_text()
    uids = next(line.split()[1:] for line in status.splitlines() if line.startswith('Uid:'))
    if len(uids) != 4 or any(int(uid) != os.geteuid() for uid in uids):
        raise BridgeError('VM process UID credentials do not match the bridge owner')
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] in ('Z', 'X'):
        raise BridgeError('VM process has exited')
    return proc, int(fields[19])  # process start time: field 22, following comm.


class PtyEndpoint:
    """Verify the discovery record and bind it to a live process and PTY master."""
    def __init__(self, info, executable):
        self.directory_fd = self.lock_fd = None
        self.info = Path(info)
        self.executable = Path(executable).resolve(strict=True)
        if not self.info.is_absolute() or self.info.name in ('.', '..'):
            raise BridgeError('PTY discovery path must be absolute')
        try:
            self.directory_fd = os.open(self.info.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            directory = os.fstat(self.directory_fd)
            if directory.st_uid != os.geteuid() or directory.st_mode & 0o077:
                raise BridgeError('PTY discovery directory must be private and owned by the bridge user')
            fd = os.open(self.info.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.directory_fd)
            try:
                self.info_meta = _private_regular(fd)
                if not 1 <= self.info_meta.st_size <= 4096:
                    raise BridgeError('Invalid PTY discovery record size')
                raw = os.read(fd, 4097)
                if len(raw) != self.info_meta.st_size:
                    raise BridgeError('PTY discovery record changed while reading')
                record = json.loads(raw)
            finally:
                os.close(fd)
            if not isinstance(record, dict) or type(record.get('pid')) is not int or record['pid'] <= 0:
                raise BridgeError('Invalid VM process identity')
            self.pid = record['pid']
            self.pty = record.get('pty')
            if not isinstance(self.pty, str) or not re.fullmatch(r'/dev/pts/(0|[1-9][0-9]*)', self.pty):
                raise BridgeError('Discovery record must name a canonical /dev/pts device')
            if record.get('transport') != 'pty' or record.get('vm_version') != 417 or record.get('network_listener') is not False:
                raise BridgeError('Unsupported VM discovery contract')
            self.pts_index = int(self.pty.rsplit('/', 1)[1])
            self.exe_meta = self.executable.stat()
            proc, self.started = _process(self.pid)
            command = (proc / 'cmdline').read_bytes()
            if len(command) > 65536:
                raise BridgeError('VM command line exceeds identity bounds')
            argv = [os.fsdecode(value) for value in command.split(b'\0') if value]
            self._argument(argv, '--data-dir', str(self.info.parent.resolve(strict=True)))
            if '--pty-info' in argv:
                self._argument(argv, '--pty-info', str(self.info))
            elif self.info.name != f'pty-{self.pid}.json':
                raise BridgeError('Discovery filename is not the process default')
            self.check()
            name = f'.bridge-{self.pid}-{self.started}.lock'
            self.lock_fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.directory_fd)
            _private_regular(self.lock_fd)
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise BridgeError('Another bridge already owns this VM transport') from error
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _argument(argv, key, expected):
        if argv.count(key) != 1:
            raise BridgeError('VM command line does not match its discovery record')
        index = argv.index(key)
        if index + 1 >= len(argv) or argv[index + 1] != expected:
            raise BridgeError('VM runtime path does not match its discovery directory')

    def check(self):
        directory = os.fstat(self.directory_fd)
        if directory.st_uid != os.geteuid() or directory.st_mode & 0o077:
            raise BridgeError('PTY discovery directory is no longer private')
        meta = os.stat(self.info.name, dir_fd=self.directory_fd, follow_symlinks=False)
        if (meta.st_dev, meta.st_ino, meta.st_mtime_ns, meta.st_size) != (self.info_meta.st_dev, self.info_meta.st_ino, self.info_meta.st_mtime_ns, self.info_meta.st_size) or not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077 or meta.st_nlink != 1:
            raise BridgeError('PTY discovery record was replaced or changed')
        proc, started = _process(self.pid)
        if started != self.started:
            raise BridgeError('VM process identity was reused')
        executable = (proc / 'exe').stat()
        if (executable.st_dev, executable.st_ino) != (self.exe_meta.st_dev, self.exe_meta.st_ino):
            raise BridgeError('VM executable does not match the explicitly selected binary')
        # Linux exposes the slave index in the PTY master's fdinfo. The live
        # process must own that master, not merely have opened an unrelated tty.
        entries = list((proc / 'fdinfo').iterdir())
        if len(entries) > 1024:
            raise BridgeError('VM descriptor inventory exceeds identity bounds')
        owns_master = False
        for entry in entries:
            try:
                target = os.readlink(proc / 'fd' / entry.name)
                if target not in ('/dev/pts/ptmx', '/dev/ptmx'):
                    continue
                text = entry.read_text()
                if re.search(rf'^tty-index:\s*{self.pts_index}\s*$', text, re.MULTILINE):
                    owns_master = True
                    break
            except FileNotFoundError:
                continue
        if not owns_master:
            raise BridgeError('Selected VM does not own the advertised PTY master')

    def open(self):
        self.check()
        fd = os.open(self.pty, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISCHR(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077 or os.ttyname(fd) != self.pty:
                raise BridgeError('PTY slave identity or permissions do not match')
            settings = termios.tcgetattr(fd)
            if settings[3] & (termios.ICANON | termios.ECHO) or settings[1] & termios.OPOST or settings[0] & termios.ICRNL:
                raise BridgeError('VM PTY is not configured for its binary protocol')
            self.check()
            return fd
        except BaseException:
            os.close(fd)
            raise

    def close(self):
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None
        if self.directory_fd is not None:
            os.close(self.directory_fd)
            self.directory_fd = None


class SafeAssets:
    """Descriptor-relative walks prevent symlink traversal and path races."""
    def __init__(self, directory):
        self.fd = os.open(Path(directory).absolute(), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            self.read('/microblocks.html')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def path(target):
        if not isinstance(target, str) or len(target) > 2048 or not target.startswith('/') or target.startswith('//'):
            raise BridgeError('Invalid request path')
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or '?' in target or '#' in target:
            raise BridgeError('URL extras are not supported')
        path = unquote(parsed.path, errors='strict')
        if '%' in path or '\\' in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
            raise BridgeError('Invalid encoded path')
        parts = ['microblocks.html'] if path == '/' else path[1:].split('/')
        if len(parts) > 32 or any(not part or part in ('.', '..') or part.startswith('.') for part in parts):
            raise BridgeError('Traversal or hidden paths are not supported')
        return parts

    def read(self, target):
        parts = self.path(target)
        current = self.fd
        opened = []
        try:
            for index, part in enumerate(parts):
                # Nonblocking also makes a FIFO substituted during the walk
                # rejectable by fstat instead of blocking the event loop.
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                if index != len(parts) - 1:
                    flags |= os.O_DIRECTORY
                fd = os.open(part, flags, dir_fd=current)
                opened.append(fd)
                current = fd
            meta = os.fstat(current)
            if not stat.S_ISREG(meta.st_mode) or meta.st_size > MAX_ASSET:
                raise BridgeError('Requested file is not a bounded regular asset')
            remaining = meta.st_size
            chunks = []
            while remaining:
                chunk = os.read(current, min(remaining, 65536))
                if not chunk:
                    raise BridgeError('Asset changed while reading')
                chunks.append(chunk)
                remaining -= len(chunk)
            after = os.fstat(current)
            if (meta.st_size, meta.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise BridgeError('Asset changed while reading')
            mime = 'application/wasm' if parts[-1].endswith('.wasm') else mimetypes.guess_type(parts[-1])[0] or 'application/octet-stream'
            return b''.join(chunks), mime
        finally:
            for fd in reversed(opened):
                os.close(fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


async def _wait_fd(fd, writable=False, timeout=.25):
    loop = asyncio.get_running_loop()
    ready = loop.create_future()
    def wake():
        if not ready.done():
            ready.set_result(None)
    add, remove = (loop.add_writer, loop.remove_writer) if writable else (loop.add_reader, loop.remove_reader)
    add(fd, wake)
    try:
        await asyncio.wait_for(ready, timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        remove(fd)


class Bridge:
    def __init__(self, editor, pty_info, vm_executable, port=8876):
        if sys.platform != 'linux' or not 0 <= port <= 65535:
            raise BridgeError('Bridge requires Linux and a valid loopback port')
        self.assets = self.endpoint = None
        self.port = port
        self.owner = asyncio.Lock()
        self.server = None
        try:
            self.assets = SafeAssets(editor)
            self.endpoint = PtyEndpoint(pty_info, vm_executable)
        except BaseException:
            self.close()
            raise

    @staticmethod
    def response(status, body, mime='text/plain; charset=utf-8'):
        return Response(status.value, status.phrase, Headers([
            ('Content-Type', mime), ('Content-Length', str(len(body))),
            ('Cache-Control', 'no-store'), ('Connection', 'close'),
            ('X-Content-Type-Options', 'nosniff'), ('X-Frame-Options', 'DENY'),
            ('Referrer-Policy', 'no-referrer'),
            ('Cross-Origin-Resource-Policy', 'same-origin'),
        ]), body)

    def request(self, connection, request):
        hosts = request.headers.get_all('Host')
        if len(hosts) != 1 or hosts[0] not in (f'127.0.0.1:{self.port}', f'localhost:{self.port}'):
            return self.response(HTTPStatus.FORBIDDEN, b'Exact loopback Host required')
        origins = request.headers.get_all('Origin')
        if len(origins) > 1 or origins and origins[0] != 'http://' + hosts[0]:
            return self.response(HTTPStatus.FORBIDDEN, b'Same-origin loopback request required')
        try:
            parts = SafeAssets.path(request.path)
        except (BridgeError, ValueError, UnicodeError):
            return self.response(HTTPStatus.BAD_REQUEST, b'Invalid asset path')
        if parts == ['ws', 'vm']:
            upgrades = request.headers.get_all('Upgrade')
            if request.path != '/ws/vm' or len(origins) != 1:
                return self.response(HTTPStatus.FORBIDDEN, b'Exact WebSocket endpoint and Origin required')
            if len(upgrades) != 1 or upgrades[0].lower() != 'websocket':
                return self.response(HTTPStatus.UPGRADE_REQUIRED, b'WebSocket required')
            return None
        try:
            body, mime = self.assets.read(request.path)
            return self.response(HTTPStatus.OK, body, mime)
        except (OSError, BridgeError, UnicodeError, ValueError):
            return self.response(HTTPStatus.NOT_FOUND, b'Asset unavailable')

    async def handle(self, ws):
        if ws.request.path != '/ws/vm' or self.owner.locked():
            await ws.close(1013, 'VM already has a controller')
            return
        async with self.owner:
            fd = None
            tasks = []
            try:
                fd = self.endpoint.open()
                await ws.send('ready')
                async def from_pty():
                    checked = 0.
                    while True:
                        if time.monotonic() - checked >= .25:
                            self.endpoint.check()
                            checked = time.monotonic()
                        try:
                            data = os.read(fd, IO_CHUNK)
                        except BlockingIOError:
                            await _wait_fd(fd)
                            continue
                        if not data:
                            raise BridgeError('VM PTY closed')
                        await asyncio.wait_for(ws.send(data), timeout=5)
                async def to_pty():
                    async for data in ws:
                        if not isinstance(data, bytes) or len(data) > MAX_MESSAGE:
                            await ws.close(1003, 'Bounded binary VM messages required')
                            return
                        self.endpoint.check()
                        remaining = memoryview(data)
                        deadline = time.monotonic() + 5
                        while remaining:
                            if time.monotonic() >= deadline:
                                raise BridgeError('VM PTY write timed out')
                            try:
                                count = os.write(fd, remaining)
                            except BlockingIOError:
                                await _wait_fd(fd, writable=True)
                                continue
                            if count <= 0:
                                raise BridgeError('VM PTY write failed')
                            remaining = remaining[count:]
                tasks = [asyncio.create_task(from_pty()), asyncio.create_task(to_pty())]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                results = await asyncio.gather(*tasks, return_exceptions=True)
                if any(isinstance(result, Exception) and not isinstance(result, ConnectionClosed) for result in results):
                    await ws.close(1011, 'Verified VM transport unavailable')
            except (OSError, BridgeError, ValueError):
                await ws.close(1011, 'Verified VM transport unavailable')
            except ConnectionClosed:
                pass
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                if fd is not None:
                    os.close(fd)

    async def start(self):
        self.server = await serve(self.handle, LOOPBACK, self.port,
            process_request=self.request, compression=None,
            origins=[re.compile(r'^http://(?:127\.0\.0\.1|localhost):[1-9][0-9]{0,4}$')],
            open_timeout=5, close_timeout=2, max_size=MAX_MESSAGE, max_queue=8,
            write_limit=8192, server_header=None)
        self.port = self.server.sockets[0].getsockname()[1]
        if any(sock.getsockname()[0] != LOOPBACK for sock in self.server.sockets):
            self.server.close()
            await self.server.wait_closed()
            raise BridgeError('Refusing a non-loopback listener')
        return self

    async def stop(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        self.close()

    def close(self):
        if self.endpoint is not None:
            self.endpoint.close()
            self.endpoint = None
        if self.assets is not None:
            self.assets.close()
            self.assets = None


async def main(args):
    bridge = Bridge(args.editor, args.pty_info, args.vm_executable, args.http_port)
    try:
        await bridge.start()
        print(f'Local SmallVM editor: http://127.0.0.1:{bridge.port}/', flush=True)
        print('Scope: verified local PTY byte stream; no external peripherals or graphical acceptance implied.', flush=True)
        stopped = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, stopped.set)
        await stopped.wait()
    finally:
        await bridge.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--pty-info', type=Path, required=True)
    parser.add_argument('--vm-executable', type=Path, required=True)
    parser.add_argument('--http-port', type=int, default=8876)
    args = parser.parse_args()
    if not 1 <= args.http_port <= 65535:
        parser.error('--http-port must be 1..65535')
    try:
        asyncio.run(main(args))
    except (BridgeError, OSError, ValueError) as error:
        parser.exit(1, f'Local VM bridge refused: {error}\n')
