#!/usr/bin/env python3
"""Sanitized portable PCM ownership/format tests; no microphone access."""
# SPDX-License-Identifier: MIT
import argparse,json,subprocess,tempfile
from pathlib import Path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);a=p.parse_args()
 repo=Path(__file__).resolve().parents[1]
 with tempfile.TemporaryDirectory(prefix='p4-audio-') as work:
  binary=Path(work)/'audio'
  subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined',
   '-I'+str(repo/'common/audio'),'-I'+str(repo/'common/image'),str(repo/'common/audio/audio_store.c'),
   str(repo/'common/image/image_store.c'),str(repo/'tests/p4_audio_store_test.c'),'-o',str(binary)],check=True)
  result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
  report=json.loads(result.stdout);report['scope']='offline PCM store; no physical mic or speech claim'
  print(json.dumps(report,indent=2))
  if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
