#!/usr/bin/env python3
"""Complete, owned Pi5 source install; no global Python or hardware setup.

Normally launched by the published checksum-pinned GitHub bootstrap. Native VM
remains v417. Local-only by default; --lan and --service are explicit actions.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import fcntl
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import socket
import subprocess
import sys
import sysconfig
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'linux/arm64'))
sys.path.insert(0,str(ROOT/'tools'))
from blinka_setup import ensure as ensure_python

OWNER='microblocks-pi5-v1'
UPSTREAM='https://codeberg.org/MicroBlocks/smallvm.git'
VM_COMMIT='2071df569623ba9cdcd6f8106b61796e047df38b'
PROJECT='speccy88/microblocks-zephyr'

class InstallError(RuntimeError):pass
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(value,why):
    if not value:raise InstallError(why)
def atomic(path,raw):
    path=Path(path);temporary=path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)
def write_json(path,value):atomic(path,(json.dumps(value,indent=2)+'\n').encode())
def load(path):return json.loads(Path(path).read_text())
def canonical_prefix(value):
    path=Path(value)
    require(path.is_absolute() and path!=Path('/') and '..' not in path.parts and path.resolve()==path,'Use a canonical absolute non-root prefix without symlinks')
    require(not re.search(r'[\x00-\x1f$"%\\]',str(path)),'Prefix contains unsupported service/path characters')
    return path
def host_prerequisites(install=False,build=True):
    require(platform.system()=='Linux' and platform.machine()=='aarch64','Requires native 64-bit AArch64 Linux')
    require(os.geteuid()!=0,'Run as your ordinary account; do not run this installer as root')
    require(sys.version_info>=(3,11),'Requires Python 3.11+ (a current 64-bit Pi OS/Debian installation)')
    model=Path('/proc/device-tree/model')
    require(model.is_file() and model.read_text().startswith('Raspberry Pi 5 Model B'),'Requires a real Raspberry Pi 5 Model B; no forced board selection')
    missing=[]
    for command,package in ([('git','git'),('gcc','build-essential')] if build else []):
        if shutil.which(command) is None:missing.append(package)
    if importlib.util.find_spec('ensurepip') is None:missing.append('python3-venv')
    if build and not (Path(sysconfig.get_path('include'))/'Python.h').is_file():missing.append('python3-dev')
    if missing:
        packages=sorted(set(missing))
        require(install,'Missing prerequisites. Install: sudo apt-get install '+' '.join(packages)+'; or explicitly pass --install-prerequisites')
        subprocess.run(['sudo','-n','apt-get','update'],check=True,stdin=subprocess.DEVNULL)
        subprocess.run(['sudo','-n','apt-get','install','-y',*packages],check=True,stdin=subprocess.DEVNULL)

def endpoint(bind=None,lan=False,port=8877,clients=None,*,proxy_origin=None,additional_origins=None):
    require(type(port) is int and 1024<=port<=65535,'Use an unprivileged port 1024..65535. Port 80/Caddy is never replaced; use 8877 or configure a proxy separately.')
    if proxy_origin is not None:
        require(not lan and bind is None and clients is None,'Choose either --proxy-origin or the direct --lan/--bind/--clients options')
        from lan_editor import LoopbackProxyPolicy
        policy=LoopbackProxyPolicy(proxy_origin,port,[] if additional_origins is None else additional_origins)
        return {'backend_port':port,'origin':policy.origin,'additional_origins':policy.origins[1:]}
    require(additional_origins is None,'--additional-origin/--clear-additional-origins requires --proxy-origin or an existing proxy installation')
    if lan and bind is None:
        result=subprocess.check_output(['ip','-j','-4','addr','show','scope','global'],text=True)
        addresses={}
        for interface in json.loads(result):
            for record in interface.get('addr_info',[]):
                address=record.get('local')
                if address and any(ipaddress.ip_address(address) in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):addresses[address]=record.get('prefixlen',24)
        require(len(addresses)==1,'Multiple/no private addresses: choose --bind PRIVATE_IP explicitly')
        bind=next(iter(addresses))
        clients=clients or str(ipaddress.ip_network(bind+'/'+str(max(24,addresses[bind])),strict=False))
    bind=bind or '127.0.0.1'
    from lan_editor import Policy
    if bind=='127.0.0.1':
        require(not lan,'--lan requires a private interface address');clients=clients or '127.0.0.1/32'
    else:
        require(lan,'A non-loopback address requires explicit --lan (unauthenticated HTTP/WS)')
        clients=clients or str(ipaddress.ip_network(bind+'/24',strict=False))
    policy=Policy(bind,port,clients)
    return {'direct_bind':policy.bind,'clients':str(policy.clients),'backend_port':port,'origin':policy.origin}

def port_available(plan):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as check:
        try:check.bind((plan.get('direct_bind','127.0.0.1'),plan['backend_port']))
        except OSError as error:raise InstallError('Address/port is occupied or unavailable; existing services are preserved. Choose another --port.') from error


def same_listener(previous,plan):
    return bool(previous) and previous.get('direct_bind','127.0.0.1')==plan.get('direct_bind','127.0.0.1') and previous.get('backend_port')==plan.get('backend_port')


def configured_endpoint(args,old):
    """Omitted endpoint options retain an owned installation's exact proxy scope."""
    direct_requested=args.lan or args.bind is not None or args.clients is not None
    existing_proxy=bool(old) and old.get('direct_bind') is None
    proxy=args.proxy_origin or (old.get('origin') if existing_proxy and not direct_requested else None)
    extra=args.additional_origins
    if args.clear_additional_origins:
        extra=[]
    elif extra is None and proxy is not None:
        extra=old.get('additional_origins',[])
    if proxy is not None:
        return endpoint(args.bind,args.lan,args.port or old.get('backend_port',8877),args.clients,
            proxy_origin=proxy,additional_origins=extra)
    return endpoint(args.bind or (old.get('direct_bind') if not args.lan else None),
        args.lan or bool(old.get('direct_bind') and old['direct_bind']!='127.0.0.1'),
        args.port or old.get('backend_port',8877),args.clients or old.get('clients'),additional_origins=extra)

def state_unlocked(prefix):
    for name in ('data/.smallvm.lock','python-state/.python.lock'):
        path=prefix/name
        if not path.exists():continue
        require(not path.is_symlink(),'Preserve an unexpected state lock')
        fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
        try:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise InstallError('An existing foreground VM/Python process owns the data; stop it explicitly before updating') from None
        finally:os.close(fd)

def source_order(previous,current):
    if not previous or previous==current:return
    require(re.fullmatch('[a-f0-9]{40}',previous) is not None,'Installed source revision is unknown; do not silently replace it')
    url='https://api.github.com/repos/'+PROJECT+'/compare/'+previous+'...'+current+'?per_page=1'
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'MicroBlocks-Pi5-Installer/1','Accept':'application/vnd.github+json'}),timeout=20) as response:
        raw=response.read(3*1024*1024+1)
    require(len(raw)<=3*1024*1024,'Project comparison is too large; selection unchanged')
    result=json.loads(raw)
    require(result.get('status')=='ahead' and result.get('merge_base_commit',{}).get('sha')==previous,'Refusing an older or diverging source revision')

def run_logged(args,log,cwd=None,timeout=300):
    with Path(log).open('ab') as output:
        result=subprocess.run([str(x) for x in args],cwd=cwd,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
    require(result.returncode==0,'Command failed; current installation preserved. See '+str(log))

def build_release(source,stage,python,cache):
    """Real build: exact upstream Git objects and hash-checked JS source assets."""
    log=stage/'build.log';upstream=cache/'upstream'
    if not upstream.exists():
        run_logged(['git','init','-q',upstream],log)
        run_logged(['git','-C',upstream,'remote','add','origin',UPSTREAM],log)
    origin=subprocess.check_output(['git','-C',str(upstream),'remote','get-url','origin'],text=True).strip()
    require(origin==UPSTREAM,'Preserve an unrelated source cache')
    present=subprocess.run(['git','-C',str(upstream),'cat-file','-e',VM_COMMIT+'^{commit}'],capture_output=True).returncode==0
    if not present:run_logged(['git','-C',upstream,'fetch','--depth=1','origin',VM_COMMIT],log,timeout=300)
    run_logged([sys.executable,'-B',source/'linux/arm64/build.py','--upstream',upstream,'--output',stage/'native','--test'],log,timeout=300)
    binary=stage/'native/smallvm';header=binary.read_bytes()[:20]
    require(header[:6]==b'\x7fELF\x02\x01' and header[18:20]==bytes([183,0]),'Build did not produce native ARM64 ELF')
    from mobile_editor_source import prepare_archive,read_editor
    editor_source=cache/'editor-source'
    if editor_source.exists():read_editor(editor_source)
    else:prepare_archive(cache/'editor-source.zip',editor_source,fetch=True)
    from package_pi_lan_editor import package as package_pi
    from package_python_extension_editor import package as package_python
    package_pi(editor_source,stage/'editor-base');package_python(stage/'editor-base',stage/'editor')
    code=stage/'code/linux';(code/'arm64').mkdir(parents=True)
    for item in (source/'linux/arm64').glob('*.py'):shutil.copy2(item,code/'arm64'/item.name)
    shutil.copy2(source/'linux/arm64/pi5-python-lock.json',code/'arm64/pi5-python-lock.json')
    shutil.copy2(source/'scripts/install-smallvm-linux-arm64.sh',code/'arm64/install-smallvm-linux-arm64.sh')
    shutil.copytree(source/'linux/extensions',code/'extensions',ignore=shutil.ignore_patterns('__pycache__','tests'))
    (code/'microduck').mkdir()
    for item in (source/'linux/microduck').glob('*.py'):shutil.copy2(item,code/'microduck'/item.name)
    shutil.copy2(source/'LICENSES.md',stage/'LICENSES.md')
    return {'binary':'native/smallvm','binary_sha256':sha(binary),'editor':'editor','code':'code/linux/arm64/lan_service.py'}

def seal_release(stage,metadata):
    files={p.relative_to(stage).as_posix():sha(p) for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='receipt.json'}
    require(not any(p.is_symlink() for p in stage.rglob('*')),'Release may not contain symlinks')
    write_json(stage/'receipt.json',{'owner':OWNER,'files':files,**metadata})
def verify_release(stage):
    require(stage.is_dir() and not stage.is_symlink(),'Missing managed release')
    receipt=load(stage/'receipt.json');require(receipt.get('owner')==OWNER,'Unrecognized release')
    for name,digest in receipt['files'].items():
        path=stage/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink() and path.resolve().is_relative_to(stage),'Unsafe release entry')
        require(sha(path)==digest,'Installed release changed: '+name)
    return receipt

class SystemService:
    def __init__(self,prefix):
        self.prefix=prefix;self.name='microblocks-pi5-'+str(os.geteuid())+'-'+hashlib.sha256(str(prefix).encode()).hexdigest()[:10]+'.service'
        self.path=Path('/etc/systemd/system')/self.name
    def verify(self,state):
        if self.path.exists():
            require(not self.path.is_symlink() and state and state.get('unit_sha256')==sha(self.path),'Existing service is unrelated or modified; preserve it for review')
            require(self.path.read_text().startswith('# '+OWNER+' '+str(self.prefix)+'\n'),'Existing service belongs to another prefix')
            drops=subprocess.check_output(['systemctl','show',self.name,'-p','DropInPaths','--value'],text=True).strip()
            require(not drops,'Existing service overrides require manual review')
        else:require(not state or not state.get('unit_sha256'),'Owned service disappeared; review before changing the installation')
    def authorize(self):
        require(shutil.which('systemctl') and shutil.which('systemd-analyze') and shutil.which('sudo'),'systemd, systemd-analyze and sudo are required for --service; use --prepare-only otherwise')
        result=subprocess.run(['sudo','-n','true'],stdin=subprocess.DEVNULL,capture_output=True)
        require(result.returncode==0,'Service/prerequisite setup needs sudo authorization. Run sudo -v, then repeat the same installer.')
    def stop(self):subprocess.run(['sudo','-n','systemctl','stop',self.name],check=True)
    def start(self):subprocess.run(['sudo','-n','systemctl','start',self.name],check=True)
    def text(self,release,python):
        user=pwd.getpwuid(os.geteuid()).pw_name
        return ('# '+OWNER+' '+str(self.prefix)+'\n[Unit]\nDescription=MicroBlocks Pi5 editor, VM and Python\nAfter=network-online.target\nWants=network-online.target\n\n[Service]\nType=simple\nUser='+user+'\nWorkingDirectory='+str(self.prefix)+'\nExecStart="'+str(python)+'" -B "'+str(release/'code/linux/arm64/lan_service.py')+'" --root "'+str(self.prefix)+'"\nRestart=on-failure\nRestartSec=2\nTimeoutStopSec=20\nUMask=0077\nNoNewPrivileges=true\n\n[Install]\nWantedBy=multi-user.target\n')
    def install(self,text):
        path=self.prefix/'run'/self.name;atomic(path,text.encode())
        checked=subprocess.run(['systemd-analyze','verify',str(path)],capture_output=True,text=True)
        require(checked.returncode==0,'Generated service failed systemd validation; selection preserved: '+checked.stderr[-800:])
        subprocess.run(['sudo','-n','install','-m','644',str(path),str(self.path)],check=True)
        subprocess.run(['sudo','-n','systemctl','daemon-reload'],check=True)
        subprocess.run(['sudo','-n','systemctl','enable',self.name],check=True)
        self.start();return sha(self.path)
    def remove(self):
        subprocess.run(['sudo','-n','systemctl','disable','--now',self.name],check=True)
        subprocess.run(['sudo','-n','rm','--',str(self.path)],check=True)
        subprocess.run(['sudo','-n','systemctl','daemon-reload'],check=True)
    def ready(self,expected):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            try:
                state=load(self.prefix/'run/status.json')
                pid=int(subprocess.check_output(['systemctl','show',self.name,'-p','MainPID','--value'],text=True))
                if state['state']=='ready' and state['supervisor_pid']==pid and state['binary_sha256']==expected:return
            except (OSError,ValueError,KeyError):pass
            time.sleep(.2)
        raise InstallError('Owned service failed readiness; restoring the previous selection')

class Installer:
    def __init__(self,prefix,*,builder=build_release,dependencies=ensure_python,service=None,order=source_order):
        self.prefix=canonical_prefix(prefix);self.builder=builder;self.dependencies=dependencies;self.service=service or SystemService(self.prefix);self.order=order
    def state(self):
        marker=self.prefix/'INSTALLATION.json'
        if self.prefix.exists():
            require(self.prefix.is_dir() and self.prefix.stat().st_uid==os.geteuid() and not self.prefix.stat().st_mode&0o077,'Existing prefix must be private and current-user owned')
            require(marker.is_file() and not marker.is_symlink() and load(marker).get('owner')==OWNER,'Preserve an unrelated or unrecognized installation prefix')
        selected=load(self.prefix/'installed.json') if (self.prefix/'installed.json').exists() else None
        if selected:
            require(selected.get('owner')==OWNER,'Preserve unrelated installation metadata')
            relative=Path(selected.get('release','/'))
            require(not relative.is_absolute() and '..' not in relative.parts and relative.parts and relative.parts[0]=='releases','Unsafe installed release path')
        return selected
    def uninstall(self):
        previous=self.state();require(previous,'No managed installation to uninstall')
        self.service.verify(previous)
        if previous.get('unit_sha256'):self.service.authorize();self.service.remove()
        launcher=self.prefix/'bin/microblocks-pi5'
        if launcher.exists():
            require(not launcher.is_symlink() and sha(launcher)==previous['launcher_sha256'],'Preserve a modified launcher')
            launcher.unlink()
        write_json(self.prefix/'installed.json',{**previous,'unit_sha256':None,'status':'uninstalled'})
        return {'status':'uninstalled','programs_and_versions_retained':True,'prefix':str(self.prefix)}
    def install(self,commit,archive_sha,plan,*,use_service=False,prepare_only=False,native_updates=False):
        require(isinstance(commit,str) and isinstance(archive_sha,str) and re.fullmatch('[a-f0-9]{40}',commit) and re.fullmatch('[a-f0-9]{64}',archive_sha),'Verified source commit and archive SHA-256 required')
        previous=self.state();self.service.verify(previous)
        wanted=use_service or bool(previous and previous.get('unit_sha256'))
        require(not(prepare_only and previous and previous.get('unit_sha256')),'Do not prepare over an active installation; choose a separate prefix')
        if wanted:self.service.authorize()
        # Fail occupied/privileged ports before creating any installation state.
        old_config=load(self.prefix/'service.json') if (self.prefix/'service.json').exists() else None
        if old_config:
            settings=old_config.get('python_extensions',{})
            require(old_config.get('data')=='data' and settings.get('profile')=='python-profile.json' and settings.get('state')=='python-state','Customized state paths require manual migration; existing configuration is preserved')
        if not(previous and previous.get('unit_sha256') and same_listener(old_config,plan)):port_available(plan)
        self.order(previous.get('source_commit') if previous else None,commit)
        self.prefix.mkdir(mode=0o700,parents=True,exist_ok=True)
        if not(self.prefix/'INSTALLATION.json').exists():write_json(self.prefix/'INSTALLATION.json',{'owner':OWNER,'uid':os.geteuid(),'schema':1})
        for name in ('cache','releases','backups','bin','run','data','python-state'):(self.prefix/name).mkdir(mode=0o700,exist_ok=True)
        lock=os.open(self.prefix/'run/install.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:os.close(lock);raise InstallError('Another installer is active') from None
        try:
            print('Preparing verified isolated Python/Blinka dependencies...',flush=True)
            python=self.dependencies(self.prefix)
            same_source=previous and previous['source_commit']==commit
            if same_source:
                release=self.prefix/previous['release'];metadata=verify_release(release)
            else:
                release=self.prefix/'releases'/('pi5-'+commit[:12]+'-'+uuid.uuid4().hex[:8]);release.mkdir(mode=0o700)
                print('Building pinned native VM417 and packaging the verified editor...',flush=True)
                metadata=self.builder(ROOT,release,Path(python['interpreter']),self.prefix/'cache')
                metadata={**metadata,'source_commit':commit,'source_archive_sha256':archive_sha}
                seal_release(release,metadata)
            profile=self.prefix/'python-profile.json'
            if not profile.exists():shutil.copy2(ROOT/'linux/extensions/profiles/pi5.json',profile);profile.chmod(0o600)
            require(not profile.is_symlink(),'Preserve a symlink application profile for review')
            config=dict(old_config or {},schema=1,vm_version=417,
                binary=(release/metadata['binary']).relative_to(self.prefix).as_posix(),binary_sha256=metadata['binary_sha256'],
                editor=(release/metadata['editor']).relative_to(self.prefix).as_posix(),data='data',
                release_version='pi5-source-'+commit[:12],native_port_commit=commit,
                required_runtime_capabilities=['python-extensions'],authentication=False,encryption=False,
                allow_browser_native_install=native_updates or bool(old_config and old_config.get('allow_browser_native_install')),
                python_extensions={'profile':'python-profile.json','state':'python-state','interpreter':python['interpreter']},**plan)
            # Endpoint mode comes from this validated plan, not stale fields from
            # a previous direct/proxy selection. Other installation settings stay.
            for key in ('direct_bind','clients','additional_origins'):
                if key not in plan:config.pop(key,None)
            launcher=self.prefix/'bin/microblocks-pi5'
            launcher_text=('#!/bin/sh\n# '+OWNER+'\nexec '+__import__('shlex').quote(python['interpreter'])+' -B '+__import__('shlex').quote(str(release/'code/linux/arm64/lan_service.py'))+' --root '+__import__('shlex').quote(str(self.prefix))+'\n').encode()
            if previous and same_source and old_config==config and launcher.exists() and sha(launcher)==previous.get('launcher_sha256') and (not wanted or previous.get('unit_sha256')):
                if wanted:self.service.ready(metadata['binary_sha256'])
                return {'status':'already-current','origin':plan['origin'],'prefix':str(self.prefix),'source_commit':commit,'python':python['interpreter']}
            backup=self.prefix/'backups'/uuid.uuid4().hex;backup.mkdir(mode=0o700)
            if old_config:write_json(backup/'service.json',old_config)
            if previous:write_json(backup/'installed.json',previous)
            if launcher.exists():
                require(previous and sha(launcher)==previous.get('launcher_sha256'),'Preserve an unrelated launcher')
                shutil.copy2(launcher,backup/'launcher')
            old_unit=self.service.path.read_bytes() if previous and previous.get('unit_sha256') else None
            if old_unit:(backup/'service-unit').write_bytes(old_unit)
            for name in ('data','python-state'):
                for path in (self.prefix/name).rglob('*'):require(not path.is_symlink() and (path.is_file() or path.is_dir() or path.is_socket()),'Unexpected state entry; preserve it for review')
            if previous and previous.get('unit_sha256'):self.service.stop()
            snapshots_complete=False
            try:
                state_unlocked(self.prefix)
                for name in ('data','python-state'):
                    require(not any(p.is_socket() for p in (self.prefix/name).rglob('*')),'An application is still running; stop its owned foreground process before updating')
                    shutil.copytree(self.prefix/name,backup/name)
                snapshots_complete=True
                write_json(self.prefix/'service.json',config);atomic(launcher,launcher_text);launcher.chmod(0o700)
                unit_sha=self.service.install(self.service.text(release,Path(python['interpreter']))) if wanted else None
                if wanted:self.service.ready(metadata['binary_sha256'])
                selected={'owner':OWNER,'source_commit':commit,'source_archive_sha256':archive_sha,
                    'release':release.relative_to(self.prefix).as_posix(),'binary_sha256':metadata['binary_sha256'],
                    'launcher_sha256':sha(launcher),'unit_sha256':unit_sha,'unit_name':self.service.name,
                    'origin':plan['origin'],'status':'active' if wanted else 'prepared','backup':str(backup)}
                write_json(self.prefix/'installed.json',selected)
                return {**selected,'prefix':str(self.prefix),'python':python['interpreter'],'hardware_enabled':False}
            except BaseException:
                if wanted and self.service.path.exists():self.service.stop()
                if wanted and not old_unit and self.service.path.exists():self.service.remove()
                if old_config:write_json(self.prefix/'service.json',old_config)
                else:(self.prefix/'service.json').unlink(missing_ok=True)
                if (backup/'launcher').exists():atomic(launcher,(backup/'launcher').read_bytes());launcher.chmod(0o700)
                else:launcher.unlink(missing_ok=True)
                if snapshots_complete:
                    state_unlocked(self.prefix)
                    for name in ('data','python-state'):
                        failed=backup/('failed-'+name)
                        require((self.prefix/name).resolve().is_relative_to(self.prefix),'State path escaped its prefix')
                        (self.prefix/name).rename(failed)
                        shutil.copytree(backup/name,self.prefix/name)
                if previous:write_json(self.prefix/'installed.json',previous)
                if old_unit:self.service.install(old_unit.decode());self.service.ready(previous['binary_sha256'])
                raise
        finally:os.close(lock)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',type=Path,default=Path.home()/'.local/share/microblocks-pi5')
    parser.add_argument('--bind');parser.add_argument('--lan',action='store_true');parser.add_argument('--clients');parser.add_argument('--port',type=int)
    parser.add_argument('--proxy-origin',help='Exact public HTTP IPv4 origin on an existing port-80 reverse proxy; backend remains loopback-only')
    origins=parser.add_mutually_exclusive_group()
    origins.add_argument('--additional-origin',dest='additional_origins',action='append',help='Additional exact private/Tailscale HTTP origin; repeat to select the full list')
    origins.add_argument('--clear-additional-origins',action='store_true',help='Explicitly remove additional proxy origins')
    parser.add_argument('--service',action='store_true');parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--enable-native-updates',action='store_true');parser.add_argument('--install-prerequisites',action='store_true')
    parser.add_argument('--uninstall',action='store_true');parser.add_argument('--blinka-only',action='store_true');parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--source-commit');parser.add_argument('--source-sha256')
    args=parser.parse_args();os.umask(0o077)
    try:
        require(not(args.service and args.prepare_only),'Choose --service or --prepare-only')
        prefix=canonical_prefix(args.prefix)
        if args.uninstall:
            require(os.geteuid()!=0,'Run uninstall as the original ordinary account')
            print(json.dumps(Installer(prefix).uninstall(),indent=2));return
        if args.blinka_only:
            require(not(args.service or args.lan or args.enable_native_updates or args.proxy_origin or args.additional_origins or args.clear_additional_origins),'Dependency-only setup never changes or exposes a service')
            host_prerequisites(args.install_prerequisites,build=False)
            print(json.dumps(ensure_python(prefix),indent=2));return
        marker=ROOT/'.pi5-bootstrap.json'
        source=load(marker) if marker.is_file() else {}
        commit=args.source_commit or source.get('source_commit');archive_sha=args.source_sha256 or source.get('source_sha256')
        require(isinstance(commit,str) and isinstance(archive_sha,str) and re.fullmatch('[a-f0-9]{40}',commit) and re.fullmatch('[a-f0-9]{64}',archive_sha),'Verified bootstrap/source identity is required before installation')
        installer=Installer(prefix);previous=installer.state();installer.service.verify(previous)
        require(not(args.prepare_only and previous and previous.get('unit_sha256')),'Use a separate prefix for prepare-only testing')
        old=load(prefix/'service.json') if (prefix/'service.json').exists() else {}
        chosen=configured_endpoint(args,old)
        if not(previous and previous.get('unit_sha256') and same_listener(old,chosen)):port_available(chosen)
        if args.dry_run:
            print(json.dumps({'prefix':str(prefix),'endpoint':chosen,'service_requested':args.service,'install_prerequisites_requested':args.install_prerequisites,'native_vm_version':417,'no_changes':True},indent=2));return
        # Validate target and explicit prerequisites; never upgrade/configure OS hardware.
        host_prerequisites(args.install_prerequisites)
        scope=('explicit client scope '+chosen['clients']) if 'direct_bind' in chosen else ('loopback proxy; exact origins '+', '.join([chosen['origin'],*chosen['additional_origins']]))
        print('Endpoint: '+chosen['origin']+' (unauthenticated HTTP/WS; '+scope+')',flush=True)
        print(json.dumps(installer.install(commit,archive_sha,chosen,use_service=args.service,prepare_only=args.prepare_only,native_updates=args.enable_native_updates),indent=2))
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
        raise SystemExit('Pi5 installation stopped: '+str(error))

if __name__=='__main__':main()
