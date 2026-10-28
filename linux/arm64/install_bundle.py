#!/usr/bin/env python3
"""Install a verified self-contained Pi5 candidate, without runtime downloads.

Run from the extracted bundle. Published bootstrap must authenticate its outer
archive SHA256 first. This manifest checks consistency, not publisher identity.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import platform
import pwd
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile

_bytecode_setting=sys.dont_write_bytecode
sys.dont_write_bytecode=True
from service import safe_path, owned_private_directory, check_loopback_port
sys.dont_write_bytecode=_bytecode_setting


def verify_bundle(root):
    raw=(root/'bundle-manifest.json').read_bytes()
    if len(raw)>1024*1024:raise ValueError('Oversized bundle manifest')
    manifest=json.loads(raw);files=manifest['files']
    if manifest.get('platform')!='raspberry-pi5-aarch64' or not 1<=len(files)<=5000:raise ValueError('Unexpected bundle target/layout')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if not stat.S_ISDIR(p.lstat().st_mode)}
    if actual!=set(files)|{'bundle-manifest.json'}:raise ValueError('Bundle member set differs')
    total=0
    for name,digest in files.items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or path.as_posix()!=name:raise ValueError('Unsafe bundle path')
        target=root/name
        if target.is_symlink() or not target.is_file():raise ValueError('Bundle links/special files refused')
        data=target.read_bytes();total+=len(data)
        if len(data)>64*1024*1024 or total>256*1024*1024:raise ValueError('Bundle exceeds size limit')
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Bundle hash mismatch: '+name)
    return manifest,hashlib.sha256(raw).hexdigest()


def copy_immutable(source,target):
    if target.is_symlink():raise ValueError('Managed destination cannot be a symlink')
    if target.exists():
        existing={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file() and not p.is_symlink()}
        expected={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        if existing!=expected or any(p.is_symlink() for p in target.rglob('*')):raise ValueError('Existing immutable installation differs')
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix='.bundle-copy-',dir=target.parent))
        try:shutil.copytree(source,staged,dirs_exist_ok=True);os.rename(staged,target)
        finally:
            if staged.exists():shutil.rmtree(staged)


def boot_startup(login_only):
    user=pwd.getpwuid(os.geteuid()).pw_name
    enabled=subprocess.check_output(['loginctl','show-user',str(os.getuid()),'-p','Linger','--value'],text=True).strip()=='yes'
    if not enabled and not login_only:
        # Persistent session policy is a separate, explicit human choice.
        try:
            with open('/dev/tty','r+') as terminal:
                terminal.write('Enable this user\'s services at boot and after logout? This changes systemd lingering. [y/N] ');terminal.flush();answer=terminal.readline().strip().lower()
        except OSError:answer=''
        if answer not in ('y','yes'):
            raise ValueError('Boot startup needs explicit lingering consent; rerun interactively or choose --login-startup')
        subprocess.run(['sudo','loginctl','enable-linger',user],check=True)
        enabled=subprocess.check_output(['loginctl','show-user',str(os.getuid()),'-p','Linger','--value'],text=True).strip()=='yes'
        if not enabled:raise RuntimeError('Boot startup was not enabled')
    return 'boot-existing-or-explicitly-approved-linger' if enabled else 'after-user-login'


def install(root,prefix,data,port,login_only=False):
    if platform.system()!='Linux' or platform.machine()!='aarch64' or os.geteuid()==0:
        raise ValueError('Run as the intended unprivileged user on64-bit Raspberry Pi5 Linux')
    model=Path('/proc/device-tree/model').read_text().rstrip('\0')
    if not model.startswith('Raspberry Pi 5 '):raise ValueError('This installer is validated only for Raspberry Pi5; MicroDuck is separate')
    if sys.version_info<(3,10):raise ValueError('Python3.10+ and python3-venv are prerequisites')
    root=root.resolve(strict=True);prefix=safe_path(prefix);data=safe_path(data)
    if type(port) is not int or not 1024<=port<=65535:raise ValueError('Use an unprivileged loopback port')
    manifest,digest=verify_bundle(root)
    for path in (prefix,prefix/'lib',prefix/'share',prefix/'bin',prefix/'lib/microblocks',
                 prefix/'lib/microblocks-python',prefix/'lib/microblocks-installer',prefix/'share/microblocks-editor',data):
        if path.is_symlink():raise ValueError('Managed destination cannot be a symlink')
        if path.exists() and (not path.is_dir() or path.stat().st_uid!=os.geteuid()):raise ValueError('Managed directories must belong to the installing user')
    if data.exists():owned_private_directory(data)
    unit=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'systemd/user/microblocks-smallvm.service'
    if unit.exists() or unit.is_symlink():
        if unit.is_symlink() or '# microblocks-prefix='+str(prefix) not in unit.read_text().splitlines():raise ValueError('Existing unrelated service retained; select its owning install first')
    else:
        check_loopback_port(port)
    helper=prefix/'bin/microblocks-uninstall';marker='# microblocks-session-uninstaller-v1'
    if helper.is_symlink() or (helper.exists() and marker not in helper.read_text().splitlines()):raise ValueError('Unrelated uninstall helper retained')
    subprocess.run(['systemctl','--user','show-environment'],check=True,capture_output=True)
    # Check venv support before changing an install. Dependencies come only from
    # the authenticated bundle, never a moving package index.
    import ensurepip,venv
    startup=boot_startup(login_only)
    wheel=json.loads((root/'dependencies/linux-bridge.json').read_text())
    environment=prefix/'lib/microblocks-python'/wheel['sha256']
    if environment.is_symlink():raise ValueError('Refusing a symlink Python environment')
    interpreter=environment/'bin/python'
    if environment.exists():
        if not (environment/'.microblocks-wheel').is_file() or (environment/'.microblocks-wheel').read_text()!=wheel['sha256']:raise ValueError('Unmanaged Python environment retained')
    else:
        environment.mkdir(parents=True,mode=0o700)
        try:
            venv.EnvBuilder(with_pip=True).create(environment)
            subprocess.run([str(interpreter),'-m','pip','install','--no-index','--no-deps','--disable-pip-version-check',str(root/'wheels'/wheel['filename'])],check=True)
            (environment/'.microblocks-wheel').write_text(wheel['sha256'])
        except BaseException:
            shutil.rmtree(environment);raise
    subprocess.run([str(interpreter),'-c','import websockets; assert websockets.__version__ == "15.0.1"'],check=True)
    editor=prefix/'share/microblocks-editor'/manifest['editor_sha256']
    copy_immutable(root/'editor',editor)
    tools=prefix/'lib/microblocks-installer'/digest
    copy_immutable(root/'scripts',tools)
    component=manifest['binary']
    binary_install=subprocess.run(['bash',str(tools/'install-smallvm-linux-arm64.sh'),'--version',component['version'],'--sha256',component['sha256'],
                    '--archive',str(root/'binary.tar.gz'),'--prefix',str(prefix),'--data-dir',str(data)],capture_output=True,text=True)
    if binary_install.returncode:raise RuntimeError('Binary installation failed: '+binary_install.stdout+binary_install.stderr)
    service_output=subprocess.check_output([str(interpreter),str(root/'linux/arm64/service.py'),'--prefix',str(prefix),'--data',str(data),
                                           '--editor',str(editor),'--python',str(interpreter),'--port',str(port)],text=True)
    report=json.loads(service_output)
    helper.write_text('#!/bin/sh\n'+marker+'\nexec bash '+shlex.quote(str(tools/'uninstall-smallvm-linux-arm64.sh'))+' --prefix '+shlex.quote(str(prefix))+'\n');helper.chmod(0o700)
    # SSH_CONNECTION provides the server address of this authenticated session.
    fields=os.environ.get('SSH_CONNECTION','').split();host=socket.gethostname()+'.local'
    if len(fields)==4:
        try:host=str(ipaddress.ip_address(fields[2]))
        except ValueError:pass
    username=pwd.getpwuid(os.geteuid()).pw_name
    forward=shlex.join(['ssh','-N','-L',f'127.0.0.1:{port}:127.0.0.1:{port}',username+'@'+host])
    report.update(startup=startup,ssh_forward_command=forward,editor_url=f'http://127.0.0.1:{port}/',uninstall_command=shlex.quote(str(helper)),
                  bundle_sha256=digest,program_directory=str(data),physical_robot=False)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prefix',type=Path,default=Path.home()/'.local')
    parser.add_argument('--data',type=Path,default=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'microblocks')
    parser.add_argument('--port',type=int,default=8876);parser.add_argument('--login-startup',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    try:
        result=install(Path(__file__).resolve().parents[2],args.prefix,args.data,args.port,args.login_startup)
        print('\nSmallVM and editor bridge are ready.\nOn this Pi: '+result['editor_url']+'\nFrom another computer, run: '+result['ssh_forward_command']+'\nThen open: '+result['editor_url']+'\nUninstall (keeps programs): '+result['uninstall_command'])
        print(json.dumps(result,sort_keys=True))
    except (ValueError,OSError,RuntimeError,ImportError,subprocess.SubprocessError) as error:raise SystemExit('Pi installation refused: '+str(error)+'\nPrerequisites:64-bit Pi5 OS, Python3.10+, python3-venv, systemd user manager, bash and coreutils.')
