#!/usr/bin/env python3
"""Pack pinned genuine GP editor into a bounded P4 flash asset partition."""
# SPDX-License-Identifier: MPL-2.0
import argparse,gzip,hashlib,json,mimetypes,struct,tempfile,zlib
from pathlib import Path
from package_p4_ide import build
def package(source,output,repo):
 parent=(repo/'build-artifacts').resolve();parent.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='p4-hosted-package-',dir=parent) as name:
  folder=Path(name).resolve();assert folder.is_relative_to(parent)
  build(source,folder,repo,hosted=True)
  files=sorted(p for p in folder.rglob('*') if p.is_file());body=bytearray();entries=[]
  for path in files:
   rel=path.relative_to(folder).as_posix();raw=path.read_bytes()
   zipped=gzip.compress(raw,compresslevel=9,mtime=0);encoding='gzip' if len(zipped)<len(raw) else None;stored=zipped if encoding else raw
   if len(rel)>120 or any(x in rel for x in ['..','\\']):raise ValueError('Unsafe asset path')
   body.extend(b'\0'*(-len(body)%8));offset=64+len(body);body.extend(stored)
   mime=mimetypes.guess_type(rel)[0] or 'application/octet-stream'
   if rel.endswith('.js'):mime='text/javascript'
   if rel.endswith('.wasm'):mime='application/wasm'
   entries.append(dict(path=rel,offset=offset,bytes=len(raw),flash_bytes=len(stored),encoding=encoding,mime=mime,sha256=hashlib.sha256(raw).hexdigest()))
 header=struct.pack('<8sIIII32s8x',b'MBP4AS1\0',1,len(entries),len(body),zlib.crc32(body),hashlib.sha256(body).digest())
 blob=header+body
 if len(blob)>0x1000000:raise ValueError('Editor assets exceed reserved 16 MiB partition')
 output.mkdir(parents=True,exist_ok=True);(output/'assets.bin').write_bytes(blob)
 code=['/* Generated from pinned public editor assets; no credentials. */','#include "hosted_server.h"','#include <zephyr/net/http/service.h>',
  'const unsigned char p4_asset_header[64]={'+','.join(map(str,header))+'};',f'const unsigned p4_asset_total={len(blob)};']
 for i,e in enumerate(entries):
  code += [f'static const struct p4_asset asset_{i}={{{e["offset"]},{e["flash_bytes"]},{"true" if e["encoding"] else "false"}}};',
   f'static struct http_resource_detail_dynamic asset_detail_{i}={{',
   ' .common={.type=HTTP_RESOURCE_TYPE_DYNAMIC,.bitmask_of_supported_http_methods=BIT(HTTP_GET),',
   f' .content_type={json.dumps(e["mime"])},.content_encoding={json.dumps(e["encoding"]) if e["encoding"] else "NULL"}}},.cb=p4_asset_handler,.user_data=(void *)&asset_{i}}};',
   f'HTTP_RESOURCE_DEFINE(p4_resource_{i},p4_http,{json.dumps("/"+e["path"])},&asset_detail_{i});']
  if e['path']=='microblocks.html':code.append(f'HTTP_RESOURCE_DEFINE(p4_asset_root,p4_http,"/",&asset_detail_{i});')
 (output/'assets.c').write_text('\n'.join(code)+'\n',newline='\n')
 report=dict(board='ESP32-P4 WIFI6',offset='0xfe0000',partition_bytes=0x1000000,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),files=len(entries),assets=entries,credentials_included=False)
 (output/'assets-manifest.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
 return {k:v for k,v in report.items() if k!='assets'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ide-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(package(a.ide_source,a.output,Path(__file__).resolve().parents[1]),indent=2))
