#!/usr/bin/env python3
"""Prepare a versioned isolated Pi5 Python environment, never enable hardware.

Official PyPI packages only. No sudo, OS upgrades, service/profile edits,
BLINKA_FORCE*, I2C constructors, pin requests, PWM, LEDs or sensor drivers.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import sys
import uuid

BLINKA_VERSION='10.1.0'
REQUIREMENTS=('Adafruit-Blinka==10.1.0','gpiod==2.5.0','websockets==15.0.1')
BLINKA_WHEEL_SHA256='6ff171b8b769a96a729385e7badf3dae1e6026b7a86fc0d9af38867ceb204c30'
PROBE=r'''
import importlib.metadata as m,json,sys
from adafruit_platformdetect import Detector
detector=Detector()
if detector.board.id!='RASPBERRY_PI_5':raise RuntimeError('Blinka did not detect RASPBERRY_PI_5')
import board,busio,digitalio,gpiod,websockets
expected=json.loads(sys.argv[1])
if any(m.version(name)!=version for name,version in expected.items()):raise RuntimeError('Pinned dependency versions differ')
if sys.prefix==sys.base_prefix:raise RuntimeError('Isolated Python environment required')
print(json.dumps({'board_id':detector.board.id,'chip_id':detector.chip.id,
    'python':sys.version.split()[0],'environment':sys.prefix,
    'versions':{n:m.version(n) for n in expected},
    'imports':['board','busio','digitalio','gpiod','websockets'],
    'scl_gpio':board.SCL.id,'sda_gpio':board.SDA.id,'hardware_io_created':False,
    'sensor_driver_installed':False,'physical_sensor_tested':False}))
'''

class SetupError(RuntimeError):pass

def atomic(path,value):
    temporary=path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as out:
            json.dump(value,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def private_directory(path):
    if path.is_symlink() or path.resolve()!=path:raise SetupError('Refusing a symlink dependency directory')
    path.mkdir(parents=True,mode=0o700,exist_ok=True)
    meta=path.stat()
    if meta.st_uid!=os.geteuid() or meta.st_mode&0o077:raise SetupError('Dependency state must be private and user owned')

def dependency_lock(value=None):
    value=value if value is not None else json.loads(Path(__file__).with_name('pi5-python-lock.json').read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict) or value.get('schema')!=1 or value.get('source')!='https://pypi.org':raise SetupError('Official PyPI dependency lock required')
    packages=value.get('packages')
    if not isinstance(packages,list) or not 3<=len(packages)<=128:raise SetupError('Invalid dependency lock size')
    by_name={}
    for item in packages:
        name=item.get('name');version=item.get('version');hashes=item.get('sha256')
        if (not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',name)
                or not isinstance(version,str) or not re.fullmatch(r'[0-9][A-Za-z0-9_.+!-]{0,63}',version)
                or not isinstance(hashes,list) or not 1<=len(hashes)<=256
                or any(not isinstance(h,str) or not re.fullmatch(r'[a-f0-9]{64}',h) for h in hashes)):
            raise SetupError('Invalid pinned dependency entry')
        normalized=re.sub(r'[-_.]+','-',name).lower()
        if normalized in by_name:raise SetupError('Duplicate dependency lock entry')
        by_name[normalized]=item
    for name,version in [('adafruit-blinka','10.1.0'),('gpiod','2.5.0'),('websockets','15.0.1')]:
        if by_name.get(name,{}).get('version')!=version:raise SetupError('Required dependency pin changed without review')
    digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return value,by_name,digest

def ensure(prefix,*,model_path=Path('/proc/device-tree/model'),runner=None,lock=None):
    runner=runner or subprocess.run
    locked,by_name,lock_sha=dependency_lock(lock)
    expected={item['name']:item['version'] for item in locked['packages']}
    raw=Path(prefix)
    if not raw.is_absolute() or '..' in raw.parts or raw.resolve()!=raw or raw==Path('/'):
        raise SetupError('Canonical absolute installation prefix required')
    if os.geteuid()==0:raise SetupError('Run as the intended ordinary user, not root')
    if sys.version_info<(3,11):raise SetupError('Python 3.11+ is required for the Pi application')
    model=model_path.read_text().strip('\x00\n')
    if not model.startswith('Raspberry Pi 5 Model B'):raise SetupError('This dependency profile requires a detected Raspberry Pi 5 Model B')
    if any(name.startswith('BLINKA_FORCE') or name=='BLINKA_SKIP_DEPENDENCY_CHECK' for name in os.environ):
        raise SetupError('Remove forced Blinka board/dependency overrides before automatic detection')
    base=raw/'lib/microblocks/python';private_directory(base)
    lock=os.open(base/'.setup.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    import fcntl
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:os.close(lock);raise SetupError('Another dependency setup is in progress') from None
    active=base/'active.json';key={'requirements':list(REQUIREMENTS),'python_minor':list(sys.version_info[:2]),'schema':1,'lock_sha256':lock_sha}
    # Pi OS may configure an additional wheel index globally. Disable config
    # for this child only; never rewrite the user's/system's pip settings.
    install_env={name:value for name,value in os.environ.items() if not name.startswith('PIP_')}
    install_env['PIP_CONFIG_FILE']=os.devnull
    def probe(environment):
        response=runner([str(environment/'bin/python'),'-B','-c',PROBE,json.dumps(expected)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=25)
        if response.returncode:raise SetupError('Blinka import/board detection failed: '+response.stderr[-600:].strip())
        value=json.loads(response.stdout)
        if value.get('board_id')!='RASPBERRY_PI_5' or value.get('hardware_io_created') is not False or value.get('versions')!=expected or Path(value['environment']).resolve()!=environment:
            raise SetupError('Unexpected Blinka verification result')
        return value
    try:
        if active.exists():
            if active.is_symlink():raise SetupError('Refusing a symlink dependency selection')
            previous=json.loads(active.read_text())
            if previous.get('owner')!='microblocks-pi5-python-v1':raise SetupError('Preserve an unrelated dependency selection')
            environment=Path(previous.get('environment',''))
            prior_key=previous.get('key',{})
            entries={re.sub(r'[-_.]+','-',p['name']).lower():p for p in previous.get('packages',[])}
            verified_legacy=(not prior_key.get('lock_sha256') and set(entries)==set(by_name)
                and all(entries[n]['version']==v['version'] and entries[n]['sha256'] in v['sha256'] for n,v in by_name.items())
                and prior_key.get('requirements')==key['requirements'] and prior_key.get('python_minor')==key['python_minor'])
            if (prior_key==key or verified_legacy) and environment.parent==base and environment.is_dir() and not environment.is_symlink():
                try:
                    result=probe(environment)
                    selected={**previous,'key':key,'reused':True,'verification':result}
                    if prior_key!=key:
                        atomic(environment/'installation.json',{'state':'ready',**selected});atomic(active,selected)
                    return selected
                except (OSError,ValueError,SetupError):pass
        environment=base/('blinka-'+BLINKA_VERSION+'-py'+str(sys.version_info[0])+str(sys.version_info[1])+'-'+uuid.uuid4().hex[:10])
        environment.mkdir(mode=0o700)
        atomic(environment/'installation.json',{'owner':'microblocks-pi5-python-v1','state':'preparing','key':key})
        requirements_file=environment/'requirements.txt'
        requirements_file.write_text('\n'.join(item['name']+'=='+item['version']+' '+ ' '.join('--hash=sha256:'+h for h in item['sha256']) for item in locked['packages'])+'\n')
        log=environment/'install.log'
        try:
            with log.open('wb') as output:
                for arguments,timeout in (([sys.executable,'-m','venv',str(environment)],90),
                    ([str(environment/'bin/python'),'-m','pip','--isolated','install','--disable-pip-version-check','--no-input','--index-url','https://pypi.org/simple','--report',str(environment/'pip-report.json'),'--require-hashes','-r',str(requirements_file)],300),
                    ([str(environment/'bin/python'),'-m','pip','--isolated','check'],30)):
                    result=runner(arguments,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,timeout=timeout,env=install_env)
                    if result.returncode:raise SetupError('Python dependency setup failed; existing selection preserved. See '+str(log))
            report=json.loads((environment/'pip-report.json').read_text())
            packages=[]
            for item in report['install']:
                name=item['metadata']['name'];version=item['metadata']['version']
                normalized=re.sub(r'[-_.]+','-',name).lower()
                digest=item['download_info']['archive_info'].get('hashes',{}).get('sha256')
                url=item['download_info']['url']
                from urllib.parse import urlsplit
                parsed=urlsplit(url)
                if parsed.scheme!='https' or parsed.hostname!='files.pythonhosted.org' or parsed.username or parsed.password:
                    raise SetupError('Dependency artifact did not come from official PyPI HTTPS storage')
                if normalized not in by_name or by_name[normalized]['version']!=version or digest not in by_name[normalized]['sha256']:
                    raise SetupError('Dependency differs from the verified PyPI lock: '+name)
                if normalized=='adafruit-blinka' and (version!=BLINKA_VERSION or digest!=BLINKA_WHEEL_SHA256):
                    raise SetupError('Official pinned Blinka wheel identity changed')
                packages.append({'name':name,'version':version,'sha256':digest})
            if {re.sub(r'[-_.]+','-',p['name']).lower() for p in packages}!=set(by_name):raise SetupError('Incomplete pinned installation receipt')
            verification=probe(environment)
            selected={'owner':'microblocks-pi5-python-v1','key':key,'environment':str(environment),
                'interpreter':str(environment/'bin/python'),'requirements':list(REQUIREMENTS),
                'packages':packages,'verification':verification,'model':model,'reused':False,
                'system_packages_changed':False,'service_configuration_changed':False,'i2c_or_permissions_changed':False}
            atomic(environment/'installation.json',{'state':'ready',**selected});atomic(active,selected)
            return selected
        except BaseException as error:
            atomic(environment/'installation.json',{'owner':'microblocks-pi5-python-v1','state':'failed','key':key,'error':str(error)[:800]})
            raise
    finally:os.close(lock)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prefix',type=Path,required=True);args=parser.parse_args()
    os.umask(0o077)
    try:print(json.dumps(ensure(args.prefix),indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:raise SystemExit(str(error))
