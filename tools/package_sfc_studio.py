#!/usr/bin/env python3
"""Opt-in genuine GP editor + chart authoring; hardware connection is disabled."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,re
from pathlib import Path
from package_p4_ide import build as build_p4

MARKER='microblocks-sfc-offline-editor-v1\n'

def offline_adapter(raw):
    text=raw.decode('utf-8')
    old='XRP development preview: the production RP2350 library is available for editing. Hardware connection is not enabled yet.'
    if text.count(old)!=1:raise ValueError('Changed disconnected preview message')
    return text.replace(old,'SFC authoring preview: edit the chart and MicroBlocks project here. Hardware connection is disabled.').encode('utf-8')

def inject(assets,repo):
    html=assets['microblocks.html'].decode('utf-8')
    anchor='window.PORTAL_BOARD={board:"esp32p4",'
    if html.count(anchor)!=1:raise ValueError('Changed P4 preview profile anchor')
    html=html.replace(anchor,anchor+'connection_enabled:false,connection_message:"SFC authoring preview: hardware connection is disabled.",')
    html=html.replace('name:"Waveshare ESP32-P4 camera"','name:"MicroBlocks SFC authoring preview"')
    assets['sfc-library.js']=('/* Existing MicroBlocks library, preserved as data. */\nwindow.MicroBlocksSFCLibrary='+json.dumps((repo/'integration/Steps_Transitions.ubl').read_text(encoding='utf-8'),ensure_ascii=True)+';\n').encode('utf-8')
    for name in ['sfc-core.js','sfc-execution.js','sfc-export.js','sfc-studio.js','sfc-studio.css','sfc-view.css','sfc-actions.css']:
        assets[name]=(repo/'web/sfc'/name).read_bytes()
    tags=[]
    for name in ['sfc-studio.css','sfc-view.css','sfc-actions.css','sfc-core.js','sfc-execution.js','sfc-export.js','sfc-library.js','sfc-studio.js']:
        url=name+'?v='+hashlib.sha256(assets[name]).hexdigest()[:16]
        tags.append('<link rel="stylesheet" href="'+url+'">' if name.endswith('.css') else '<script src="'+url+'"></script>')
    if html.count('</head>')!=1:raise ValueError('Changed HTML head')
    html=html.replace('</head>','\n'.join(tags)+'\n</head>')
    assets['microblocks.html']=html.encode('utf-8');assets['index.html']=assets['microblocks.html']
    return assets

def build(source,output,repo):
    if output.is_symlink():raise ValueError('Output cannot be a symlink')
    source,output,repo=source.resolve(),output.resolve(),repo.resolve()
    if source==output or source.is_relative_to(output) or output.is_relative_to(source) or output==repo or repo.is_relative_to(output):
        raise ValueError('Source, repository and owned output must be separate')
    if output.exists() and any(output.iterdir()):
        marker=output/'.sfc-editor-build'
        if not marker.is_file() or marker.is_symlink() or marker.read_text(encoding='utf-8')!=MARKER:
            raise ValueError('Choose a new output or an owned SFC editor build')
    # Existing builder verifies every original GP asset before changing output.
    base=build_p4(source,output,repo)
    assets=inject({'microblocks.html':(output/'microblocks.html').read_bytes()},repo)
    assets['unoq-network.js']=offline_adapter((output/'unoq-network.js').read_bytes())
    for name in ['microblocks.html','index.html']:
        html=assets[name].decode('utf-8')
        html,count=re.subn(r'src="unoq-network.js(?:\?v=[^"]*)?"','src="unoq-network.js?v='+hashlib.sha256(assets['unoq-network.js']).hexdigest()[:16]+'"',html)
        if count!=1:raise ValueError('Changed adapter script reference')
        assets[name]=html.encode('utf-8')
    for name,raw in assets.items():(output/name).write_bytes(raw)
    (output/'.sfc-editor-build').write_text(MARKER,encoding='utf-8',newline='\n')
    report={'real_editor':'MicroBlocks GP 2.5.8','connection_enabled':False,
            'SFC_scope':'bounded execution-plan drafts, N/P1/P0/S/R logical requests, priority and export; no controller or hardware acceptance',
            'base_editor':base,'assets':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in assets.items()},
            'native_step_core_modified':False,'published':False}
    (output/'sfc-editor-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide-source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(build(args.ide_source,args.output,Path(__file__).resolve().parents[1]),indent=2))
