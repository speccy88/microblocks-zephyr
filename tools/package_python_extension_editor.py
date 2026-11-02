#!/usr/bin/env python3
"""Add shared domain blocks to a fresh copy of an existing Linux/Pi JS editor."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]


def package(source,output):
    source,output=Path(source),Path(output)
    if output.exists():raise ValueError('Choose a fresh Python editor output')
    if source.is_symlink() or not source.is_dir():raise ValueError('Expected an existing verified JS editor package')
    for p in source.rglob('*'):
        if p.is_symlink():raise ValueError('Editor package may not contain symlinks')
    mobile=(source/'mobile/index.html').is_file();folder=source/'mobile' if mobile else source
    if not (folder/'engine/mb-compiler.js').is_file():raise ValueError('Only a JavaScript editor package can host Python blocks')
    manifest=json.loads((folder/'source-manifest.json').read_text())
    for entry in manifest['files']:
        if entry['path'].startswith('engine/') and hashlib.sha256((folder/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Upstream JS engine changed')
    library=(ROOT/'linux/extensions/Python.ubl').read_text(encoding='utf-8')
    inference=(ROOT/'linux/extensions/Inference.ubl').read_text(encoding='utf-8')
    data={
        'python-library.js':('globalThis.MicroBlocksPythonLibrary='+json.dumps({'source':library,'inferenceSource':inference},ensure_ascii=False)+';\n').encode(),
        'python-blocks.js':(ROOT/'web/js-editor/python-blocks.js').read_bytes(),
        'Libraries/Linux/Python Extensions.ubl':library.encode(),
        'Libraries/Linux/Neural Inference.ubl':inference.encode(),
        'Examples/Python/SQLite readings.ubp':((ROOT/'linux/extensions/examples/sqlite.ubp').read_text(encoding='utf-8')+'\n'+library).encode(),
        'Examples/Python/Neural inference.ubp':((ROOT/'linux/extensions/examples/inference.ubp').read_text(encoding='utf-8')+'\n'+library+'\n'+inference).encode()}
    if any((folder/name).exists() for name in data):raise ValueError('Python overlay already exists')
    shutil.copytree(source,output);destination=output/'mobile' if mobile else output
    for name,raw in data.items():
        p=destination/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    for name in ('index.html','microblocks.html'):
        p=destination/name
        if not p.exists():continue
        html=p.read_text(encoding='utf-8')
        match=re.search(r'(<script id="mobile-load-config" type="application/json">)(.*?)(</script>)',html)
        if match:
            config=json.loads(match[2]);index=next(i for i,x in enumerate(config['scripts']) if x.get('src')=='ui/ide.js')
            config['scripts'][index:index]=[{'src':'python-library.js'},{'src':'python-blocks.js'}]
            html=html[:match.start(2)]+json.dumps(config,separators=(',',':')).replace('<','\\u003c')+html[match.end(2):]
        else:
            anchor='\t\t<!-- IDE -->\n\t\t<script type="text/javascript" src="ui/ide.js"></script>'
            if html.count(anchor)!=1:raise ValueError('Review changed JS editor startup')
            html=html.replace(anchor,'<script src="python-library.js"></script>\n<script src="python-blocks.js"></script>\n'+anchor)
        p.write_text(html,encoding='utf-8',newline='\n')
    if mobile:(output/'microblocks.html').write_bytes((destination/'index.html').read_bytes())
    index=destination/'files.txt';index.write_text('\n'.join(sorted(set(index.read_text().splitlines())|set(data)))+'\n',encoding='utf-8')
    # Preserve the existing updater/asset receipt contract on Pi and standalone
    # packages, with hashes of the final bytes rather than the pre-overlay HTML.
    for name in ('pi-build-manifest.json','build-manifest.json'):
        receipt=output/name
        if not receipt.is_file():continue
        previous=json.loads(receipt.read_text(encoding='utf-8'))
        detailed=any(isinstance(v,dict) for v in previous.get('files',{}).values())
        previous['python_extensions']='configured-linux-v1'
        previous['files']={p.relative_to(output).as_posix():({'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} if detailed else hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(output.rglob('*')) if p.is_file() and p!=receipt and p.name!='python-extension-manifest.json'}
        receipt.write_text(json.dumps(previous,indent=2)+'\n',encoding='utf-8')
    # Include every output byte in an add-on receipt; never claim that the
    # original package's receipt still covers modified entry documents.
    result={'schema':1,'profile':'linux-python-extensions','upstream_engine_modified':False,'source_commit':manifest['source_commit'],
        'physical_hardware_validated':False,'files':{p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}}
    (output/'python-extension-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return {'profile':result['profile'],'files':len(result['files']),'mobile':mobile}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(package(a.source,a.output)))
