#!/usr/bin/env python3
"""Install the reviewed foreground VM/loopback bridge as an opt-in user service.

Requires an existing guarded binary installation and explicit local editor/Python.
No download, dependency installation, network exposure or lingering change.
"""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import tempfile
import time

UNIT = 'microblocks-smallvm.service'
MARKER = '# microblocks-linux-arm64-v1'


def safe_path(path):
    text = str(path)
    if not path.is_absolute() or text == '/' or text.endswith(' ') or any(ord(c)<32 or ord(c)==127 or c in '$"%\\' for c in text):
        raise ValueError('Unsupported absolute path')
    return path


def unit_text(prefix, data, editor, python, runtime, binary, port):
    for path in (prefix,data,editor,python,runtime,binary):safe_path(path)
    if type(port) is not int or not 1024<=port<=65535:raise ValueError('Use an unprivileged loopback port')
    args=[python,runtime/'session.py','--binary',binary,'--editor',editor,'--data',data,'--resume','--port',str(port),'--service-managed']
    return (MARKER+'\n# microblocks-prefix='+str(prefix)+'\n[Unit]\nDescription=MicroBlocks VM and local editor bridge\n'
            '[Service]\nExecStart='+' '.join('"'+str(a)+'"' for a in args)+'\nWorkingDirectory='+str(data)+'\n'
            'Restart=on-failure\nRestartSec=3\nKillMode=control-group\nNoNewPrivileges=true\nPrivateTmp=true\n'
            'ProtectSystem=strict\nReadWritePaths="'+str(data)+'"\n[Install]\nWantedBy=default.target\n')


def owned_private_directory(path):
    meta=path.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid!=os.geteuid() or meta.st_mode&0o077:
        raise ValueError('Data must be a private owned directory, not a symlink')


def check_loopback_port(port):
    # Match asyncio's listener policy: TIME_WAIT from the previous owned bridge
    # is reusable; a live listener still prevents binding this exact endpoint.
    with socket.socket() as available:
        available.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        available.bind(('127.0.0.1',port))


def wait_ready(data, port, timeout=20):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=subprocess.run(['systemctl','--user','show',UNIT,'-p','MainPID','--value'],capture_output=True,text=True,timeout=5)
        try:
            pid=int(result.stdout.strip());path=data/'session.json';meta=path.lstat()
            if stat.S_ISREG(meta.st_mode) and meta.st_uid==os.geteuid() and not meta.st_mode&0o077:
                value=json.loads(path.read_text())
                if (pid>0 and value.get('supervisor_pid')==pid and value.get('state')=='ready'
                    and value.get('service_installed') is True and value.get('bind')=='127.0.0.1' and value.get('port')==port):
                    return value
        except (ValueError,OSError):pass
        time.sleep(.1)
    raise RuntimeError('Service has not published matching ready state; inspect its journal and session logs')


def install(prefix, data, editor, python, port, *, unit_dir=None):
    if os.geteuid()==0:raise ValueError('Use the intended unprivileged account')
    prefix,data,editor,python=map(safe_path,(prefix,data,editor,python))
    owned_private_directory(data)
    marker=prefix/'lib/microblocks/INSTALLATION'
    if marker.is_symlink() or marker.read_text().strip()!='microblocks-linux-arm64-v1':raise ValueError('No guarded binary installation')
    launcher=prefix/'bin/smallvm'
    if launcher.is_symlink() or MARKER not in launcher.read_text().splitlines():raise ValueError('Unrecognized binary launcher')
    # Read the exact executable via the generated launcher's pinned release;
    # never execute or parse arbitrary shell syntax to discover its target.
    import shlex
    commands=[shlex.split(line) for line in launcher.read_text().splitlines() if line.startswith('exec ')]
    if len(commands)!=1 or len(commands[0])<2:raise ValueError('Unrecognized launcher layout')
    binary=safe_path(Path(commands[0][1]))
    release=binary.parent
    if release.parent!=prefix/'lib/microblocks' or binary.name!='smallvm' or binary.is_symlink():raise ValueError('Executable outside versioned install')
    metadata=json.loads((release/'manifest.json').read_text())
    if metadata.get('source_commit')!='2071df569623ba9cdcd6f8106b61796e047df38b' or metadata.get('architecture')!='linux-aarch64':raise ValueError('Unreviewed executable provenance')
    raw=binary.read_bytes()
    if len(raw)<64 or raw[:6]!=b'\x7fELF\x02\x01' or struct.unpack_from('<H',raw,18)[0]!=183:raise ValueError('Installed binary is not ELF64 AArch64')
    if metadata.get('binary_sha256')!=hashlib.sha256(raw).hexdigest():raise ValueError('Installed executable hash mismatch')
    for name in ('microblocks.html','source-manifest.json'):
        if not (editor/name).is_file() or (editor/name).is_symlink():raise ValueError('Explicit packaged JS editor required')
    if json.loads((editor/'source-manifest.json').read_text()).get('source_commit')!='5564b1e42d6790360450ebf11c9eb33a1c6877f2':raise ValueError('Unreviewed editor source')
    dependency=subprocess.run([str(python),'-c','import websockets; assert websockets.__version__ == "15.0.1"'],capture_output=True,text=True,timeout=10)
    if dependency.returncode:raise ValueError('Selected Python must provide websockets15.0.1')
    sources={name:Path(__file__).with_name(name).read_bytes() for name in ('session.py','bridge.py')}
    digest=hashlib.sha256(b''.join(name.encode()+b'\0'+sources[name] for name in sorted(sources))).hexdigest()
    runtime=prefix/'lib/microblocks-session'/digest
    text=unit_text(prefix,data,editor,python,runtime,binary,port)
    directory=unit_dir or Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'systemd/user'
    safe_path(directory);unit=directory/UNIT
    for managed in (directory,prefix/'lib/microblocks-session'):
        if managed.is_symlink():raise ValueError('Refusing a symlink managed destination')
    if unit.is_symlink():raise ValueError('Refusing a symlink user unit')
    if unit.exists():
        old=unit.read_text()
        if MARKER not in old.splitlines() or '# microblocks-prefix='+str(prefix) not in old.splitlines():raise ValueError('Foreign user unit retained')
        state=subprocess.run(['systemctl','--user','is-active','--quiet',UNIT]).returncode
        if state==0 and old!=text:raise ValueError('Stop the owned unit explicitly before changing its session configuration')
        if state==0:
            return {'unit':str(unit),'unchanged':True,'port':port,'runtime_sha256':digest,'session':wait_ready(data,port)}
    subprocess.run(['systemctl','--user','show-environment'],check=True,capture_output=True,timeout=10)
    check_loopback_port(port)
    if runtime.is_symlink():raise ValueError('Refusing a symlink runtime')
    if runtime.exists():
        for name,raw in sources.items():
            if (runtime/name).is_symlink() or (runtime/name).read_bytes()!=raw:raise ValueError('Existing immutable runtime differs')
    else:
        runtime.parent.mkdir(parents=True,exist_ok=True)
        staged=Path(tempfile.mkdtemp(prefix='.session-',dir=runtime.parent))
        try:
            for name,raw in sources.items():(staged/name).write_bytes(raw)
            os.rename(staged,runtime)
        finally:
            if staged.exists():shutil.rmtree(staged)
    directory.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.microblocks-session-',dir=directory)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(text);stream.flush();os.fsync(stream.fileno())
        # Verify the actual unit syntax before publishing to the user manager.
        verify=Path(name+'.service');os.rename(name,verify)
        try:
            # Unit basename is needed for WantedBy verification; use a staging directory.
            with tempfile.TemporaryDirectory(prefix='microblocks-unit-') as test:
                candidate=Path(test)/UNIT;candidate.write_text(text)
                subprocess.run(['systemd-analyze','--user','verify',str(candidate)],check=True,capture_output=True,timeout=10)
            os.replace(verify,unit)
        finally:
            if verify.exists():verify.unlink()
    finally:
        if Path(name).exists():Path(name).unlink()
    for args in (['daemon-reload'],['enable','--now',UNIT],['is-active','--quiet',UNIT]):
        subprocess.run(['systemctl','--user',*args],check=True,timeout=15)
    return {'unit':str(unit),'unchanged':False,'bind':'127.0.0.1','port':port,'runtime_sha256':digest,
            'data':str(data),'binary':str(binary),'lingering_changed':False,'session':wait_ready(data,port),
            'editor_url':f'http://127.0.0.1:{port}/','connection':'Use the same loopback port through SSH on another computer'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prefix','data','editor','python'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--port',type=int,default=8876);a=p.parse_args()
    try:print(json.dumps(install(a.prefix,a.data,a.editor,a.python,a.port)))
    except (ValueError,OSError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('Session service refused: '+str(error))
