#!/usr/bin/env python3
"""Bounded portable automation tests; no hardware, network or actuators."""
# SPDX-License-Identifier: MIT
import json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'build-artifacts/automation';out.mkdir(parents=True,exist_ok=True)
command=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'common/automation'),str(root/'common/automation/clock.c'),str(root/'common/automation/steps.c'),str(root/'tests/automation_test.c'),'-o',str(out/'test')]
subprocess.run(command,check=True)
r=subprocess.run([str(out/'test')],check=True,text=True,capture_output=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(r.stdout);report.update(sanitizers=['address','undefined'],physical_tested=False,command=['python3','tools/test_automation.py'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
