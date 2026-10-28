"""Foreground lifecycle tests: native VM with loopback fixture assets, no board."""
# SPDX-License-Identifier: MIT
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / 'linux/arm64/session.py'
BINARY = Path(os.environ.get('SMALLVM_MICRODUCK_BINARY', ROOT / 'build-artifacts/linux-ci-native/smallvm'))
session = None
if sys.platform == 'linux':
    spec = importlib.util.spec_from_file_location('foreground_session', SESSION)
    session = importlib.util.module_from_spec(spec); spec.loader.exec_module(session)


@unittest.skipUnless(session is not None, 'Linux directory/lock semantics required')
class SessionPolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='smallvm-session-policy-')
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def release(self, handles):
        os.close(handles[2]); os.close(handles[1])
    def test_explicit_resume_private_directory_and_missing_data(self):
        data = self.root / 'data'
        self.release(session.acquire_directory(data, False))
        with self.assertRaisesRegex(RuntimeError, '--resume'):
            session.acquire_directory(data, False)
        self.release(session.acquire_directory(data, True))
        with self.assertRaises(FileNotFoundError):
            session.acquire_directory(self.root / 'missing', True)
        data.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, 'private'):
            session.acquire_directory(data, True)
        self.assertEqual(data.stat().st_mode & 0o777, 0o755)
    def test_symlink_directory_lock_and_status_are_refused(self):
        target = self.root / 'target'; target.mkdir(mode=0o700)
        link = self.root / 'alias'; link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(OSError):session.acquire_directory(link, True)
        outside = self.root / 'outside'; outside.write_bytes(b'keep'); outside.chmod(0o600)
        for name in ('.session.lock', 'session.json'):
            data = self.root / name.replace('.', '_'); data.mkdir(mode=0o700)
            (data / name).symlink_to(outside)
            with self.assertRaises((OSError, RuntimeError)):session.acquire_directory(data, True)
            self.assertEqual(outside.read_bytes(), b'keep')
    def test_supervisor_ownership_is_exclusive_and_released(self):
        data = self.root / 'data'; first = session.acquire_directory(data, False)
        try:
            with self.assertRaisesRegex(RuntimeError, 'Another supervisor'):
                session.acquire_directory(data, True)
        finally:self.release(first)
        self.release(session.acquire_directory(data, True))
    def test_discovery_cannot_select_a_different_pid_or_unsafe_file(self):
        data, fd, lock = session.acquire_directory(self.root / 'data', False)
        try:
            path = data / 'fresh.json'
            value = {'pid':42,'transport':'pty','vm_version':417,'network_listener':False}
            path.write_text(json.dumps(value)); path.chmod(0o600)
            with self.assertRaisesRegex(RuntimeError, 'newly spawned'):
                session.child_discovery(fd, path.name, 43)
            self.assertEqual(session.child_discovery(fd, path.name, 42), value)
            path.unlink(); os.mkfifo(path)
            with self.assertRaisesRegex(RuntimeError, 'regular'):
                session.child_discovery(fd, path.name, 42)
        finally:os.close(lock); os.close(fd)


class WebWire:
    """Official framed protocol through the real bridge, not a VM simulation."""
    def __init__(self, port):
        from websockets.sync.client import connect
        origin = f'http://127.0.0.1:{port}'
        self.ws = connect(origin.replace('http:', 'ws:') + '/ws/vm', origin=origin, proxy=None, compression=None, close_timeout=1)
        if self.ws.recv(timeout=3) != 'ready':raise AssertionError('Missing verified PTY readiness')
        self.buffer = bytearray()
    def close(self):self.ws.close()
    def short(self, kind, index=0):self.ws.send(bytes([250,kind,index]))
    def wait(self, kind, index=0):
        until = time.monotonic() + 4
        while time.monotonic() < until:
            while len(self.buffer) >= 3:
                if self.buffer[0] == 250:size,offset=3,3
                elif self.buffer[0] == 251:
                    if len(self.buffer)<5:break
                    size,offset=5+int.from_bytes(self.buffer[3:5],'little'),5
                else:raise AssertionError('Unframed VM output')
                if len(self.buffer)<size:break
                event=(self.buffer[1],self.buffer[2],bytes(self.buffer[offset:size]));del self.buffer[:size]
                if event[:2]==(kind,index):return event[2]
                if event[0]==19:raise AssertionError('Actual VM task error')
            frame=self.ws.recv(timeout=max(.01,until-time.monotonic()))
            if not isinstance(frame,bytes) or len(self.buffer)+len(frame)>65536:raise AssertionError('Unexpected bridge frame')
            self.buffer.extend(frame)
        raise AssertionError('VM response timeout')
    def ping(self):self.short(26,73);self.wait(26,73)
    def crc(self):self.short(11);return int.from_bytes(self.wait(23),'little')
    def upload(self):
        self.code=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        body=bytes([2])+self.code+b'\xfe'
        self.ws.send(bytes([251,32,0])+struct.pack('<H',len(body))+body)
        crc=int.from_bytes(self.wait(23),'little')
        if crc!=zlib.crc32(self.code):raise AssertionError('Upload CRC mismatch')
        return crc
    def reporter(self):
        self.short(3);body=self.wait(18)
        if body[0]!=1:raise AssertionError('Expected actual integer result')
        return int.from_bytes(body[1:5],'little',signed=True)


@unittest.skipUnless(session is not None and BINARY.is_file(), 'Requires Linux and the selected real native VM binary')
class SessionNativeLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='smallvm-session-native-');self.root=Path(self.temp.name)
        self.editor=self.root/'editor';self.editor.mkdir();(self.editor/'microblocks.html').write_text('<title>Lifecycle fixture assets</title>')
        self.children=[]
    def tearDown(self):
        for child in reversed(self.children):
            if child.poll() is None:child.terminate();child.wait(timeout=15)
            if child.stdout:child.stdout.close()
            if child.stderr:child.stderr.close()
        self.temp.cleanup()
    def port(self):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
    def command(self,data,port,resume=False):
        return [sys.executable,str(SESSION),'--binary',str(BINARY),'--editor',str(self.editor),'--data',str(data),'--port',str(port),*(['--resume'] if resume else [])]
    def start(self,data,port,resume=False):
        child=subprocess.Popen(self.command(data,port,resume),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);self.children.append(child)
        if not select.select([child.stdout],[],[],15)[0]:raise AssertionError('Supervisor readiness timeout')
        line=child.stdout.readline()
        if not line:raise AssertionError(child.stderr.read())
        report=json.loads(line);self.assertEqual(report['state'],'ready');return child,report
    def stop(self,child):
        child.send_signal(signal.SIGTERM);child.communicate(timeout=15);self.assertEqual(child.returncode,0)
    def test_socket_reconnect_and_resume_preserve_program_and_prior_logs(self):
        data=self.root/'data';port=self.port();first,report=self.start(data,port)
        wire=WebWire(port)
        try:wire.ping();crc=wire.upload();self.assertEqual(wire.reporter(),12)
        finally:wire.close()
        wire=WebWire(port)
        try:self.assertEqual(wire.crc(),crc);self.assertEqual(wire.reporter(),12)
        finally:wire.close()
        self.stop(first);saved=(data/'program.ucode').read_bytes()
        logs={path:path.read_bytes() for path in data.glob('*.log')}
        self.assertEqual(json.loads((data/'session.json').read_text())['state'],'stopped')
        second,resumed=self.start(data,port,True)
        self.assertNotEqual(report['pty_info'],resumed['pty_info'])
        self.assertEqual((data/'program.ucode').read_bytes(),saved)
        wire=WebWire(port)
        try:self.assertEqual(wire.crc(),crc);self.assertEqual(wire.reporter(),12)
        finally:wire.close()
        for path,raw in logs.items():self.assertEqual(path.read_bytes(),raw)
        self.assertNotIn(b'--microduck-socket',Path(f'/proc/{resumed["vm_pid"]}/cmdline').read_bytes())
        self.stop(second)
    def test_competing_supervisor_leaves_owner_and_status_untouched(self):
        data=self.root/'data';port=self.port();owner,report=self.start(data,port)
        before=(data/'session.json').read_bytes()
        result=subprocess.run(self.command(data,port,True),capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0);self.assertIn('Another supervisor',result.stderr)
        self.assertEqual((data/'session.json').read_bytes(),before);self.assertIsNone(owner.poll())
        wire=WebWire(port)
        try:wire.ping()
        finally:wire.close()
    def test_stale_live_vm_metadata_is_not_consumed_or_removed(self):
        from linux_arm64_protocol import Runtime
        other_data=self.root/'other';other_data.mkdir(mode=0o700);other=Runtime(BINARY,other_data,1)
        try:
            data=self.root/'resume';data.mkdir(mode=0o700);stale=data/'pty.json';stale.write_bytes(other.info.read_bytes());stale.chmod(0o600)
            before=stale.read_bytes();owner,report=self.start(data,self.port(),True)
            self.assertNotEqual(report['vm_pid'],other.process.pid);self.assertEqual(stale.read_bytes(),before)
            other.wire.ping();self.stop(owner);other.wire.ping()
        finally:other.stop()
    def test_direct_vm_owner_is_preserved_after_failed_resume(self):
        from linux_arm64_protocol import Runtime
        data=self.root/'direct';data.mkdir(mode=0o700);other=Runtime(BINARY,data,1)
        try:
            before=(data/'program.ucode').read_bytes()
            result=subprocess.run(self.command(data,self.port(),True),capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0);self.assertNotIn('"state": "ready"',result.stdout)
            self.assertEqual((data/'program.ucode').read_bytes(),before);other.wire.ping()
        finally:other.stop()
    def test_occupied_http_port_cannot_falsely_report_ready(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'unrelated fixture')
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            port=server.server_port;data=self.root/'occupied'
            result=subprocess.run(self.command(data,port),capture_output=True,text=True,timeout=8)
            self.assertNotEqual(result.returncode,0);self.assertNotIn('"state": "ready"',result.stdout)
            report=json.loads((data/'session.json').read_text());self.assertEqual(report['state'],'failed')
            for pid in [report['vm_pid'],report['bridge_pid']]:self.assertFalse(Path(f'/proc/{pid}').exists())
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=2) as response:self.assertEqual(response.read(),b'unrelated fixture')
        finally:server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
