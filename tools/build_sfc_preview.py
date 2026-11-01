#!/usr/bin/env python3
"""Build a disconnected native GP SFC editor from hash-pinned original assets."""
# SPDX-License-Identifier: MPL-2.0
import argparse,hashlib,json,tempfile
from pathlib import Path
from package_pages import fetch
from package_sfc_studio import build as build_template
from package_sfc_native import build as build_native

def build(source,output,repo):
 source,output,repo=source.resolve(),output.resolve(),repo.resolve()
 if output.exists():raise ValueError('Choose a new SFC preview output directory')
 if source==output or source.is_relative_to(output) or output.is_relative_to(source):raise ValueError('Source and output must be separate')
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='sfc-template-',dir=output.parent) as temporary:
  template=Path(temporary)/'editor'
  build_template(source,template,repo)
  report=build_native(template,output,repo)
 upstream=json.loads((repo/'dependencies/ide-assets.json').read_text())
 extra={'LICENSES.md':(repo/'LICENSES.md').read_bytes(),
  'UPSTREAM.json':(json.dumps({'editor':'MicroBlocks GP 2.5.8','source_repository':upstream['source_repository'],
   'source_commit':upstream['source_commit'],'adapter_sources':['web/sfc-native.gp','web/sfc-branches.gp','web/sfc-live.gp','tools/patch_sfc_blocks.py','tools/sfc_branch_icons.py'],
   'hardware_connection_enabled':False},indent=2)+'\n').encode()}
 for name,raw in extra.items():
  (output/name).write_bytes(raw);report['files'][name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 report['source']=str(source)
 (output/'sfc-native-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
 return {'status':'PASS','files':len(report['files']),'connection_enabled':False,'output':str(output)}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ide-source',type=Path,default=Path('build-artifacts/ide-source'))
 p.add_argument('--output',type=Path,required=True);p.add_argument('--fetch',action='store_true');a=p.parse_args();repo=Path(__file__).resolve().parents[1]
 if a.fetch:fetch(a.ide_source,repo)
 print(json.dumps(build(a.ide_source,a.output,repo),indent=2))
