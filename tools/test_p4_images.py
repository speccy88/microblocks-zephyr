#!/usr/bin/env python3
"""Exercise the shared image engine with address/undefined-behavior sanitizers."""
# SPDX-License-Identifier: MIT
import argparse, json, subprocess, tempfile
from pathlib import Path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);a=p.parse_args()
 repo=Path(__file__).resolve().parents[1];core=repo/'common/image'
 with tempfile.TemporaryDirectory(prefix='p4-images-') as work:
  binary=Path(work)/'images'
  cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-I'+str(core),str(core/'image_store.c'),str(repo/'tests/p4_image_store_test.c'),'-Wl,--wrap=malloc','-o',str(binary)]
  subprocess.run(cmd,check=True);r=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
  report=json.loads(r.stdout);report['scope']='offline shared image engine; no camera/VM hardware claim'
  print(json.dumps(report,indent=2))
  if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
