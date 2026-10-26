#!/usr/bin/env python3
"""Test bounded RAM file operations without hardware, host file access or network."""
# SPDX-License-Identifier: MIT
import json, os, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/storage';out.mkdir(parents=True,exist_ok=True)
command=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror',
    '-fsanitize=address,undefined','-fno-omit-frame-pointer',
    '-I'+str(root/'common/storage'),str(root/'common/storage/storage.c'),
    str(root/'tests/storage_test.c'),'-o',str(out/'test')]
subprocess.run(command,check=True)
r=subprocess.run([str(out/'test')],check=True,capture_output=True,text=True,
    env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(r.stdout)
report.update(sanitizers=['address','undefined'],physical_tested=False,
    command=['python3','tools/test_storage.py'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
