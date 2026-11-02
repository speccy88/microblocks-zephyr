import hashlib,json,os,pathlib,signal,subprocess,time
from websockets.sync.client import connect

root=pathlib.Path('/home/fred/.local/share/microblocks-lan')
def state():return json.loads((root/'run/status.json').read_text())
def prop(name):return subprocess.check_output(['systemctl','show','microblocks-lan.service','-p',name,'--value'],text=True).strip()
def version():
    with connect('ws://192.168.1.105/ws/vm',origin='http://192.168.1.105',open_timeout=4) as socket:
        if socket.recv(timeout=3)!='ready':raise RuntimeError('Expected verified VM ready')
        socket.send(bytes([250,12,0]))
        result=b''
        for _ in range(5):
            value=socket.recv(timeout=3)
            if not isinstance(value,bytes):raise RuntimeError('Expected real binary VM reply')
            result+=value
            if b'v417 Linux ARM64' in result:return 417
        raise RuntimeError('Expected physical native version reply')
before=state();main=int(prop('MainPID'));pid=before['vm_pid']
binary=root/'releases/pi417-20261102/smallvm'
proc=pathlib.Path('/proc')/str(pid)
if main!=before['supervisor_pid'] or proc.stat().st_uid!=os.geteuid() or not (proc/'exe').samefile(binary):
    raise RuntimeError('Refuse to signal a process outside this owned service')
parent=next(line.split()[1] for line in (proc/'status').read_text().splitlines() if line.startswith('PPid:'))
if int(parent)!=main:raise RuntimeError('Owned VM parent changed')
program=root/'data/program.ucode'
digest=hashlib.sha256(program.read_bytes()).hexdigest()
initial_restarts=int(prop('NRestarts'));first=version();start=time.monotonic()
os.kill(pid,signal.SIGTERM)
deadline=start+25
while time.monotonic()<deadline:
    try:
        after=state()
        if after['state']=='ready' and after['supervisor_pid']!=main and int(prop('MainPID'))==after['supervisor_pid']:
            second=version();break
    except (OSError,ValueError,RuntimeError):pass
    time.sleep(.2)
else:raise RuntimeError('Owned service did not recover from its VM exit')
if hashlib.sha256(program.read_bytes()).hexdigest()!=digest:raise RuntimeError('Program persistence changed during restart')
print(json.dumps({'url':'http://192.168.1.105/','result':'PASS','vm_version_before':first,'vm_version_after':second,
    'old_supervisor_pid':main,'new_supervisor_pid':after['supervisor_pid'],'old_vm_pid':pid,'new_vm_pid':after['vm_pid'],
    'restart_count_before':initial_restarts,'restart_count_after':int(prop('NRestarts')),
    'recovery_seconds':round(time.monotonic()-start,3),'program_sha256_preserved':digest,
    'boot_enabled':prop('UnitFileState')=='enabled','os_rebooted':False}))
