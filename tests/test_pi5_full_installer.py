"""Real private filesystem lifecycle; build/dependency/systemd calls are fixtures."""
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if sys.platform=='linux':
    sys.path.insert(0,str(ROOT/'tools'))
    import install_pi5 as app

class FakeService:
    def __init__(self,prefix,root):self.prefix=prefix;self.path=root/'unit.service';self.name='fixture-pi5.service';self.stops=0;self.starts=0;self.fail_ready=False
    def verify(self,state):
        if self.path.exists() and (not state or state.get('unit_sha256')!=app.sha(self.path)):raise app.InstallError('unrelated service')
    def authorize(self):pass
    def text(self,release,python):return '# fixture-owned '+str(self.prefix)+'\n'+str(release)+'\n'+str(python)+'\n'
    def install(self,text):self.path.write_text(text);self.starts+=1;return app.sha(self.path)
    def stop(self):self.stops+=1
    def start(self):self.starts+=1
    def remove(self):self.path.unlink(missing_ok=True)
    def ready(self,expected):
        if self.fail_ready:self.fail_ready=False;raise app.InstallError('fixture candidate readiness failed')

@unittest.skipUnless(sys.platform=='linux' and os.geteuid()!=0,'Unprivileged Linux installer lifecycle')
class FullInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.prefix=self.root/'app'
        self.service=FakeService(self.prefix,self.root);self.builds=0;self.fail_build=False
        self.installer=app.Installer(self.prefix,builder=self.builder,dependencies=self.dependencies,service=self.service,order=lambda old,new:None)
        self.plan=app.endpoint('127.0.0.1',False,38877)
        self.port=patch.object(app,'port_available');self.port.start()
    def tearDown(self):self.port.stop();self.tmp.cleanup()
    def dependencies(self,prefix):
        interpreter=prefix/'fixture-python/bin/python';interpreter.parent.mkdir(parents=True,exist_ok=True);interpreter.write_text('not executed')
        return {'interpreter':str(interpreter)}
    def builder(self,source,stage,python,cache):
        if self.fail_build:raise app.InstallError('fixture build failed')
        self.builds+=1
        (stage/'native').mkdir();binary=stage/'native/smallvm';binary.write_bytes(('fixture binary '+str(self.builds)).encode())
        (stage/'editor').mkdir();(stage/'editor/index.html').write_text('fixture editor')
        code=stage/'code/linux/arm64';code.mkdir(parents=True);(code/'lan_service.py').write_text('# fixture only')
        return {'binary':'native/smallvm','binary_sha256':app.sha(binary),'editor':'editor','code':'code/linux/arm64/lan_service.py'}
    def install(self,commit='1',service=False):return self.installer.install(commit*40,'a'*64,self.plan,use_service=service)
    def test_fresh_repeat_and_uninstall_preserve_data_and_versions(self):
        first=self.install();self.assertEqual(first['status'],'prepared');self.assertEqual(self.builds,1)
        program=self.prefix/'data/program.ucode';program.write_bytes(b'user program')
        database=self.prefix/'python-state/programs.sqlite3';database.write_bytes(b'user database')
        repeat=self.install();self.assertEqual(repeat['status'],'already-current');self.assertEqual(self.builds,1)
        old_release=self.prefix/first['release'];result=self.installer.uninstall()
        self.assertTrue(result['programs_and_versions_retained']);self.assertEqual(program.read_bytes(),b'user program');self.assertEqual(database.read_bytes(),b'user database')
        self.assertTrue(old_release.is_dir());self.assertFalse((self.prefix/'bin/microblocks-pi5').exists())
        self.assertEqual(self.install()['status'],'prepared')
    def test_owned_service_source_update_preserves_program_database_profile(self):
        first=self.install(service=True);program=self.prefix/'data/program.ucode';program.write_bytes(b'user code')
        database=self.prefix/'python-state/programs.sqlite3';database.write_bytes(b'original database')
        profile=self.prefix/'python-profile.json';value=app.load(profile);value['extensions']['sqlite']['settings']['max_rows']=7;app.write_json(profile,value);profile_before=profile.read_bytes()
        second=self.install('2',service=True)
        self.assertNotEqual(first['release'],second['release']);self.assertTrue((self.prefix/first['release']).exists())
        self.assertEqual(program.read_bytes(),b'user code');self.assertEqual(database.read_bytes(),b'original database');self.assertEqual(profile.read_bytes(),profile_before)
        self.assertEqual(self.service.stops,1)
        self.installer.uninstall();self.assertFalse(self.service.path.exists());self.assertEqual(program.read_bytes(),b'user code')
    def test_failed_build_never_stops_or_changes_active_selection(self):
        first=self.install(service=True);before=(self.prefix/'service.json').read_bytes();unit=self.service.path.read_bytes()
        self.fail_build=True
        with self.assertRaises(app.InstallError):self.install('2',service=True)
        self.assertEqual((self.prefix/'service.json').read_bytes(),before);self.assertEqual(self.service.path.read_bytes(),unit);self.assertEqual(self.service.stops,0)
        self.assertEqual(app.load(self.prefix/'installed.json')['release'],first['release'])
    def test_failed_start_restores_config_unit_program_and_database(self):
        first=self.install(service=True);program=self.prefix/'data/program.ucode';program.write_bytes(b'code before update')
        database=self.prefix/'python-state/programs.sqlite3';database.write_bytes(b'database before update')
        old_config=(self.prefix/'service.json').read_bytes();old_unit=self.service.path.read_bytes()
        self.service.fail_ready=True
        with self.assertRaises(app.InstallError):self.install('2',service=True)
        self.assertEqual(app.load(self.prefix/'service.json'),json.loads(old_config));self.assertEqual(self.service.path.read_bytes(),old_unit)
        self.assertEqual(program.read_bytes(),b'code before update');self.assertEqual(database.read_bytes(),b'database before update')
        self.assertEqual(app.load(self.prefix/'installed.json')['release'],first['release'])
    def test_failed_fresh_start_removes_only_new_unit_and_keeps_version_data(self):
        self.service.fail_ready=True
        with self.assertRaises(app.InstallError):self.install(service=True)
        self.assertFalse(self.service.path.exists());self.assertFalse((self.prefix/'service.json').exists())
        self.assertTrue((self.prefix/'data').is_dir());self.assertTrue(list((self.prefix/'releases').iterdir()))
    def test_unrelated_prefix_or_service_is_not_modified(self):
        self.prefix.mkdir(mode=0o700);marker=self.prefix/'important.txt';marker.write_text('keep')
        with self.assertRaises(app.InstallError):self.install()
        self.assertEqual(marker.read_text(),'keep');self.assertEqual(self.builds,0)
        other=self.root/'other-app';other_service=FakeService(other,self.root);other_service.path.write_text('unrelated service')
        installer=app.Installer(other,builder=self.builder,dependencies=self.dependencies,service=other_service)
        with self.assertRaises(app.InstallError):installer.install('1'*40,'a'*64,self.plan,use_service=True)
        self.assertEqual(other_service.path.read_text(),'unrelated service');self.assertFalse(other.exists())
    def test_changed_release_and_custom_state_paths_require_review(self):
        selected=self.install();(self.prefix/selected['release']/'editor/index.html').write_text('changed by user')
        with self.assertRaises(app.InstallError):self.install()
        self.assertEqual(self.builds,1)
    def test_custom_state_paths_are_preserved_without_attempting_upgrade(self):
        self.install();config=app.load(self.prefix/'service.json');config['data']='custom-programs';app.write_json(self.prefix/'service.json',config)
        data=self.prefix/'custom-programs';data.mkdir();(data/'program.ucode').write_bytes(b'custom user code')
        with self.assertRaises(app.InstallError):self.install('2')
        self.assertEqual(app.load(self.prefix/'service.json')['data'],'custom-programs')
        self.assertEqual((data/'program.ucode').read_bytes(),b'custom user code');self.assertEqual(self.service.stops,0)
    def test_explicit_prepare_does_not_override_owned_service(self):
        self.install(service=True)
        with self.assertRaises(app.InstallError):self.installer.install('2'*40,'a'*64,self.plan,prepare_only=True)

    def test_proxy_source_updates_and_failed_start_preserve_origin_scope_and_data(self):
        self.plan=app.endpoint(port=38877,proxy_origin='http://192.168.2.50',additional_origins=['http://100.100.10.20','https://pi.tail-example.ts.net'])
        self.install(service=True)
        program=self.prefix/'data/program.ucode';program.write_bytes(b'keep this program')
        old=app.load(self.prefix/'service.json')
        self.assertNotIn('direct_bind',old);self.assertNotIn('clients',old)
        self.install('2',service=True)
        selected=app.load(self.prefix/'service.json')
        self.assertEqual(selected['origin'],old['origin']);self.assertEqual(selected['additional_origins'],old['additional_origins'])
        self.assertEqual(program.read_bytes(),b'keep this program')
        self.service.fail_ready=True
        with self.assertRaises(app.InstallError):self.install('3',service=True)
        self.assertEqual(app.load(self.prefix/'service.json'),selected)
        self.assertEqual(program.read_bytes(),b'keep this program')

    def test_changing_proxy_origins_reuses_only_the_owned_loopback_listener(self):
        self.plan=app.endpoint(port=38877,proxy_origin='http://192.168.2.50')
        self.install(service=True)
        with patch.object(app,'port_available') as available:
            self.plan=app.endpoint(port=38877,proxy_origin='http://192.168.2.50',additional_origins=['http://100.100.10.20'])
            self.install('2',service=True)
            available.assert_not_called()
        self.assertEqual(app.load(self.prefix/'service.json')['additional_origins'],['http://100.100.10.20'])
        self.assertEqual(self.service.stops,1)

@unittest.skipUnless(sys.platform=='linux','Direct listener and source policy')
class PolicyTests(unittest.TestCase):
    def test_proxy_mode_is_explicit_loopback_and_separate_from_direct_lan(self):
        plan=app.endpoint(port=38877,proxy_origin='http://192.168.2.50',additional_origins=['http://100.100.10.20'])
        self.assertEqual(plan,{'backend_port':38877,'origin':'http://192.168.2.50','additional_origins':['http://100.100.10.20']})
        secure=app.endpoint(port=38877,proxy_origin='http://192.168.2.50',additional_origins=['https://pi.tail-example.ts.net'])
        self.assertEqual(secure['additional_origins'],['https://pi.tail-example.ts.net'])
        for kwargs in ({'lan':True},{'bind':'127.0.0.1'},{'clients':'127.0.0.1/32'}):
            with self.assertRaises(app.InstallError):app.endpoint(proxy_origin='http://192.168.2.50',**kwargs)
        with self.assertRaises(app.InstallError):app.endpoint(additional_origins=['http://100.100.10.20'])
        with socket.socket() as existing:
            existing.bind(('127.0.0.1',0));port=existing.getsockname()[1]
            with self.assertRaises(app.InstallError):app.port_available(app.endpoint(port=port,proxy_origin='http://192.168.2.50'))

    def test_omitted_cli_options_keep_proxy_origins_and_explicit_options_replace_or_clear(self):
        old={'origin':'http://192.168.2.50','backend_port':38877,'additional_origins':['http://100.100.10.20']}
        def args(**change):
            return SimpleNamespace(**dict({'lan':False,'bind':None,'clients':None,'port':None,
                'proxy_origin':None,'additional_origins':None,'clear_additional_origins':False},**change))
        self.assertEqual(app.configured_endpoint(args(),old),old)
        replaced=app.configured_endpoint(args(additional_origins=['http://100.100.10.30']),old)
        self.assertEqual(replaced['additional_origins'],['http://100.100.10.30'])
        cleared=app.configured_endpoint(args(clear_additional_origins=True),old)
        self.assertEqual(cleared['additional_origins'],[]);self.assertEqual(cleared['origin'],old['origin'])
        self.assertNotIn('additional_origins',app.configured_endpoint(args(),{}))

    def test_loopback_and_explicit_lan_keep_exact_host_origin(self):
        local=app.endpoint('127.0.0.1',False,38877);self.assertEqual(local['clients'],'127.0.0.1/32')
        lan=app.endpoint('192.168.2.50',True,8877);self.assertEqual(lan['origin'],'http://192.168.2.50:8877')
        with self.assertRaises(app.InstallError):app.endpoint('192.168.2.50',False,8877)
        with self.assertRaises(app.InstallError):app.endpoint('127.0.0.1',False,80)
        with self.assertRaises(ValueError):app.endpoint('0.0.0.0',True,8877)
        from lan_editor import Policy
        class Headers:
            def __init__(self,host,origin):self.values={'Host':[host],'Origin':[origin],'Upgrade':['websocket']}
            def get_all(self,key):return self.values.get(key,[])
        policy=Policy('127.0.0.1',38877,'127.0.0.1/32');good=Headers('127.0.0.1:38877','http://127.0.0.1:38877')
        self.assertTrue(policy.request_allowed(('127.0.0.1',123),'/ws/vm',good))
        self.assertFalse(policy.request_allowed(('192.168.2.50',123),'/ws/vm',good))
        self.assertFalse(policy.request_allowed(('127.0.0.1',123),'/ws/vm',Headers('127.0.0.1:38877','https://evil.invalid')))
    def test_occupied_port_is_refused_without_changing_listener(self):
        with socket.socket() as existing:
            existing.bind(('127.0.0.1',0));port=existing.getsockname()[1]
            with self.assertRaises(app.InstallError):app.port_available(app.endpoint('127.0.0.1',False,port))
            self.assertEqual(existing.getsockname()[1],port)
    def test_source_downgrade_is_refused(self):
        import io
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*error):self.close()
        for status in ('behind','diverged','identical'):
            raw=json.dumps({'status':status,'merge_base_commit':{'sha':'1'*40}}).encode()
            with patch.object(app.urllib.request,'urlopen',return_value=Response(raw)),self.assertRaises(app.InstallError):app.source_order('1'*40,'2'*40)
        with patch.object(app.urllib.request,'urlopen',return_value=Response(json.dumps({'status':'ahead','merge_base_commit':{'sha':'1'*40}}).encode())):app.source_order('1'*40,'2'*40)

    def test_unrelated_real_unit_validation_never_runs_systemctl(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manager=app.SystemService(root/'app');manager.path=root/'existing.service';manager.path.write_text('unrelated service')
            with patch.object(app.subprocess,'check_output') as query,self.assertRaises(app.InstallError):manager.verify(None)
            query.assert_not_called();self.assertEqual(manager.path.read_text(),'unrelated service')
    def test_service_runs_as_current_unprivileged_user_without_capabilities(self):
        import pwd
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manager=app.SystemService(root/'app');unit=manager.text(root/'release',root/'python/bin/python')
            self.assertIn('User='+pwd.getpwuid(os.geteuid()).pw_name,unit)
            self.assertIn('NoNewPrivileges=true',unit);self.assertIn('WantedBy=multi-user.target',unit)
            self.assertNotIn('AmbientCapabilities',unit);self.assertNotIn('User=root',unit)
    @unittest.skipUnless(shutil.which('systemd-analyze'),'systemd unit parser required')
    def test_generated_unit_passes_real_systemd_parser_including_space_in_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prefix=root/'app with space';prefix.mkdir()
            manager=app.SystemService(prefix);unit=root/'pi5-verification.service'
            unit.write_text(manager.text(root/'release',Path(sys.executable)))
            checked=subprocess.run(['systemd-analyze','verify',str(unit)],capture_output=True,text=True)
            self.assertEqual(checked.returncode,0,checked.stderr)
    def test_foreground_state_lock_is_not_interrupted(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir();path=root/'data/.smallvm.lock';path.write_bytes(b'owned by foreground process')
            with path.open('rb+') as owner:
                fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(app.InstallError):app.state_unlocked(root)
                self.assertEqual(path.read_bytes(),b'owned by foreground process')

if __name__=='__main__':unittest.main()
