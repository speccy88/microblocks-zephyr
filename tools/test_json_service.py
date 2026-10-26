#!/usr/bin/env python3
"""Build portable C tests with ASan/UBSan; no board or network access."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(output:Path):
 output.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'dependencies/json.json').read_text())
 for name,sha in manifest['files'].items():
  if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Changed JSON dependency: '+name)
 flags=['-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
        '-include',str(ROOT/'common/json/json_config.h'),'-I'+str(ROOT/'common/json'),'-I'+str(ROOT/'third_party/yyjson')]
 executable=output/'json-test'
 command=['gcc',*flags,*map(str,[ROOT/'common/json/json_service.c',ROOT/'third_party/yyjson/yyjson.c',ROOT/'tests/json_service_test.c']),'-o',str(executable)]
 subprocess.run(command,check=True)
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1')
 result=subprocess.run([str(executable)],check=True,env=env,text=True,capture_output=True)
 report=json.loads(result.stdout)
 report.update(scope='host portable core, no VM/hardware claim',dependency=manifest['commit'],sanitizers=['address','undefined'],
               command=command,physical_tested=False)
 (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'build-artifacts/json');a=p.parse_args();run(a.output)
