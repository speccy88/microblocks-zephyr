#!/usr/bin/env python3
"""Verify and compress the real Fruit Jam IDE into flash tables, without network."""
# SPDX-License-Identifier: MIT
import argparse,gzip,hashlib,json,mimetypes
from pathlib import Path
from fruit_jam_ide_assets import prepare_assets

def package(source,output,repo):
    manifest=json.loads((repo/'dependencies/ide-assets.json').read_text())
    output.mkdir(parents=True,exist_ok=True)
    patched=prepare_assets(repo,source)
    assembly=['.section .rodata.fruit_jam_web_assets,"a"']
    code=['#include "network_server.h"'];rows=[];audit=[]
    for i,item in enumerate(manifest['files']):
        name=item['path'];raw=(source/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('IDE source hash mismatch: '+name)
        raw=patched.get(name,raw);compressed=gzip.compress(raw,compresslevel=9,mtime=0)
        encoded=len(compressed)<len(raw);blob=compressed if encoded else raw
        path=output/f'asset-{i}.bin';path.write_bytes(blob);label=f'fj_asset_{i}'
        assembly.extend([f'.global {label}',f'{label}:',f'.incbin "{path.as_posix()}"'])
        code.append(f'extern const unsigned char {label}[];')
        mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
        if name.endswith('.wasm'):mime='application/wasm'
        if name.endswith('.js'):mime='text/javascript'
        rows.append('{'+','.join([json.dumps('/'+name),json.dumps(mime),label,str(len(blob)),'true' if encoded else 'false'])+'}')
        audit.append({'path':'/'+name,'encoding':'gzip' if encoded else '', 'content_type':mime,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'flash_bytes':len(blob),'flash_sha256':hashlib.sha256(blob).hexdigest()})
    code.extend(['const struct fj_web_asset fj_web_assets[]={',',\n'.join(rows),'};',f'const unsigned fj_web_asset_count={len(rows)};'])
    (output/'assets.c').write_text('\n'.join(code)+'\n')
    (output/'assets.S').write_text('\n'.join(assembly)+'\n')
    report={'files':len(rows),'flash_bytes':sum(x['flash_bytes'] for x in audit),'ide_version':'2.5.8','board':'Adafruit Fruit Jam','assets':audit}
    (output/'assets-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='assets'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();package(args.source.resolve(),args.output.resolve(),Path(__file__).resolve().parents[1])
