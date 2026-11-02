"""Camera protocol, fragmented shared transport and release/disabled behavior."""
# SPDX-License-Identifier: MIT
import asyncio
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pose_camera_rpc import request_packet,decode_reply,Reply,FrameReader,AsyncCameraRPC,capture_frame,P4PoseProducer


def response(request,operation=0,session=0,data=b'',state=0,status=0):
    body=struct.pack('<4sBBBBII',b'P4CP',1,operation,status,state,request,session)+data
    return bytes([251,211,0])+len(body).to_bytes(2,'little')+body


class PoseCameraWireTests(unittest.TestCase):
    def test_request_and_reply_contract(self):
        packet=request_packet(3,17,23,100,512)
        self.assertEqual(packet[:5],bytes([251,211,0,25,0]));self.assertEqual(packet[-1],254)
        self.assertEqual(struct.unpack('<4sBBHIIIHH',packet[5:-1]),(b'P4CP',1,3,0,17,23,100,512,0))
        reply=decode_reply(response(17,3,23,b'abc',2));self.assertEqual(reply.data,b'abc');self.assertEqual(reply.session,23)
        for args in [(5,1,2),(1,1,0),(3,1,2,10367,2),(3,1,2,0,513),(0,1,0,1,0)]:
            with self.assertRaises(ValueError):request_packet(*args)

    def test_fragmented_and_joined_frames(self):
        reader=FrameReader();frame=response(1,data=b'hello');out=[]
        for value in frame:out+=reader.feed(bytes([value]))
        self.assertEqual(out,[frame]);self.assertEqual(reader.feed(b'\xfa\x1a\x49'+frame),[b'\xfa\x1a\x49',frame])
        for data in [b'bad',b'\xfb\x01\x00\xff\xff',b'x'*16385]:
            with self.assertRaises(ValueError):FrameReader().feed(data)

    def test_bad_replies_are_rejected(self):
        for frame in [b'',response(1)[:-1],response(1,status=7),response(1,state=4),response(1,data=b'x'*513)]:
            with self.assertRaises(ValueError):decode_reply(frame)


class PoseCameraAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_correlation_and_close(self):
        sent=[];rpc=AsyncCameraRPC(lambda p:sent.append(p) or True)
        task=asyncio.create_task(rpc.request(2,17));await asyncio.sleep(0)
        request=struct.unpack_from('<I',sent[0],13)[0]
        rpc.accept(response(request,2,99));self.assertFalse(task.done())
        rpc.accept(response(request,2,17,state=2));self.assertEqual((await task).state,2)
        task=asyncio.create_task(rpc.request(0));await asyncio.sleep(0);rpc.close()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(rpc.pending,{})

    async def test_capture_releases_its_session_on_success_and_failure(self):
        class Fake:
            def __init__(self,truncate=False):self.calls=[];self.truncate=truncate
            async def request(self,op,session=0,offset=0,count=0):
                self.calls.append((op,session,offset,count))
                if op==2:return Reply(op,0,2,1,session,json.dumps(dict(width=192,height=108,bytes=10368,age_ms=20)).encode())
                if op==3:return Reply(op,0,2,1,session,b'x'*(count-int(self.truncate)))
                return Reply(op,0,0,1,session,b'')
        fake=Fake();raw,captured=await capture_frame(fake,31)
        self.assertEqual(len(raw),10368);self.assertGreater(captured,0);self.assertEqual(fake.calls[-1],(4,31,0,0))
        self.assertTrue(all(c[1]==31 for c in fake.calls))
        fake=Fake(True)
        with self.assertRaises(RuntimeError):await capture_frame(fake,31)
        self.assertEqual(fake.calls[-1],(4,31,0,0))

    async def test_disabled_capture_does_not_read_or_release_another_frame(self):
        class Fake:
            def __init__(self):self.calls=[]
            async def request(self,op,session=0,offset=0,count=0):self.calls.append(op);return Reply(op,3,0,1,session,b'')
        fake=Fake();self.assertIsNone(await capture_frame(fake,31));self.assertEqual(fake.calls,[1])

    async def test_disabled_producer_never_requests_capture(self):
        event=asyncio.Event()
        class Fake:
            def __init__(self):self.calls=[]
            async def request(self,op,*args):self.calls.append(op);event.set();return Reply(op,0,0,1,0,b'{"enabled":false}')
        fake=Fake();sent=[]
        with patch('pose_camera_rpc.load_model',return_value=object()):
            producer=P4PoseProducer(fake);task=asyncio.create_task(producer.run(sent.append))
            await asyncio.wait_for(event.wait(),2);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(fake.calls,[0]);self.assertEqual(sent,[])


if __name__=='__main__':unittest.main()
