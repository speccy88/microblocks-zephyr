import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'linux/arm64'))
import blinka_setup as setup

def fixture_lock(extra=False):
    packages=[{'name':n,'version':v,'sha256':[h]} for n,v,h in (
        ('Adafruit-Blinka','10.1.0',setup.BLINKA_WHEEL_SHA256),
        ('gpiod','2.5.0','1'*64),('websockets','15.0.1','2'*64))]
    if extra:packages.append({'name':'fixture-addon','version':'1','sha256':['3'*64]})
    return {'schema':1,'source':'https://pypi.org','packages':packages}

class FakeRunner:
    def __init__(self):self.calls=[];self.fail_install=False;self.wrong_board=False;self.bad_hash=False
    def __call__(self,args,**kwargs):
        self.calls.append(args)
        if args[1:3]==['-m','venv']:
            env=Path(args[3]);(env/'bin').mkdir();(env/'bin/python').write_text('fixture interpreter')
        if '--report' in args:
            if self.fail_install:return subprocess.CompletedProcess(args,1)
            report=Path(args[args.index('--report')+1])
            entries=[]
            for line in Path(args[args.index('-r')+1]).read_text().splitlines():
                pin,hasharg,*_=line.split();name,version=pin.split('==')
                digest=hasharg.split(':')[-1]
                if self.bad_hash and name=='Adafruit-Blinka':digest='0'*64
                entries.append({'metadata':{'name':name,'version':version},
                    'download_info':{'url':'https://files.pythonhosted.org/fixture.whl','archive_info':{'hashes':{'sha256':digest}}}})
            report.write_text(json.dumps({'install':entries}))
        if '-c' in args:
            env=Path(args[0]).parents[1]
            data={'board_id':'RASPBERRY_PI_4B' if self.wrong_board else 'RASPBERRY_PI_5',
                'environment':str(env),'hardware_io_created':False,'versions':json.loads(args[-1])}
            return subprocess.CompletedProcess(args,0,json.dumps(data),'')
        return subprocess.CompletedProcess(args,0,'','')

@unittest.skipUnless(sys.platform=='linux' and os.geteuid()!=0,'Unprivileged Linux dependency environment')
class BlinkaSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.prefix=self.root/'app';self.model=self.root/'model';self.model.write_text('Raspberry Pi 5 Model B Rev 1.0\x00')
        self.runner=FakeRunner()
    def tearDown(self):self.tmp.cleanup()
    def ensure(self,**kw):return setup.ensure(self.prefix,model_path=self.model,runner=self.runner,lock=kw.pop('lock',fixture_lock()),**kw)
    def test_fresh_install_and_repeat_without_network_or_replacement(self):
        first=self.ensure();calls=len(self.runner.calls);second=self.ensure()
        self.assertFalse(first['reused']);self.assertTrue(second['reused']);self.assertEqual(first['environment'],second['environment'])
        self.assertEqual(len(self.runner.calls),calls+1)
        self.assertTrue(all('sudo' not in c and '--break-system-packages' not in c for c in self.runner.calls))
        self.assertEqual(first['requirements'],list(setup.REQUIREMENTS))
    def test_new_requirements_create_a_new_generation_and_keep_old(self):
        first=self.ensure();second=self.ensure(lock=fixture_lock(extra=True))
        self.assertNotEqual(first['environment'],second['environment']);self.assertTrue(Path(first['environment']).is_dir())
    def test_failed_update_preserves_selected_environment(self):
        first=self.ensure();active=self.prefix/'lib/microblocks/python/active.json';before=active.read_bytes()
        self.runner.fail_install=True
        with self.assertRaises(setup.SetupError):self.ensure(lock=fixture_lock(extra=True))
        self.assertEqual(active.read_bytes(),before);self.assertTrue(Path(first['environment']).is_dir())
        failed=[json.loads(p.read_text()) for p in active.parent.glob('*/installation.json')]
        self.assertTrue(any(x['state']=='failed' for x in failed))
    def test_wrong_hardware_or_forced_detection_is_not_accepted(self):
        self.model.write_text('Raspberry Pi 4 Model B')
        with self.assertRaises(setup.SetupError):self.ensure()
        self.assertFalse(self.prefix.exists());self.assertEqual(self.runner.calls,[])
        self.model.write_text('Raspberry Pi 5 Model B')
        with patch.dict(os.environ,{'BLINKA_FORCEBOARD':'RASPBERRY_PI_5'}),self.assertRaises(setup.SetupError):self.ensure()
    def test_wrong_board_import_or_artifact_hash_never_selects(self):
        self.runner.wrong_board=True
        with self.assertRaises(setup.SetupError):self.ensure()
        self.assertFalse((self.prefix/'lib/microblocks/python/active.json').exists())
        self.runner.wrong_board=False;self.runner.bad_hash=True
        with self.assertRaises(setup.SetupError):self.ensure()
        self.assertFalse((self.prefix/'lib/microblocks/python/active.json').exists())
    def test_unrelated_selection_and_symlink_paths_are_preserved(self):
        base=self.prefix/'lib/microblocks/python';base.mkdir(parents=True,mode=0o700)
        active=base/'active.json';active.write_text('{"owner":"another-app"}')
        with self.assertRaises(setup.SetupError):self.ensure()
        self.assertEqual(json.loads(active.read_text())['owner'],'another-app')
        link=self.root/'alias';link.symlink_to(self.prefix,target_is_directory=True)
        with self.assertRaises(setup.SetupError):setup.ensure(link,model_path=self.model,runner=self.runner)

    def test_verified_legacy_receipt_adopted_without_reinstall(self):
        first=self.ensure();active=self.prefix/'lib/microblocks/python/active.json'
        old=json.loads(active.read_text());old['key'].pop('lock_sha256');active.write_text(json.dumps(old))
        calls=len(self.runner.calls);second=self.ensure()
        self.assertTrue(second['reused']);self.assertEqual(first['environment'],second['environment'])
        self.assertEqual(len(self.runner.calls),calls+1)
        self.assertIn('lock_sha256',json.loads(active.read_text())['key'])

    def test_lock_rejects_unpinned_or_duplicate_dependencies_before_changes(self):
        invalid=fixture_lock();invalid['packages'][1]['sha256']=['bad']
        with self.assertRaises(setup.SetupError):self.ensure(lock=invalid)
        duplicate=fixture_lock();duplicate['packages'].append(duplicate['packages'][0])
        with self.assertRaises(setup.SetupError):self.ensure(lock=duplicate)
        self.assertEqual(self.runner.calls,[]);self.assertFalse(self.prefix.exists())

if __name__=='__main__':unittest.main()
