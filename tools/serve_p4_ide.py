#!/usr/bin/env python3
"""Real GP editor through COM5; loopback-only, one controller, no firewall edits."""
# SPDX-License-Identifier: MPL-2.0
import argparse,asyncio,mimetypes
from http import HTTPStatus
from pathlib import Path
from urllib.parse import unquote,urlsplit
from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.http11 import Response
from p4_serial import P4SerialVM
async def main(a):
 root=a.editor.resolve();owner=asyncio.Lock()
 def response(status,body,mime='text/plain'):
  return Response(status.value,status.phrase,Headers([('Content-Type',mime),('Content-Length',str(len(body))),('Cache-Control','no-store'),('Connection','close')]),body)
 def http(connection,request):
  path=unquote(urlsplit(request.path).path)
  if path=='/ws/vm':return None
  target=(root/('microblocks.html' if path=='/' else path.lstrip('/'))).resolve()
  if not target.is_relative_to(root) or not target.is_file():return response(HTTPStatus.NOT_FOUND,b'Not found')
  mime='application/wasm' if target.suffix=='.wasm' else mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
  return response(HTTPStatus.OK,target.read_bytes(),mime)
 async def bridge(ws):
  if ws.request.path!='/ws/vm' or owner.locked():await ws.close(1013,'COM5 controller unavailable');return
  async with owner:
   vm=None
   try:
    vm=P4SerialVM();vm.serial.timeout=0;await ws.send('ready');print('COM5 real VM connected',flush=True)
    async def receive():
     while True:
      n=vm.serial.in_waiting
      if n:
       data=vm.serial.read(min(n,2048))
       if data:await ws.send(data)
      else:await asyncio.sleep(.002)
    async def transmit():
     async for data in ws:
      if not isinstance(data,bytes) or len(data)>4096:await ws.close(1003,'Bounded binary VM messages required');return
      vm.send(data)
    tasks=[asyncio.create_task(receive()),asyncio.create_task(transmit())]
    _,waiting=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    for task in waiting:task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
   except Exception as e:print('COM5 bridge error:',type(e).__name__,str(e),flush=True);await ws.close(1011,'COM5 VM unavailable')
   finally:
    if vm:vm.close();print('COM5 closed',flush=True)
 async with serve(bridge,'127.0.0.1',a.http_port,process_request=http,origins=[f'http://127.0.0.1:{a.http_port}'],max_size=4096,max_queue=8,write_limit=8192,compression=None):
  print(f'Real P4 editor: http://127.0.0.1:{a.http_port}/?bridge=1',flush=True);await asyncio.Future()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--editor',type=Path,required=True);p.add_argument('--http-port',type=int,default=8874);a=p.parse_args();asyncio.run(main(a))
