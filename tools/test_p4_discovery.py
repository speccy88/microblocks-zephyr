#!/usr/bin/env python3
"""Portable I2C registry/measurement fixtures under ASan/UBSan; no hardware."""
# SPDX-License-Identifier: MIT
import argparse,json,subprocess,tempfile
from pathlib import Path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);a=p.parse_args();root=Path(__file__).resolve().parents[1]
 with tempfile.TemporaryDirectory(prefix='i2c-discovery-') as work:
  binary=Path(work)/'discovery'
  subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined','-I'+str(root/'common/i2c'),str(root/'common/i2c/discovery.c'),str(root/'tests/p4_discovery_test.c'),'-o',str(binary)],check=True)
  result=json.loads(subprocess.check_output([str(binary)],text=True));print(json.dumps(result,indent=2))
  if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n',newline='\n')
