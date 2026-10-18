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
from fruit_jam_ide_assets import patch_package, prepare_assets


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
