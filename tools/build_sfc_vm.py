#!/usr/bin/env python3
"""Owned SmallVM host fixture + actual step C core; no production source edits."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,signal,subprocess,tempfile,time
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
assert not a.output.exists();sys_path=str(root/'linux/arm64')
import sys
sys.path.insert(0,sys_path);spec=importlib.util.spec_from_file_location('sfc_linux_build',root/'linux/arm64/build.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
report=build.prepare(a.upstream,a.output,sanitize=True)
header=a.output/'vm/interp.h';text=header.read_text();anchor='\tMicroDuckPrims,\n\tPrimitiveSetCount';assert text.count(anchor)==1
header.write_text(text.replace(anchor,'\tMicroDuckPrims,\n\tSFCReservedPrims,\n\tSFCTestPrims,\n\tPrimitiveSetCount'))
main=a.output/'platform/main.c';text=main.read_text();anchor='primsInit();addMicroduckPrims();';assert text.count(anchor)==1
main.write_text(text.replace(anchor,'primsInit();addMicroduckPrims();addSFCTestPrims();').replace('extern void vmSlice','extern void addSFCTestPrims(void);\nextern void vmSlice'))
for source,target in [(root/'tests/sfc_vm_steps.c',a.output/'sfc_vm_steps.c'),(root/'common/automation/steps.c',a.output/'steps.c'),(root/'common/automation/steps.h',a.output/'steps.h')]:shutil.copyfile(source,target)
shell=a.output/'build.sh';text=shell.read_text();assert text.count(' -lm -o smallvm')==1;shell.write_text(text.replace(' -lm -o smallvm',' sfc_vm_steps.c steps.c -lm -o smallvm'))
log=a.output/'compile.log';started=time.monotonic()
with log.open('w') as stream:
 child=subprocess.Popen(['sh',str(shell)],cwd=a.output,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
 try:code=child.wait(timeout=180)
 except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait();raise
assert code==0,log.read_text()[-4000:]
r=subprocess.run([str(a.output/'smallvm'),'--self-test'],capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stdout+r.stderr
report.update(binary_sha256=hashlib.sha256((a.output/'smallvm').read_bytes()).hexdigest(),build_host='WSL x86_64',hardware_access=False,production_VM_changed=False,fixture_step_set=24,
 compiler_seconds=round(time.monotonic()-started,3),host_only_changes={n:hashlib.sha256((a.output/n).read_bytes()).hexdigest() for n in ['vm/interp.h','platform/main.c','sfc_vm_steps.c','steps.c','steps.h','build.sh']},self_test=r.stdout,
 compile_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
(a.output/'sfc-build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['binary_sha256','compiler_seconds','fixture_step_set','hardware_access']},indent=2))
