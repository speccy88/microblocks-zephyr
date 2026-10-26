#!/usr/bin/env python3
"""Sanitized native RAM/session/codec tests; builds a synthetic stdio fixture."""
# SPDX-License-Identifier: MIT
import json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'build-artifacts/storage-dispatch';out.mkdir(parents=True,exist_ok=True)
base=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
 '-I'+str(root/'common/storage')]+[str(root/'common/storage'/name) for name in ['storage.c','dispatcher.c','wire.c']]
for test,name in [('storage_dispatch_test.c','test'),('storage_wire_host.c','wire-host')]:
 subprocess.run(base+[str(root/'tests'/test),'-o',str(out/name)],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,text=True,check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(r.stdout);report.update(sanitizers=['address','undefined'],physical_tested=False)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
