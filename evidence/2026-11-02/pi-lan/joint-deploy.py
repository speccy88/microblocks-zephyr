#!/usr/bin/env python3
"""Reviewed one-off joint Pi deployment. Requires explicit transfer approval.

Prepare an immutable release, then activate only the existing owned unit.
Never edits Caddy, router, firewall or the base service unit. No extra listener.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request

ROOT=Path('/home/fred/.local/share/microblocks-lan')
SOURCE=Path('/home/fred/mb-python-udufkoyi')
RELEASE=ROOT/'releases/pi417-python-548fea9'
UNIT='microblocks-lan.service'
DROPIN=Path('/etc/systemd/system/microblocks-lan.service.d/20-joint-runtime.conf')
BASE_SHA='b2061fb1b33b8ab49f772b452accb3f68ad8b33cc4f0d6c4006d41c3c1614ed8'
OVERLAY_SHA='08e596c2711bf3cafe75eeb7543ee6d3c62fd991649fb857f4e3616f65718efa'
NATIVE_SHA='25834bf64c9ed7d24826276e0c6e70e70e4a34190399ff071d6391361e012660'
BINARY_SHA='d60102ce79a73f79ee63d094e79c0803e64fdfb8cb4949a688639e9e89d09a2b'
OLD_BINARY_SHA='37dd525050936cf47b36bcb00f89b03514c153284d229fd7970c1d186956bcb5'
CODE=RELEASE/'code/linux/arm64'
BACKUP=ROOT/'backups/joint-548fea9'
PYTHON='/home/fred/microblocks-charlie/bridge-venv/bin/python'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def check(value,message):
    if not value:raise RuntimeError(message)
def command(*args):return subprocess.check_output(args,text=True).strip()
def sudo(*args):subprocess.run(['sudo','-n',*args],check=True,timeout=35)
def atomic(path,value):
    temporary=path.with_name('.'+path.name+'-joint')
    check(not temporary.exists(),'Unexpected transaction file')
    with temporary.open('x') as out:
        json.dump(value,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
    os.replace(temporary,path)
def private(path):
    m=path.lstat()
    check(stat.S_ISDIR(m.st_mode) and m.st_uid==os.geteuid() and not m.st_mode&0o077,'Private owned directory required')
def config():return json.loads((ROOT/'service.json').read_text())
def managed_state():return json.loads((ROOT/'run/status.json').read_text())
def dropin_text():
    return '[Service]\nExecStart=\nExecStart='+PYTHON+' -B '+str(CODE/'lan_service.py')+' --root '+str(ROOT)+'\n'
def ready(expected,timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            state=managed_state()
            if state['state']=='ready' and state['binary_sha256']==expected and int(command('systemctl','show',UNIT,'-p','MainPID','--value'))==state['supervisor_pid']:
                with urllib.request.urlopen('http://192.168.1.105/',timeout=2) as reply:
                    if reply.status==200:return state
        except (OSError,ValueError,KeyError):pass
        time.sleep(.2)
    raise RuntimeError('Owned service did not reach the expected HTTP/VM readiness')
def preserve_program():
    data=ROOT/'data'
    for path in data.rglob('*'):
        meta=path.lstat()
        check((stat.S_ISREG(meta.st_mode) or stat.S_ISDIR(meta.st_mode)) and meta.st_uid==os.geteuid(),'Unexpected program entry; preserve it without deployment')
    shutil.copytree(data,BACKUP/'data')
    program=data/'program.ucode'
    return sha(program) if program.exists() else None
def restore_program():
    saved=BACKUP/'data/program.ucode';target=ROOT/'data/program.ucode'
    if saved.exists():
        temporary=target.with_name('.program-joint-restore.ucode')
        check(not temporary.exists(),'Unexpected program restoration file')
        shutil.copy2(saved,temporary);os.replace(temporary,target)

def prepare():
    private(ROOT);private(SOURCE)
    old=config()
    check(old['origin']=='http://192.168.1.105' and old['backend_port']==8877 and old['data']=='data','Preserve the reviewed endpoint/data contract')
    check(old['binary_sha256']==OLD_BINARY_SHA and sha(ROOT/old['binary'])==OLD_BINARY_SHA,'Existing runtime changed; review it')
    check('python_extensions' not in old and not old.get('microduck_socket'),'Existing integration needs a new coordinated plan')
    check(not (ROOT/'updates/pending.json').exists(),'Finish or recover the existing update first')
    check(command('systemctl','show',UNIT,'-p','DropInPaths','--value')=='','Review existing service drop-ins')
    check(not RELEASE.exists() and not BACKUP.exists() and not DROPIN.exists(),'Do not overwrite an existing deployment')
    base=SOURCE/'python-pi-final-548fea9.tar.gz';overlay=SOURCE/'joint-overlay-review-08e596c2.tar.gz'
    native=SOURCE/'pi417-python-20261102.tar.gz'
    check(sha(base)==BASE_SHA and sha(overlay)==OVERLAY_SHA and sha(native)==NATIVE_SHA,'Reviewed input archive changed')
    RELEASE.mkdir(mode=0o700)
    with tarfile.open(base,'r:gz') as archive:
        receipt=json.loads(archive.extractfile('candidate.json').read())
        check(receipt['vm_source']=='2071df569623ba9cdcd6f8106b61796e047df38b','Unvalidated native source')
        check(receipt['js_source']=='5564b1e42d6790360450ebf11c9eb33a1c6877f2','Unreviewed editor source')
        seen=set();total=0
        for member in archive:
            name=Path(member.name)
            check(member.isfile() and not name.is_absolute() and '..' not in name.parts and member.name not in seen,'Unsafe source archive layout')
            check(member.size<=32*1024*1024,'Oversized source entry')
            seen.add(member.name);total+=member.size;check(total<=256*1024*1024,'Oversized expanded source archive')
            raw=archive.extractfile(member).read()
            if member.name!='candidate.json':
                expected=receipt['files'][member.name]
                if isinstance(expected,dict):expected=expected['sha256']
                check(hashlib.sha256(raw).hexdigest()==expected,'Source receipt mismatch')
            if name.parts[0] not in ('code','editor') and member.name!='candidate.json':continue
            target=RELEASE/name;target.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
            with target.open('xb') as out:out.write(raw)
        check(seen==set(receipt['files'])|{'candidate.json'},'Source receipt has missing or added entries')
    with tarfile.open(overlay,'r:gz') as archive:
        allowed={'overlay.json','code/linux/arm64/lan_service.py','code/linux/arm64/install-smallvm-linux-arm64.sh'}
        members=archive.getmembers();check({m.name for m in members}==allowed and len(members)==3 and all(m.isfile() for m in members),'Unexpected reviewed overlay')
        metadata=json.loads(archive.extractfile('overlay.json').read())
        check(metadata['base_sha256']==BASE_SHA,'Overlay base differs')
        for name,expected in metadata['overlay'].items():
            check(name in allowed and name!='overlay.json','Unexpected overlay target')
            raw=archive.extractfile(name).read();check(hashlib.sha256(raw).hexdigest()==expected,'Overlay checksum mismatch')
            (RELEASE/name).write_bytes(raw)
    sys.path.insert(0,str(CODE))
    from browser_update import review_archive
    reviewed=review_archive(native,NATIVE_SHA)
    check(reviewed['vm_version']==417 and reviewed['binary_sha256']==BINARY_SHA and 'python-extensions' in reviewed['capabilities'],'Unvalidated native candidate')
    subprocess.run(['bash',str(CODE/'install-smallvm-linux-arm64.sh'),'--version',reviewed['version'],'--sha256',NATIVE_SHA,'--archive',str(native),'--prefix',str(ROOT/'installed'),'--data-dir',str(ROOT/'data')],check=True,timeout=35)
    candidate=ROOT/'installed/lib/microblocks'/reviewed['version']/'smallvm'
    check(sha(candidate)==BINARY_SHA,'Installed candidate differs')
    profile=RELEASE/'python-profile.json';shutil.copy2(RELEASE/'code/linux/extensions/profiles/pi5.json',profile);profile.chmod(0o600)
    new=dict(old,binary=candidate.relative_to(ROOT).as_posix(),binary_sha256=BINARY_SHA,
        editor=(RELEASE/'editor').relative_to(ROOT).as_posix(),release_version=reviewed['version'],
        python_extensions={'profile':profile.relative_to(ROOT).as_posix(),'state':'python-state','interpreter':'/usr/bin/python3'},
        required_runtime_capabilities=['python-extensions'],allow_browser_native_install=True)
    atomic(RELEASE/'next-service.json',new)
    plan={'state':'prepared','baseline_config_sha256':sha(ROOT/'service.json'),'baseline_binary_sha256':OLD_BINARY_SHA,
        'base_unit_sha256':sha(Path('/etc/systemd/system')/UNIT),'caddy_sha256':sha('/etc/caddy/Caddyfile'),
        'source_sha256':BASE_SHA,'overlay_sha256':OVERLAY_SHA,'native_archive_sha256':NATIVE_SHA,'binary_sha256':BINARY_SHA,
        'release':str(RELEASE),'program_sha256_at_prepare':sha(ROOT/'data/program.ucode')}
    atomic(RELEASE/'deployment.json',plan)
    print(json.dumps(plan,indent=2))

def rollback():
    plan=json.loads((RELEASE/'deployment.json').read_text())
    check((BACKUP/'service.json').is_file(),'No owned deployment backup')
    if DROPIN.exists():check(DROPIN.read_text()==dropin_text(),'Refuse to remove a changed service override')
    sudo('systemctl','stop',UNIT)
    atomic(ROOT/'service.json',json.loads((BACKUP/'service.json').read_text()))
    restore_program()
    if DROPIN.exists():sudo('rm','--',str(DROPIN))
    sudo('systemctl','daemon-reload');sudo('systemctl','start',UNIT)
    state=ready(plan['baseline_binary_sha256'])
    plan['state']='rolled_back';plan['rollback_state']=state;atomic(RELEASE/'deployment.json',plan)
    print(json.dumps(plan,indent=2))

def activate():
    plan=json.loads((RELEASE/'deployment.json').read_text())
    check(plan['state']=='prepared' and sha(ROOT/'service.json')==plan['baseline_config_sha256'],'Review changed deployment baseline')
    check(not DROPIN.exists() and not BACKUP.exists(),'Do not replace another transaction')
    check(sha('/etc/caddy/Caddyfile')==plan['caddy_sha256'],'Caddy changed; preserve it and review')
    BACKUP.mkdir(parents=True,mode=0o700)
    shutil.copy2(ROOT/'service.json',BACKUP/'service.json')
    shutil.copy2(Path('/etc/systemd/system')/UNIT,BACKUP/'original-service-unit')
    sudo('systemctl','stop',UNIT)
    try:
        check(command('systemctl','show',UNIT,'-p','ActiveState','--value')=='inactive','Owned service did not stop')
        plan['preserved_program_sha256']=preserve_program()
        atomic(RELEASE/'deployment.json',plan)
        atomic(ROOT/'service.json',json.loads((RELEASE/'next-service.json').read_text()))
        source=RELEASE/'20-joint-runtime.conf';source.write_text(dropin_text())
        sudo('install','-d','-m','755',str(DROPIN.parent))
        sudo('install','-m','644',str(source),str(DROPIN))
        sudo('systemctl','daemon-reload');sudo('systemctl','start',UNIT)
        state=ready(BINARY_SHA)
        check(sha('/etc/caddy/Caddyfile')==plan['caddy_sha256'],'Caddy unexpectedly changed')
        check(sha(Path('/etc/systemd/system')/UNIT)==plan['base_unit_sha256'],'Original unit unexpectedly changed')
        check(sha(ROOT/'data/program.ucode')==plan['preserved_program_sha256'],'Program changed during activation')
        plan['state']='activated';plan['runtime_state']=state;atomic(RELEASE/'deployment.json',plan)
        print(json.dumps(plan,indent=2))
    except BaseException:
        rollback();raise

if __name__=='__main__':
    os.umask(0o077)
    check(os.geteuid()!=0,'Run as the existing ordinary service user')
    check(len(sys.argv)==2 and sys.argv[1] in ('prepare','activate','rollback'),'Choose an explicit deployment action')
    {'prepare':prepare,'activate':activate,'rollback':rollback}[sys.argv[1]]()
