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
from pose_eyes import PoseProducer,DEFAULT_MODEL
from pose_tracker import Sample,FrameMux
from pose_camera_rpc import AsyncCameraRPC,P4PoseProducer,FrameReader
from face_tracker import demo_samples,DEFAULT_FACE_MODEL
import time
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
   vm=None;producer=None;camera_rpc=None;p4_producer=None;tasks=[];pose_task=None
   try:
    vm=P4SerialVM(baudrate=a.baud);vm.serial.timeout=0;mux=FrameMux(vm.send);await ws.send('ready');print(f'COM5 real VM connected at {vm.link_baud} baud'+(' (baseline fallback: '+vm.link_fallback+')' if vm.link_fallback else ''),flush=True)
    if a.pose_source=='p4':
     camera_rpc=AsyncCameraRPC(mux.inject);p4_producer=P4PoseProducer(camera_rpc,a.pose_model,a.pose_mirror,a.tracking_mode,a.face_model)
     print('P4 camera companion ready; capture stays off until the pose-camera block is enabled',flush=True)
    elif a.pose_source=='demo':
     print('SIMULATED face/person demo; no camera or neural model is used',flush=True)
    elif a.pose_source is not None:
     producer=PoseProducer(a.pose_source,a.pose_model,a.pose_mirror);producer.start()
     print('Local YOLO companion explicitly enabled; camera starts for this editor connection',flush=True)
    async def receive():
     frames=FrameReader()
     while True:
      if not mux.pending:vm.keep_link_alive()
      n=vm.serial.in_waiting
      if n:
       data=vm.serial.read(min(n,2048))
       if data:
        if camera_rpc:
         for frame in frames.feed(data):
          if frame[:2]==bytes((251,211)):camera_rpc.accept(frame)
          else:await ws.send(frame)
        else:await ws.send(data)
      else:await asyncio.sleep(.002)
    async def transmit():
     async for data in ws:
      if not isinstance(data,bytes) or len(data)>4096:await ws.close(1003,'Bounded binary VM messages required');return
      mux.feed(data)
    async def poses():
     sequence=0
     while True:
      value=producer.take()
      if value:
       captured,sample=value
       if time.monotonic()-captured>1:sample=Sample()
       sequence+=1;mux.inject(sample.packet(sequence))
      if producer.error:
       print('Local pose error: '+producer.error,flush=True)
       return
      if producer.thread is not None and not producer.thread.is_alive():return
      await asyncio.sleep(.10)
    async def demo():
     began=time.monotonic();sequence=0
     while True:
      face,person=demo_samples(time.monotonic()-began);sequence+=1
      mux.inject(person.packet(sequence));mux.inject(face.packet(sequence))
      await asyncio.sleep(.10)
    tasks=[asyncio.create_task(receive()),asyncio.create_task(transmit())]
    # YOLO completion/failure must not close the editor. Receiver TTL clears it.
    pose_task=asyncio.create_task(p4_producer.run(mux.inject)) if p4_producer else (asyncio.create_task(demo()) if a.pose_source=='demo' else (asyncio.create_task(poses()) if producer else None))
    if pose_task:
     def companion_done(task):
      if not task.cancelled() and task.exception():print('Local vision companion stopped: '+str(task.exception()),flush=True)
     pose_task.add_done_callback(companion_done)
    _,waiting=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    for task in waiting:task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
    if pose_task:pose_task.cancel();await asyncio.gather(pose_task,return_exceptions=True)
   except Exception as e:print('COM5 bridge error:',type(e).__name__,str(e),flush=True);await ws.close(1011,'COM5 VM unavailable')
   finally:
    for task in tasks:
     if not task.done():task.cancel()
    if pose_task:pose_task.cancel()
    await asyncio.gather(*tasks,*([pose_task] if pose_task else []),return_exceptions=True)
    if producer:
     producer.stop.set()
     await asyncio.to_thread(producer.thread.join,2)
    if camera_rpc:camera_rpc.close()
    if vm:vm.close();print('COM5 closed',flush=True)
 async with serve(bridge,'127.0.0.1',a.http_port,process_request=http,origins=[f'http://127.0.0.1:{a.http_port}'],max_size=4096,max_queue=8,write_limit=8192,compression=None):
  print(f'Real P4 editor: http://127.0.0.1:{a.http_port}/?bridge=1',flush=True);await asyncio.Future()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--editor',type=Path,required=True);p.add_argument('--http-port',type=int,default=8874)
 p.add_argument('--pose-source',help='p4 attached camera, demo (SIMULATED, no camera), or optional webcam number/local video; omitted means camera off')
 p.add_argument('--pose-model',default=DEFAULT_MODEL);p.add_argument('--pose-mirror',action='store_true')
 p.add_argument('--tracking-mode',choices=['pose','face','both'],default='both',help='P4 source only: face engagement, arm pose, or both')
 p.add_argument('--face-model',default=DEFAULT_FACE_MODEL)
 p.add_argument('--baud',type=int,choices=[115200,460800,921600],default=921600,help='Negotiate a leased fast serial rate; unsupported firmware stays at 115200')
 a=p.parse_args();asyncio.run(main(a))
