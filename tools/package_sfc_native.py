#!/usr/bin/env python3
"""Opt-in native GP SFC blocks; retains the normal editor and disables hardware."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
from pathlib import Path
import re
from patch_sfc_blocks import patch_package
from sfc_branch_icons import resources

CHART_ASSETS = {'sfc-core.js','sfc-execution.js','sfc-export.js','sfc-library.js',
                'sfc-studio.js','sfc-studio.css','sfc-view.css','sfc-actions.css'}


def native_html(raw):
    text=raw.decode('utf8')
    if text.count('connection_enabled:false') != 1:
        raise ValueError('Native SFC preview requires the disconnected editor profile')
    for name in sorted(CHART_ASSETS):
        pattern=r'<(?:script\s+src|link\s+rel="stylesheet"\s+href)="'+re.escape(name)+r'\?v=[0-9a-f]+"(?:></script>|>)'
        text,count=re.subn(pattern,'',text)
        if count != 1:raise ValueError('Changed chart asset tag: '+name)
    return text.replace('SFC authoring preview','Native SFC blocks preview').replace('MicroBlocks SFC authoring preview','MicroBlocks native SFC blocks').encode('utf8')


def build(source,output,repo):
    source,output,repo=source.resolve(),output.resolve(),repo.resolve()
    if output.exists():raise ValueError('Choose a new native SFC output directory')
    if source==output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Source and output must be separate')
    # Validate all transformations before creating the output.
    html=native_html((source/'microblocks.html').read_bytes())
    js,data=patch_package((source/'gp_wasm.js').read_bytes(),(source/'gp_wasm.data').read_bytes(),repo)
    assets={}
    for file in source.rglob('*'):
        if not file.is_file():continue
        name=file.relative_to(source).as_posix()
        if name in CHART_ASSETS|{'.sfc-editor-build','sfc-editor-manifest.json'}:continue
        assets[name]=file.read_bytes()
    assets.update({'gp_wasm.js':js,'gp_wasm.data':data,'microblocks.html':html,'index.html':html,
                   'sfc-native.ubp':(repo/'integration/sfc-native.ubp').read_bytes()})
    assets.update({name.lstrip('/'):raw for name,raw in resources(repo).items()})
    for example in (repo/'integration').glob('sfc-*.ubp'):
        assets['examples/'+example.name]=example.read_bytes()
    review=repo/'docs/SFC_BROWSER_REVIEW.md'
    if review.exists():assets['README_BROWSER.md']=review.read_bytes()
    network=assets['unoq-network.js']
    old=b'SFC authoring preview: edit the chart and MicroBlocks project here. Hardware connection is disabled.'
    if network.count(old)!=1:raise ValueError('Changed disconnected adapter message')
    assets['unoq-network.js']=network.replace(old,b'Native SFC blocks preview: edit the MicroBlocks project here. Hardware connection is disabled.')
    digest=hashlib.sha256(assets['unoq-network.js']).hexdigest()[:16]
    for name in ['microblocks.html','index.html']:
        text=assets[name].decode('utf8')
        text,count=re.subn(r'src="unoq-network.js\?v=[0-9a-f]+"','src="unoq-network.js?v='+digest+'"',text)
        if count!=1:raise ValueError('Changed adapter tag')
        assets[name]=text.encode('utf8')
    output.mkdir()
    for name,raw in assets.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    report={'scope':'genuine GP editor, native SFC sequence/step/transition and configurable OR/AND split/join blocks, setup/loop, live step color',
            'connection_enabled':False,'browser_opened':False,'hardware_access':False,'graph_UI_loaded':False,
            'source':str(source),'files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in sorted(assets.items())}}
    (output/'sfc-native-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor-base',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=build(args.editor_base,args.output,Path(__file__).resolve().parents[1])
    print(json.dumps({'status':'BUILT','files':len(result['files']),'connection_enabled':False}))
