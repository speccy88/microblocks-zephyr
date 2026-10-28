"""Service ownership, immutable inputs and actual unit parser; no real service writes."""
# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('session_service',ROOT/'linux/arm64/service.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


@unittest.skipUnless(sys.platform=='linux' and os.geteuid()!=0,'unprivileged Linux required')
class SessionService(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='session-service-');self.root=Path(self.temp.name)
        self.prefix=self.root/'prefix space';self.data=self.root/'data space';self.editor=self.root/'editor';self.unitdir=self.root/'config/systemd/user'
        self.data.mkdir(mode=0o700);self.editor.mkdir();(self.editor/'microblocks.html').write_text('<title>Fixture</title>')
        (self.editor/'source-manifest.json').write_text(json.dumps({'source_commit':'5564b1e42d6790360450ebf11c9eb33a1c6877f2'}))
        release=self.prefix/'lib/microblocks/vtest';release.mkdir(parents=True);self.binary=release/'smallvm'
        raw=bytearray(64);raw[:6]=b'\x7fELF\x02\x01';struct.pack_into('<H',raw,18,183);self.binary.write_bytes(raw)
        (release/'manifest.json').write_text(json.dumps({'source_commit':'2071df569623ba9cdcd6f8106b61796e047df38b','architecture':'linux-aarch64','binary_sha256':hashlib.sha256(raw).hexdigest()}))
        (release.parent/'INSTALLATION').write_text('microblocks-linux-arm64-v1\n')
        (self.prefix/'bin').mkdir();(self.prefix/'bin/smallvm').write_text(s.MARKER+'\nexec "'+str(self.binary)+'" --data-dir "'+str(self.data)+'" "$@"\n')
        self.python=Path(sys.executable)
        self.calls=[]
        self.actual_wait_ready=s.wait_ready
        ready=patch.object(s,'wait_ready',return_value={'state':'ready','service_installed':True});ready.start();self.addCleanup(ready.stop)
    def tearDown(self):self.temp.cleanup()
    def run_mock(self,args,**kwargs):
        self.calls.append(args);return subprocess.CompletedProcess(args,0,'','')
    def install(self,port=0):
        if not port:
            with socket.socket() as x:x.bind(('127.0.0.1',0));port=x.getsockname()[1]
        return s.install(self.prefix,self.data,self.editor,self.python,port,unit_dir=self.unitdir)
    def test_generated_unit_real_parser_and_hardening(self):
        if not shutil.which('systemd-analyze'):self.skipTest('systemd-analyze missing')
        text=s.unit_text(self.prefix,self.data,self.editor,self.python,self.root,self.binary,18485)
        unit=self.root/s.UNIT;unit.write_text(text)
        p=subprocess.run(['systemd-analyze','verify',str(unit)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        for expected in ('--service-managed','--resume','KillMode=control-group','NoNewPrivileges=true','PrivateTmp=true','ProtectSystem=strict'):
            self.assertIn(expected,text)
        self.assertNotIn('0.0.0.0',text)
    def test_install_copies_exact_reviewed_sources_and_marks_ownership(self):
        with patch.object(s.subprocess,'run',side_effect=self.run_mock):report=self.install()
        self.assertFalse(report['unchanged']);self.assertFalse(report['lingering_changed'])
        runtime=self.prefix/'lib/microblocks-session'/report['runtime_sha256']
        for name in ('session.py','bridge.py'):self.assertEqual((runtime/name).read_bytes(),(ROOT/'linux/arm64'/name).read_bytes())
        self.assertIn('# microblocks-prefix='+str(self.prefix),(self.unitdir/s.UNIT).read_text())
        self.assertTrue(any(args[:4]==['systemctl','--user','enable','--now'] for args in self.calls))
    def test_foreign_unit_preserved(self):
        self.unitdir.mkdir(parents=True);unit=self.unitdir/s.UNIT;unit.write_text('# other service\n')
        with patch.object(s.subprocess,'run',side_effect=self.run_mock),self.assertRaisesRegex(ValueError,'Foreign'):
            self.install()
        self.assertEqual(unit.read_text(),'# other service\n');self.assertFalse((self.prefix/'lib/microblocks-session').exists())
    def test_active_same_configuration_idempotent_and_changed_configuration_refused(self):
        with patch.object(s.subprocess,'run',side_effect=self.run_mock):
            first=self.install();before=(self.unitdir/s.UNIT).read_bytes()
            again=self.install(first['port']);self.assertTrue(again['unchanged'])
            with self.assertRaisesRegex(ValueError,'Stop the owned'):self.install(first['port']+1)
        self.assertEqual((self.unitdir/s.UNIT).read_bytes(),before)
    def test_modified_binary_and_editor_pin_rejected_before_unit_creation(self):
        original=self.binary.read_bytes();self.binary.write_bytes(original+b'x')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):self.install()
        self.binary.write_bytes(original);(self.editor/'source-manifest.json').write_text('{"source_commit":"different"}')
        with self.assertRaisesRegex(ValueError,'editor source'):self.install()
        self.assertFalse(self.unitdir.exists())
    def test_missing_python_dependency_preserves_files(self):
        saved=self.data/'program.ucode';saved.write_bytes(b'preserve')
        with patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'')),self.assertRaisesRegex(ValueError,'websockets'):
            self.install()
        self.assertEqual(saved.read_bytes(),b'preserve');self.assertFalse(self.unitdir.exists())
    def test_nonprivate_data_and_symlink_unit_refused(self):
        self.data.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private'):self.install()
        self.data.chmod(0o700);self.unitdir.mkdir(parents=True);target=self.root/'other';target.write_text('keep');(self.unitdir/s.UNIT).symlink_to(target)
        with patch.object(s.subprocess,'run',side_effect=self.run_mock),self.assertRaisesRegex(ValueError,'symlink'):self.install()
        self.assertEqual(target.read_text(),'keep')
    def test_occupied_port_preserved_without_unit_or_runtime_creation(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1',0));server.listen(1);port=server.getsockname()[1]
            with patch.object(s.subprocess,'run',side_effect=self.run_mock),self.assertRaises(OSError):self.install(port)
        self.assertFalse(self.unitdir.exists());self.assertFalse((self.prefix/'lib/microblocks-session').exists())
    def test_recently_closed_listener_endpoint_is_reusable(self):
        server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind(('127.0.0.1',0));server.listen(1);port=server.getsockname()[1]
        client=socket.create_connection(('127.0.0.1',port));accepted,_=server.accept()
        accepted.close();client.recv(1);client.close();server.close()
        s.check_loopback_port(port)
    def test_unsafe_paths_and_privileged_ports(self):
        for name in ('relative','/tmp/a%name','/tmp/a\nname','/tmp/a"name','/tmp/trailing '):
            with self.assertRaises(ValueError):s.safe_path(Path(name))
        for port in (80,0,65536,True):
            with self.assertRaises(ValueError):s.unit_text(self.prefix,self.data,self.editor,self.python,self.root,self.binary,port)
    def test_ready_state_must_match_the_real_unit_pid_and_expected_endpoint(self):
        state={'supervisor_pid':123,'state':'ready','service_installed':True,'bind':'127.0.0.1','port':18876}
        path=self.data/'session.json';path.write_text(json.dumps(state));path.chmod(0o600)
        with patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'456\n','')):
            with self.assertRaises(RuntimeError):self.actual_wait_ready(self.data,18876,timeout=.01)
        with patch.object(s.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'123\n','')):
            self.assertEqual(self.actual_wait_ready(self.data,18876,timeout=.1)['supervisor_pid'],123)
            with self.assertRaises(RuntimeError):self.actual_wait_ready(self.data,18877,timeout=.01)
