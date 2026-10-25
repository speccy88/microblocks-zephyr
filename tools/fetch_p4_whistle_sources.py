#!/usr/bin/env python3
"""Fetch/verify pinned Apache-2.0 C99 Whistle source, never model weights."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,urllib.request
from pathlib import Path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 repo=Path(__file__).resolve().parents[1];manifest=json.loads((repo/'dependencies/p4-whistle.json').read_text())
 prefix=manifest['source_repository'].replace('https://github.com/','https://raw.githubusercontent.com/')+'/'+manifest['source_commit']+'/'
 for item in manifest['files']:
  name=Path(item['path'])
  if name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe source path')
  target=a.output/name
  raw=target.read_bytes() if target.exists() else urllib.request.urlopen(prefix+name.as_posix(),timeout=30).read()
  if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Whistle source hash differs: '+name.as_posix())
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
 print(json.dumps({'verified_files':len(manifest['files']),'source_commit':manifest['source_commit'],'model_weights_downloaded':False}))
