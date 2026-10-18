"""Verified real GP editor patch and assets shared by USB and native hosting."""
# SPDX-License-Identifier: MPL-2.0
import hashlib,json,re
from patch_ide import patch_ide


def patch_package(javascript,data,library):
    javascript,data=patch_ide(javascript,data,library)
    source=javascript.decode('utf-8')
    match=re.search(r'loadPackage\((\{files:\[.*?\],remote_package_size:\d+\})\)',source)
    if not match: # patch_ide serializes quoted JSON keys.
        match=re.search(r'loadPackage\((\{"files":\[.*?\],"remote_package_size":\d+\})\)',source)
    metadata=json.loads(match[1])
    output=bytearray();entries=[]
    for item in metadata['files']:
        name=item['filename']
        payload=data[item['start']:item['end']]
        replacements=[(b"atPut primsets 'rlcd'",b"atPut primsets 'fruitJam'"),
            (b'rlcd.loadLibrary',b'fruitJam.loadLibrary'),(b'rlcd.openExample',b'fruitJam.openExample'),
            (b'Waveshare_RLCD_4_2.ubl',b'Fruit_Jam.ubl'),(b'Waveshare RLCD 4.2',b'Fruit Jam'),
            (b'Examples/Waveshare/',b'Examples/Fruit Jam/')]
        for before,after in replacements:payload=payload.replace(before,after)
        name=name.replace('Waveshare_RLCD_4_2.ubl','Fruit_Jam.ubl').replace('Examples/Waveshare/','Examples/Fruit Jam/')
        start=len(output);output.extend(payload)
        entries.append(dict(filename=name,start=start,end=len(output)))
    metadata=dict(files=entries,remote_package_size=len(output))
    source=source[:match.start(1)]+json.dumps(metadata,separators=(',',':'))+source[match.end(1):]
    source=source.replace('"/Examples","Waveshare"','"/Examples","Fruit Jam"')
    gate="""Module.preRun.push(function() {
 addRunDependency('board-english');
 Promise.resolve(GetText.ready).then(function(){removeRunDependency('board-english');},
 function(){Module.setStatus('Cannot load local language assets. Reload to retry.');});
});
"""
    return (gate+source).encode(),bytes(output)


def prepare_assets(repo,source):
    manifest=json.loads((repo/'dependencies/ide-assets.json').read_text())
    expected={item['path']:item['sha256'] for item in manifest['files']}
    originals={}
    for name in ('gp_wasm.js','gp_wasm.data','microblocks.html','gettext.js'):
        raw=(source/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected[name]:raise ValueError('IDE source changed: '+name)
        originals[name]=raw
    js,data=patch_package(originals['gp_wasm.js'],originals['gp_wasm.data'],
        (repo/'boards/adafruit_fruit_jam/integration/Fruit_Jam.ubl').read_bytes())
    html,count=re.subn(rb'(<script[^>]+src="gp_wasm\.js[^\"]*")',rb'\1 defer',originals['microblocks.html'])
    assert count==1
    hook=b"document.addEventListener('ready', () => { IDE.init(); });"
    assert html.count(hook)==1
    html=html.replace(hook,b"document.addEventListener('ready', () => { IDE.init(); document.dispatchEvent(new Event('board-ide-ready')); });")
    gettext=originals['gettext.js']
    for before,after in [(b"GetText.readLocale('en');",b"GetText.ready = GetText.readLocale('en');"),
        (b"\tfetch('translations/' + langcode + '.po')",b"\treturn fetch('translations/' + langcode + '.po')"),
        (b"GetText.setLocale = function (langcode) {",b"GetText.setLocale = function (langcode) {\n\tif (!langcode) { langcode = 'en'; }")]:
        assert gettext.count(before)==1
        gettext=gettext.replace(before,after)
    network=(repo/'web/board-network.js').read_text(encoding='utf-8')
    network=network.replace('Waveshare','Fruit Jam').replace('rlcd.','fruitJam.')
    network='\n'.join(line for line in network.splitlines() if "wifi=document.createElement('a')" not in line)+'\n'
    return {'gp_wasm.js':js,'gp_wasm.data':data,'microblocks.html':html,
            'gettext.js':gettext,'unoq-network.js':network.encode()}
