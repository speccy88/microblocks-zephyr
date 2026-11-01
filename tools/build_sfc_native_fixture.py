#!/usr/bin/env python3
"""Compile the actual step engine fixture under sanitizers; never opens hardware."""
from pathlib import Path
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/sfc-native';out.mkdir(parents=True,exist_ok=True)
sources=[root/'common/automation/steps.c',root/'tests/sfc_native_host.c']
binary=out/'host'
args=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
      '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie',
      '-I'+str(root/'common/automation'),*map(str,sources),'-o',str(binary)]
subprocess.run(args,check=True)
smoke='INIT 0\nADD 1 1\nADD 2 0\nEDGE 1 1 2 0\nSTART 0\nCOND 1 1\nSCAN 10\nSTOP\n'
r=subprocess.run([str(binary)],input=smoke,text=True,capture_output=True,check=True,
                 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'),timeout=5)
states=[json.loads(line) for line in r.stdout.splitlines()]
assert [s['active'] for s in states]==[1,2,0] and not r.stderr
report={'result':'PASS','binary':str(binary),'sources':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'sanitizers':['address','undefined'],'hardware_access':False,'smoke_states':states}
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
