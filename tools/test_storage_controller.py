#!/usr/bin/env python3
"""Build actual storage VM bridge with pinned sender and synthetic I/O only."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import hashlib,json,os,subprocess
root=Path(__file__).resolve().parents[1];out=root/'build-artifacts/storage-controller';out.mkdir(parents=True,exist_ok=True)
source=root/'build-artifacts/p4-sources/smallvm'
manifest=json.loads((source/'provenance.json').read_text())
record=next(x for x in manifest['files'] if x['path']=='vm/runtime.c')
raw=(source/'vm/runtime.c').read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha256']
text=raw.decode()
def function(signature):
 start=text.index(signature+' {');end=text.index('\n}',start)+2
 return text[start:end]
sender=function('static void sendMessage(int msgType, int chunkIndex, int dataSize, char *data)')+'\n'+function('void waitAndSendMessage(int msgType, int chunkIndex, int dataSize, char *data)')+'\n'
(out/'vm_sender.inc').write_text(sender,newline='\n')
(out/'vm').mkdir(exist_ok=True)
(out/'vm/interp.h').write_text('int hasOutputSpace(int n);\nvoid waitAndSendMessage(int,int,int,char *);\n',newline='\n')
flags=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(out),'-I'+str(root/'common/storage')]
sources=[root/'common/storage'/name for name in ['storage.c','dispatcher.c','wire.c','controller.c','storage_protocol.c']]+[root/'tests/storage_vm_fakes.c']
for test,name in [('storage_controller_test.c','test'),('storage_application_host.c','application-host')]:
 subprocess.run(flags+list(map(str,sources))+[str(root/'tests'/test),'-o',str(out/name)],check=True)
run=subprocess.run([str(out/'test')],check=True,capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(run.stdout);report.update(sanitizers=['address','undefined'],runtime_sha256=record['sha256'],source_commit=manifest['canonical_commit'],sender_sha256=hashlib.sha256(sender.encode()).hexdigest())
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
