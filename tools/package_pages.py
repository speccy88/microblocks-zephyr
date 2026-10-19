#!/usr/bin/env python3
"""Build the static two-board portal with the real, hash-pinned GP editor.

No credentials or hardware access. The original self-hosted asset packagers
are unchanged. --fetch downloads only manifest-listed immutable public files.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse, hashlib, json, re, shutil, urllib.request
from pathlib import Path
from fruit_jam_ide_assets import prepare_assets
from patch_ide import patch_ide

PROJECT_API = b"""} (endPoint == 'portal.serialize') {
        saveScripts scripter nil true
        respondAPIRequest this id (codeString (project scripter))
    } (endPoint == 'portal.load') {
        respondAPIRequest this id 0
        openProject editor (at params 1) (at params 2)
    """

def project_api(javascript, data):
    source=javascript.decode('utf-8')
    match=re.search(r'loadPackage\((\{"files":\[.*?\],"remote_package_size":\d+\})\)',source)
    if not match: raise ValueError('Unexpected patched package metadata')
    metadata=json.loads(match[1]); packed=bytearray(); entries=[]; changed=0
    anchor=b"} (endPoint == 'project.save') {"
    for item in metadata['files']:
        payload=data[item['start']:item['end']]
        if anchor in payload:
            assert payload.count(anchor)==1
            payload=payload.replace(anchor,PROJECT_API+anchor);changed+=1
        start=len(packed);packed.extend(payload)
        entries.append(dict(filename=item['filename'],start=start,end=len(packed)))
    assert changed==1
    replacement=json.dumps(dict(files=entries,remote_package_size=len(packed)),separators=(',',':'))
    return (source[:match.start(1)]+replacement+source[match.end(1):]).encode(),bytes(packed)

def xrp_package(javascript, data):
    """Select the authentic production XRP library, never the beta library.

    The editor remains usable offline; the portal separately disables hardware
    connection while the XRP SmallVM/transport implementation is incomplete.
    """
    source=javascript.decode('utf-8')
    match=re.search(r'loadPackage\((\{files:\[.*?\],remote_package_size:\d+\})\)',source)
    if not match:raise ValueError('Unexpected pinned XRP package metadata')
    metadata=json.loads(re.sub(r'([,{])(\w+):',r'\1"\2":',match[1]))
    packed=bytearray();entries=[];api_count=compiler_count=library_count=0
    for item in metadata['files']:
        start_offset,end_offset=int(item['start']),int(item['end'])
        if start_offset!=item['start'] or end_offset!=item['end'] or not 0<=start_offset<=end_offset<=len(data):
            raise ValueError('Invalid XRP package range')
        name=item['filename'];payload=data[start_offset:end_offset]
        if name=='/Libraries/Robots/XRP.ubl':
            assert hashlib.sha256(payload).hexdigest()=='c137323584dbe1401b24962eed68a6a5a168215c30094ecf9098430a4c48aa66'
            library_count+=1
        if b"atPut primsets 'unoq' (at primsets 'io')" in payload:
            payload=payload.replace(b"atPut primsets 'unoq' (at primsets 'io')",b"atPut primsets 'xrp' (at primsets 'io')")
            compiler_count+=1
        if b"endPoint == 'unoq.loadLibrary'" in payload:
            for before,after in [(b'Libraries/UNO_Q_Hardware.ubl',b'Libraries/Robots/XRP.ubl'),
                (b"'UNO Q Hardware'",b"'XRP'"),(b'unoq.loadLibrary',b'xrp.loadLibrary'),
                (b'unoq.openExample',b'xrp.openExample'),(b'Examples/UNO Q/',b'Examples/XRP/'),
                (b"'arithmetic' 'output' 'rgb' 'matrix' 'combined' 'matrix-drawing'",b"'arithmetic' 'output'")]:
                payload=payload.replace(before,after)
            api_count+=1
        if name.startswith('/Examples/UNO Q/'):
            if name.rsplit('/',1)[-1] not in ('arithmetic.ubp','output.ubp'):continue
            name=name.replace('/Examples/UNO Q/','/Examples/XRP/')
            if name.endswith('/output.ubp'):
                assert payload.count(b'repeat 500 {')==1
                payload=payload.replace(b'repeat 500 {',b'repeat 50 {')
        start=len(packed);packed.extend(payload)
        entries.append(dict(filename=name,start=start,end=len(packed)))
    assert (api_count,compiler_count,library_count)==(1,1,1)
    replacement=json.dumps(dict(files=entries,remote_package_size=len(packed)),separators=(',',':'))
    source=(source[:match.start(1)]+replacement+source[match.end(1):]).replace('"/Examples","UNO Q"','"/Examples","XRP"')
    return source.encode(),bytes(packed)

def build(source, output, repo):
    manifest=json.loads((repo/'dependencies/ide-assets.json').read_text(encoding='utf-8'))
    originals={}
    for item in manifest['files']:
        name=Path(item['path'])
        if name.is_absolute() or '..' in name.parts: raise ValueError('Unsafe manifest path')
        raw=(source/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']: raise ValueError('Source changed: '+str(name))
        originals[name.as_posix()]=raw
    output.mkdir(parents=True,exist_ok=True)
    marker=output/'.portal-build'
    if any(output.iterdir()) and not marker.exists(): raise ValueError('Output is not an owned portal build')
    marker.write_text('hash-pinned GP portal\n',encoding='utf-8',newline='\n')
    for path in (repo/'web/portal').rglob('*'):
        if path.is_file():
            target=output/path.relative_to(repo/'web/portal');target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,target)
    common=prepare_assets(repo,source)
    portal_version=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((repo/'web/portal').rglob('*')) if p.is_file())).hexdigest()[:16]
    root_html=(output/'index.html').read_text(encoding='utf-8')
    root_html=root_html.replace('href="portal.css"','href="portal.css?v='+portal_version+'"').replace('src="portal.js"','src="portal.js?v='+portal_version+'"')
    (output/'index.html').write_text(root_html,encoding='utf-8',newline='\n')
    report={'real_editor':'MicroBlocks GP 2.5.8','upstream_commit':manifest['source_commit'],
            'source_manifest_sha256':hashlib.sha256((repo/'dependencies/ide-assets.json').read_bytes()).hexdigest(),
            'runtime_third_party_network':False,'boards':{}}
    for board in ('fruit-jam','waveshare','xrp-rp2350'):
        assets=dict(originals);assets.update(common)
        if board in ('waveshare','xrp-rp2350'):
            if board=='waveshare':
                js,data=patch_ide(originals['gp_wasm.js'],originals['gp_wasm.data'],
                    (repo/'boards/waveshare_esp32s3_rlcd_4_2/integration/Waveshare_RLCD_4_2.ubl').read_bytes())
            else:js,data=xrp_package(originals['gp_wasm.js'],originals['gp_wasm.data'])
            # The same locale dependency used by the physically accepted hosts.
            gate=b"""Module.preRun.push(function() {
 addRunDependency('board-english');
 Promise.resolve(GetText.ready).then(function(){removeRunDependency('board-english');},
 function(){Module.setStatus('Cannot load local language assets. Reload to retry.');});
});
"""
            assets['gp_wasm.js']=gate+js;assets['gp_wasm.data']=data
        assets['gp_wasm.js'],assets['gp_wasm.data']=project_api(assets['gp_wasm.js'],assets['gp_wasm.data'])
        assets['unoq-network.js']=(repo/'web/portal/portal-adapter.js').read_bytes()
        html=assets['microblocks.html'].decode('utf-8')
        tag='<script src="unoq-network.js"></script>'
        assert html.count(tag)==1
        profile={'board':board,'name':{'fruit-jam':'Fruit Jam','waveshare':'Waveshare RLCD 4.2',
                  'xrp-rp2350':'SparkFun XRP RP2350 (development)'}[board]}
        if board=='xrp-rp2350':profile['connection_enabled']=False
        config=json.dumps(profile,separators=(',',':'))
        html=html.replace(tag,'<link rel="stylesheet" href="../../portal.css?v='+portal_version+'">\n'
            '<script>window.PORTAL_BOARD='+config+';</script>\n'
            '<script src="../../portal-core.js?v='+portal_version+'"></script>\n'
            '<script src="unoq-network.js?v='+portal_version+'"></script>')
        gp_version=hashlib.sha256(assets['gp_wasm.js']+assets['gp_wasm.data']).hexdigest()[:16]
        html=html.replace('26eb855451371f4c',gp_version)
        html=html.replace('<meta charset="utf-8">','<meta charset="utf-8">\n'
            '<meta name="referrer" content="no-referrer">\n'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'self\' data: blob:; '
            'connect-src \'self\' wss:; script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; '
            'style-src \'self\' \'unsafe-inline\'; object-src \'none\'; base-uri \'self\'">')
        assets['microblocks.html']=html.encode()
        folder=output/'editor'/board;folder.mkdir(parents=True,exist_ok=True)
        for name,raw in assets.items():
            target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        report['boards'][board]={'files':len(assets),'hardware_connection_enabled':board!='xrp-rp2350',
             'gp_data_sha256':hashlib.sha256(assets['gp_wasm.data']).hexdigest(),
             'gp_js_sha256':hashlib.sha256(assets['gp_wasm.js']).hexdigest(),'html_sha256':hashlib.sha256(assets['microblocks.html']).hexdigest()}
    for name in ('LICENSE','LICENSES.md'):
        shutil.copyfile(repo/name,output/name)
    shutil.copytree(repo/'licenses',output/'licenses',dirs_exist_ok=True)
    (output/'UPSTREAM.md').write_text('Real MicroBlocks GP editor 2.5.8, MPL-2.0.\n'
        'Pinned source and corresponding GP source are retained in the GP package.\n'
        f"Source: {manifest['source_repository']}/tree/{manifest['source_commit']}\n"
        'Original website code, mascot artwork and website fonts are not copied.\n'
        'See LICENSES.md and licenses/ for component notices.\n',encoding='utf-8',newline='\n')
    (output/'.nojekyll').write_text('',encoding='utf-8')
    (output/'build-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report

def fetch(source,repo):
    manifest=json.loads((repo/'dependencies/ide-assets.json').read_text(encoding='utf-8'))
    prefix=f"https://raw.githubusercontent.com/speccy88/uno-q-microblocks/{manifest['source_commit']}/{manifest['source_prefix']}"
    for item in manifest['files']:
        path=Path(item['path']);target=source/path
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe source path')
        raw=target.read_bytes() if target.exists() else urllib.request.urlopen(prefix+path.as_posix(),timeout=30).read()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Fetched source hash differs: '+str(path))
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide-source',required=True,type=Path);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--fetch',action='store_true');args=parser.parse_args();repo=Path(__file__).resolve().parents[1]
    if args.fetch:fetch(args.ide_source,repo)
    print(json.dumps(build(args.ide_source,args.output,repo),indent=2))
