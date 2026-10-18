#!/usr/bin/env python3
"""Serve the pinned real GP MicroBlocks IDE with a local Fruit Jam USB bridge.

Listens on loopback only, checks WebSocket origin and USB identity, permits
one controller, bounds messages, and never flashes firmware or accesses I2C.
Needs pyserial and websockets (the session's existing tooling provides both).
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,asyncio,hashlib,json,mimetypes,re
from http import HTTPStatus
from pathlib import Path
from urllib.parse import unquote,urlsplit
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response
from fruit_jam_serial import SerialVM
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


async def main(args):
    repo=Path(__file__).resolve().parents[1]
    source=args.ide_source.resolve()
    assets=prepare_assets(repo,source)
    owner=asyncio.Lock()
    origins=[f'http://127.0.0.1:{args.http_port}',f'http://localhost:{args.http_port}']
    def response(status,body,mime='text/plain; charset=utf-8'):
        return Response(status.value,status.phrase,Headers([
            ('Content-Type',mime),('Content-Length',str(len(body))),
            ('Cache-Control','no-store'),('Connection','close')]),body)
    def http(connection,request):
        path=unquote(urlsplit(request.path).path)
        if path=='/ws/vm':return None
        name='microblocks.html' if path=='/' else path.lstrip('/')
        if name in assets:raw=assets[name]
        else:
            target=(source/name).resolve()
            if not target.is_relative_to(source) or not target.is_file():
                return response(HTTPStatus.NOT_FOUND,b'Not found')
            raw=target.read_bytes()
        mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
        if name.endswith('.wasm'):mime='application/wasm'
        return response(HTTPStatus.OK,raw,mime)
    async def bridge(ws):
        if ws.request.path!='/ws/vm':
            await ws.close(1008,'Unknown endpoint');return
        if owner.locked():
            await ws.close(1013,'Fruit Jam already has a controller');return
        async with owner:
            vm=None
            try:
                vm=SerialVM(args.port)
                if vm.identity['serial']!='E46570978F1E5A34':raise RuntimeError('Unexpected USB identity')
                vm.serial.timeout=0
                await ws.send('ready')
                async def usb_to_ws():
                    while True:
                        count=vm.serial.in_waiting
                        if count:
                            raw=vm.serial.read(min(count,2048))
                            if raw:await ws.send(raw)
                        else:await asyncio.sleep(.003)
                async def ws_to_usb():
                    async for data in ws:
                        if not isinstance(data,bytes) or len(data)>4096:
                            await ws.close(1003,'Bounded binary data required');return
                        vm.send(data)
                tasks=[asyncio.create_task(usb_to_ws()),asyncio.create_task(ws_to_usb())]
                _,pending=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
                for task in pending:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
            except Exception as exc:
                print('USB bridge closed:',type(exc).__name__,str(exc),flush=True)
                await ws.close(1011,'Fruit Jam USB unavailable')
            finally:
                if vm:vm.close()
    async with serve(bridge,'127.0.0.1',args.http_port,process_request=http,
                     origins=origins,max_size=4096,max_queue=8,write_limit=8192,compression=None):
        print(f'Fruit Jam IDE: http://127.0.0.1:{args.http_port}/',flush=True)
        await asyncio.Future()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ide-source',type=Path,required=True)
    parser.add_argument('--port',default='COM8')
    parser.add_argument('--http-port',type=int,default=8768)
    asyncio.run(main(parser.parse_args()))
