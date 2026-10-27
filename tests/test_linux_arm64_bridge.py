#!/usr/bin/env python3
"""Localhost HTTP/WebSocket + real Linux PTY tests with an explicit echo fixture.

These tests simulate the VM byte stream. They do not execute SmallVM bytecode,
access a physical board, use SSH or connect outside loopback. Use the separate
linux_arm64_protocol.py runner for real-interpreter acceptance.
"""
# SPDX-License-Identifier: MPL-2.0
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import unittest

bridge = None
IMPORT_ERROR = 'Linux PTY support required'
if sys.platform == 'linux':
    try:
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed, InvalidStatus
        spec = importlib.util.spec_from_file_location('linux_arm64_bridge', Path(__file__).resolve().parents[1] / 'linux/arm64/bridge.py')
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
    except ImportError as error:
        bridge = None
        IMPORT_ERROR = str(error)


FAKE_VM = r'''
import argparse,json,os,pty,select,sys,tty
p=argparse.ArgumentParser();p.add_argument('--data-dir',required=True);p.add_argument('--pty-info',required=True);a=p.parse_args()
master,slave=pty.openpty();tty.setraw(slave);os.fchmod(slave,0o600)
record={'pty':os.ttyname(slave),'pid':os.getpid(),'transport':'pty','vm_version':417,'network_listener':False}
fd=os.open(a.pty_info,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.write(fd,(json.dumps(record)+'\n').encode());os.fsync(fd);os.close(fd)
print('echo-fixture-ready',flush=True)
while True:
    select.select([master],[],[])
    data=os.read(master,2048)
    if not data:break
    while data:
        count=os.write(master,data);data=data[count:]
'''


class FakeVM:
    def __init__(self, data):
        self.data = data
        self.info = data / 'fixture-pty.json'
        self.process = subprocess.Popen([sys.executable, '-u', '-c', FAKE_VM, '--data-dir', str(data), '--pty-info', str(self.info)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            if not select.select([self.process.stdout], [], [], 5)[0] or self.process.stdout.readline().strip() != 'echo-fixture-ready':
                raise RuntimeError('Explicit PTY echo fixture did not start')
            self.record = json.loads(self.info.read_text())
        except BaseException:
            self.stop()
            raise

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()


@unittest.skipUnless(bridge is not None, IMPORT_ERROR)
class Assets(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smallvm-assets-fixture-')
        self.base = Path(self.temporary.name)
        self.editor = self.base / 'editor'
        self.editor.mkdir()
        (self.editor / 'microblocks.html').write_text('<!doctype html><title>Fixture editor</title>')
        (self.editor / 'sub').mkdir()
        (self.editor / 'sub/data.bin').write_bytes(bytes(range(256)))
        (self.base / 'outside.txt').write_text('outside fixture sentinel')
        (self.editor / 'link.txt').symlink_to(self.base / 'outside.txt')
        (self.editor / 'linked-dir').symlink_to(self.base, target_is_directory=True)
        self.assets = bridge.SafeAssets(self.editor)

    def tearDown(self):
        self.assets.close()
        self.temporary.cleanup()

    def test_exact_assets_and_wasm_type(self):
        body, mime = self.assets.read('/')
        self.assertIn(b'Fixture editor', body)
        self.assertEqual(mime, 'text/html')
        self.assertEqual(self.assets.read('/sub/data.bin')[0], bytes(range(256)))
        (self.editor / 'engine.wasm').write_bytes(b'\0asm')
        self.assertEqual(self.assets.read('/engine.wasm')[1], 'application/wasm')

    def test_traversal_url_extras_encoded_separators_and_hidden_paths_are_refused(self):
        for target in ['/../outside.txt', '/%2e%2e/outside.txt', '/%252e%252e/outside.txt', '/sub/../../outside.txt', '/sub\\data.bin', '/%5coutside', '/%00bad', '/a//b', '/a/./b', '/.git/config', '/?bridge=1', '/engine.wasm?v=1', '/#fragment', '//other.invalid/file', 'http://other.invalid/file', '/%ZZ']:
            with self.subTest(target=target), self.assertRaises((bridge.BridgeError, ValueError, UnicodeError)):
                self.assets.read(target)

    def test_symlink_files_directories_and_editor_root_are_refused(self):
        for target in ['/link.txt', '/linked-dir/outside.txt']:
            with self.subTest(target=target), self.assertRaises(OSError):
                self.assets.read(target)
        link = self.base / 'root-link'
        link.symlink_to(self.editor, target_is_directory=True)
        with self.assertRaises(OSError):
            bridge.SafeAssets(link)

    def test_sparse_oversized_asset_is_refused_without_reading_it(self):
        with open(self.editor / 'too-large.data', 'wb') as stream:
            stream.truncate(bridge.MAX_ASSET + 1)
        with self.assertRaises(bridge.BridgeError):
            self.assets.read('/too-large.data')
        os.mkfifo(self.editor / 'pipe')
        with self.assertRaises(bridge.BridgeError):
            self.assets.read('/pipe')

    def test_refused_descriptor_walks_do_not_leak_descriptors(self):
        before = len(list(Path('/proc/self/fd').iterdir()))
        for _ in range(100):
            with self.assertRaises(OSError):
                self.assets.read('/linked-dir/outside.txt')
            with self.assertRaises(OSError):
                self.assets.read('/sub/absent.txt')
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), before)


@unittest.skipUnless(bridge is not None, IMPORT_ERROR)
class LocalBridge(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smallvm-bridge-fixture-')
        self.base = Path(self.temporary.name)
        self.editor = self.base / 'editor'
        self.editor.mkdir()
        (self.editor / 'microblocks.html').write_text('<!doctype html><title>Explicit mock editor</title>')
        (self.editor / 'engine.wasm').write_bytes(b'\0asm')
        (self.base / 'outside.txt').write_text('outside fixture sentinel')
        (self.editor / 'link.txt').symlink_to(self.base / 'outside.txt')
        self.data = self.base / 'private-data'
        self.data.mkdir(mode=0o700)
        self.vm = FakeVM(self.data)
        self.bridge = await bridge.Bridge(self.editor, self.vm.info, sys.executable, port=0).start()
        self.port = self.bridge.port
        self.origin = f'http://127.0.0.1:{self.port}'
        self.uri = f'ws://127.0.0.1:{self.port}/ws/vm'

    async def asyncTearDown(self):
        await self.bridge.stop()
        self.vm.stop()
        self.temporary.cleanup()

    async def client(self, **kwargs):
        return await connect(self.uri, origin=self.origin, proxy=None, compression=None, close_timeout=1, **kwargs)

    async def receive_exact(self, ws, count):
        result = b''
        while len(result) < count:
            data = await asyncio.wait_for(ws.recv(), 2)
            self.assertIsInstance(data, bytes)
            self.assertLessEqual(len(data), bridge.IO_CHUNK)
            result += data
        self.assertEqual(len(result), count)
        return result

    async def http(self, target='/', host=None, extra=()):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        headers = [('Host', host or f'127.0.0.1:{self.port}'), *extra]
        request = f'GET {target} HTTP/1.1\r\n' + ''.join(f'{key}: {value}\r\n' for key, value in headers) + '\r\n'
        writer.write(request.encode('ascii'))
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), 2)
        writer.close()
        await writer.wait_closed()
        header, body = response.split(b'\r\n\r\n', 1)
        return int(header.split()[1]), header, body

    async def test_actual_loopback_http_and_binary_pty_roundtrip(self):
        self.assertTrue(all(sock.getsockname()[0] == '127.0.0.1' for sock in self.bridge.server.sockets))
        status, headers, body = await self.http()
        self.assertEqual(status, 200)
        self.assertIn(b'Explicit mock editor', body)
        self.assertIn(b'X-Content-Type-Options: nosniff', headers)
        self.assertNotIn(b'Access-Control-Allow-Origin', headers)
        ws = await self.client()
        try:
            self.assertEqual(await ws.recv(), 'ready')
            payload = bytes(range(256)) * 16
            await ws.send(payload)
            self.assertEqual(await self.receive_exact(ws, len(payload)), payload)
            await ws.send([b'\xfa\x1a', b'\x49'])
            self.assertEqual(await self.receive_exact(ws, 3), b'\xfa\x1a\x49')
        finally:
            await ws.close()

    async def test_only_one_controller_and_reconnect_after_release(self):
        first = await self.client()
        self.assertEqual(await first.recv(), 'ready')
        second = await self.client()
        with self.assertRaises(ConnectionClosed) as closed:
            await second.recv()
        self.assertEqual(closed.exception.rcvd.code, 1013)
        await first.send(b'first controller retained')
        self.assertEqual(await self.receive_exact(first, 25), b'first controller retained')
        await first.close()
        until = time.monotonic() + 2
        while self.bridge.owner.locked() and time.monotonic() < until:
            await asyncio.sleep(.01)
        third = await self.client()
        self.assertEqual(await third.recv(), 'ready')
        await third.send(b'reconnected')
        self.assertEqual(await self.receive_exact(third, 11), b'reconnected')
        await third.close()

    async def test_text_and_oversized_messages_are_closed(self):
        for payload, expected in [('text is forbidden', 1003), (b'x' * (bridge.MAX_MESSAGE + 1), 1009)]:
            with self.subTest(expected=expected):
                ws = await self.client()
                self.assertEqual(await ws.recv(), 'ready')
                await ws.send(payload)
                with self.assertRaises(ConnectionClosed) as closed:
                    await ws.recv()
                self.assertEqual(closed.exception.rcvd.code, expected)
                await ws.close()
                until = time.monotonic() + 2
                while self.bridge.owner.locked() and time.monotonic() < until:
                    await asyncio.sleep(.01)

    async def test_missing_wrong_or_mismatched_origin_cannot_open_vm(self):
        for origin in [None, 'null', 'https://example.invalid', f'http://127.0.0.1:{self.port + 1}', f'http://localhost:{self.port}']:
            with self.subTest(origin=origin), self.assertRaises(InvalidStatus) as refused:
                await connect(self.uri, origin=origin, proxy=None)
            self.assertEqual(refused.exception.response.status_code, 403)
        local = await connect(f'ws://localhost:{self.port}/ws/vm', host='127.0.0.1', origin=f'http://localhost:{self.port}', proxy=None)
        self.assertEqual(await local.recv(), 'ready')
        await local.close()

    async def test_http_host_is_exact_single_and_same_port(self):
        for host in ['other.invalid:' + str(self.port), '127.0.0.1', '127.0.0.1:' + str(self.port + 1), 'localhost.:' + str(self.port), '127.0.0.1:0' + str(self.port)]:
            with self.subTest(host=host):
                self.assertEqual((await self.http(host=host))[0], 403)
        self.assertEqual((await self.http(extra=[('Host', f'127.0.0.1:{self.port}')]))[0], 403)
        self.assertEqual((await self.http(extra=[('Origin', 'https://other.invalid')]))[0], 403)
        self.assertEqual((await self.http(host=f'localhost:{self.port}'))[0], 200)

    async def test_http_traversal_queries_fragments_and_symlinks_are_not_served(self):
        for target in ['/../outside.txt', '/%2e%2e/outside.txt', '/%252e%252e/outside.txt', '/?bridge=1', '/engine.wasm?v=1', '/#fragment', '//other.invalid/x', '/%5cbad', '/ws/vm?extra=1']:
            with self.subTest(target=target):
                self.assertEqual((await self.http(target))[0], 400)
        self.assertEqual((await self.http('/link.txt'))[0], 404)
        self.assertEqual((await self.http('/absent'))[0], 404)
        status, headers, body = await self.http('/engine.wasm')
        self.assertEqual(status, 200)
        self.assertIn(b'Content-Type: application/wasm', headers)
        self.assertEqual(body, b'\0asm')

    async def test_second_bridge_process_owner_is_refused_without_harming_first(self):
        with self.assertRaisesRegex(bridge.BridgeError, 'Another bridge'):
            bridge.PtyEndpoint(self.vm.info, sys.executable)
        ws = await self.client()
        self.assertEqual(await ws.recv(), 'ready')
        await ws.send(b'still owned')
        self.assertEqual(await self.receive_exact(ws, 11), b'still owned')
        await ws.close()

    async def test_vm_exit_closes_socket_without_following_stale_identity(self):
        ws = await self.client()
        self.assertEqual(await ws.recv(), 'ready')
        self.vm.stop()
        with self.assertRaises(ConnectionClosed) as closed:
            await asyncio.wait_for(ws.recv(), 2)
        self.assertEqual(closed.exception.rcvd.code, 1011)
        await ws.close()

    async def test_discovery_permissions_executable_and_pty_owner_are_verified(self):
        self.vm.info.chmod(0o644)
        with self.assertRaises(bridge.BridgeError):
            bridge.PtyEndpoint(self.vm.info, sys.executable)
        self.vm.info.chmod(0o600)
        with self.assertRaises(bridge.BridgeError):
            bridge.PtyEndpoint(self.vm.info, '/bin/sh')
        link = self.data / 'symlink.json'
        link.symlink_to(self.vm.info)
        with self.assertRaises(OSError):
            bridge.PtyEndpoint(link, sys.executable)
        original = self.vm.info.read_bytes()
        for replacement in [{'pid': True}, {'pty': '/dev/pts/999999'}, {'pty': '/dev/null'}, {'network_listener': True}]:
            self.vm.info.write_text(json.dumps({**self.vm.record, **replacement}))
            with self.subTest(replacement=replacement), self.assertRaises(bridge.BridgeError):
                bridge.PtyEndpoint(self.vm.info, sys.executable)
        self.vm.info.write_bytes(original)


if __name__ == '__main__':
    if bridge is None:
        raise SystemExit('Cannot run Linux bridge tests: ' + IMPORT_ERROR)
    unittest.main(verbosity=2)
