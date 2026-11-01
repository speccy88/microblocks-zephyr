#!/usr/bin/env python3
"""Build new portable action kernel with the unchanged C step core; host only."""
from pathlib import Path
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/sfc-execution';out.mkdir(parents=True,exist_ok=True)
shared=[root/'common/automation/steps.c',root/'common/automation/sfc_actions.c']
flags=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
 '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie','-I'+str(root/'common/automation')]
commands=[]
for name,source in [('unit','sfc_actions_test.c'),('host','sfc_execution_host.c')]:
 argv=flags+list(map(str,shared+[root/'tests'/source]))+['-o',str(out/name)];commands.append(argv);subprocess.run(argv,check=True,timeout=120)
env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1')
r=subprocess.run([str(out/'unit')],text=True,capture_output=True,check=True,env=env,timeout=10);assert not r.stderr
smoke='INIT 0 3 1\nADD 1 1\nADD 2 0\nEDGE 1 1 2 0\nMAP 1 24\nBIND 1 1 3\nBIND 2 1 4\nSEAL\nSTART 0\nCOND 1 1\nSCAN 1\nRESET 2\nSTOP\n'
r2=subprocess.run([str(out/'host')],input=smoke,text=True,capture_output=True,check=True,env=env,timeout=10);assert not r2.stderr
states=[json.loads(l) for l in r2.stdout.splitlines()];assert [s['actions']['stored'] for s in states]==[1,0,1,0] and states[1]['fired']==1<<23
sources=shared+[root/'common/automation/sfc_actions.h',root/'common/automation/steps.h',root/'tests/sfc_actions_test.c',root/'tests/sfc_execution_host.c']
report={'result':'PASS','commands':commands,'unit':json.loads(r.stdout),'smoke_states':states,'sanitizers':['address','undefined'],
 'hardware_access':False,'sources':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
 'binaries':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ['unit','host']}}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
