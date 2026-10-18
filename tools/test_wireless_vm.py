#!/usr/bin/env python3
"""Physical SmallVM tests. Replaces VM test chunks; does not flash firmware.

Needs websocket-client==1.9.0. Access values are read privately and never printed.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import json
import struct
import time
import urllib.request
import zlib
from pathlib import Path
import websocket


class VM:
    def __init__(self, host, code):
        self.host = host
        self.ws = websocket.create_connection('ws://'+host+'/ws/vm', origin='http://'+host,
            timeout=5, http_no_proxy=['*'])
        self.ws.send('auth:'+code)
        if self.ws.recv() != 'ready':raise RuntimeError('Board pairing failed')
        self.ws.settimeout(.3)
        self.buffer=bytearray();self.events=[];self.last_ping=0

    def short(self, kind, index=0):self.ws.send_binary(bytes([250,kind,index]))

    def pump(self):
        if time.monotonic()-self.last_ping>.5:
            self.short(26,73);self.last_ping=time.monotonic()
        try:data=self.ws.recv()
        except websocket.WebSocketTimeoutException:return
        if not isinstance(data,bytes) or not data:raise RuntimeError('Unexpected WebSocket response')
        self.buffer.extend(data)
        while self.buffer:
            if self.buffer[0]==250:
                if len(self.buffer)<3:return
                self.events.append((self.buffer[1],self.buffer[2],b''));del self.buffer[:3]
            elif self.buffer[0]==251:
                if len(self.buffer)<5:return
                size=int.from_bytes(self.buffer[3:5],'little')
                if len(self.buffer)<5+size:return
                self.events.append((self.buffer[1],self.buffer[2],bytes(self.buffer[5:5+size])))
                del self.buffer[:5+size]
            else:raise RuntimeError('Unframed VM output byte')

    def wait(self, predicate, seconds=4, after=None):
        start=len(self.events) if after is None else after
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            for event in self.events[start:]:
                if predicate(event):return event
                if event[0]==19:raise RuntimeError('VM task error: '+event[2].hex())
            self.pump()
        raise TimeoutError('Expected VM response was not received')

    def crc(self, chunk):
        start=len(self.events);self.short(11,chunk)
        return int.from_bytes(self.wait(lambda e:e[0]==23 and e[1]==chunk,after=start)[2],'little')

    def upload(self, chunk, code, kind=1, fragmented=False):
        if len(code)%4:raise ValueError('Test bytecode must use complete 32-bit storage words')
        body=bytes([kind])+code+b'\xfe'
        packet=bytes([251,32,chunk])+struct.pack('<H',len(body))+body
        start=len(self.events)
        if fragmented:
            # Exercise WebSocket continuation frames and VM stream fragments.
            for pos in range(0,len(packet),192):
                segment=packet[pos:pos+192]
                mid=len(segment)//2
                self.ws.send_frame(websocket.ABNF.create_frame(segment[:mid],websocket.ABNF.OPCODE_BINARY,fin=0))
                self.ws.send_frame(websocket.ABNF.create_frame(segment[mid:],websocket.ABNF.OPCODE_CONT,fin=1))
                time.sleep(.03)
        else:self.ws.send_binary(packet)
        actual=int.from_bytes(self.wait(lambda e:e[0]==23 and e[1]==chunk,after=start)[2],'little')
        expected=zlib.crc32(code)
        if actual!=expected:raise AssertionError('Uploaded code CRC differs from source')
        return actual

    def run_reporter(self, chunk):
        start=len(self.events);self.short(3,chunk)
        body=self.wait(lambda e:e[0]==18 and e[1]==chunk,after=start)[2]
        if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
        if body[0]==2:return body[1:].decode('utf-8')
        if body[0]==3:return bool(body[1])
        raise RuntimeError('Unexpected reporter value type')

    def variable(self,index):
        start=len(self.events);self.short(7,index)
        body=self.wait(lambda e:e[:2]==(21,index),after=start)[2]
        assert body[0]==1
        return int.from_bytes(body[1:5],'little',signed=True)

    def close(self):self.ws.close()


def op(code,arg=0):return code | ((arg&255)<<8)
def words(values):return struct.pack('<'+'H'*len(values),*values)

def primitive(name, arguments=()):
    ops=[op(9)]
    for value in arguments:
        if isinstance(value,bool):
            ops.append(op(2,4 if value else 0))
        elif -64<=value<=63:
            ops.append(op(2,2*value+1))
        elif -4194304<=value<=4194303:
            tagged=2*value+1
            ops.extend([op(3,tagged&255),(tagged>>8)&65535])
        else:
            raise ValueError('Test primitive integer exceeds the 24-bit object encoding')
    call_word=len(ops)+1
    ops.extend([op(37,len(arguments)),0,op(35),op(127)])
    if len(ops)%2:ops.append(0)
    name_data=name.encode()+b'\0'
    name_data+=b'\0'*((-len(name_data))%4)
    literal=struct.pack('<I',(len(name_data)//4<<4)|4)+name_data
    ops[call_word]=(3<<10)+(len(ops)-call_word) # IOPrims = 3; relative 16-bit offset
    return words(ops)+literal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--reboot-port')
    parser.add_argument('--outputs',type=int,default=50)
    args=parser.parse_args()
    if not 1<=args.outputs<=500:parser.error('Use1..500 outputs')
    private=json.loads(args.private.read_text())
    report={'host':args.host,'scope':'physical board, real VM over authenticated binary WebSocket','checks':{}}
    vm=None
    try:
        vm=VM(args.host,private['pair'])
        start=len(vm.events);vm.short(26,91)
        vm.wait(lambda e:e[:2]==(26,91),after=start);report['checks']['ping']=True
        vm.short(14,1);vm.short(15,0)
        start=len(vm.events);vm.short(26,92);vm.wait(lambda e:e[:2]==(26,92),after=start)
        reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        crcs={0:vm.upload(0,reporter,2)}
        assert [vm.run_reporter(0) for _ in range(10)]==[12]*10
        report['checks']['arithmetic_runs']=10
        edited=bytearray(reporter);edited[5]=17
        vm.upload(0,edited,2);assert vm.run_reporter(0)==13
        vm.upload(0,reporter,2)
        report['checks']['live_bytecode_edit_result']=13
        for name in ['temperatureMilliC','humidityMilliPct','batteryRaw','rtcText']:
            vm.upload(10,primitive(name),2)
            report['checks'][name]=vm.run_reporter(10)
        for button in [0,1]:
            vm.upload(10,primitive('buttonPressed',[button]),2)
            report['checks']['button_'+str(button)+'_released']=not vm.run_reporter(10)
        vm.upload(10,primitive('displayChecker'),2)
        assert vm.run_reporter(10) is False
        report['checks']['lcd_checker_transfer']=True
        # Basic checks default to50 outputs; larger stress runs are opt-in.
        tagged_count=2*args.outputs-1
        stream=words([op(2,1),op(7,0),op(3,tagged_count&255),(tagged_count>>8)&65535,op(7,1),op(6,1),
            op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
        crcs[3]=vm.upload(3,stream)
        start=len(vm.events);vm.short(3,3)
        vm.wait(lambda e:e[:2]==(17,3),seconds=20,after=start)
        outputs=[int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)]
        assert outputs==list(range(1,args.outputs+1))
        report['checks']['ordered_outputs']=len(outputs)
        report['checks']['code_crc32']={str(k):f'{v:08x}' for k,v in crcs.items()}
        # Maximum VM message size, split across many frames with inter-byte gaps.
        large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0])
        crcs[2]=vm.upload(2,large,fragmented=True)
        start=len(vm.events);vm.short(3,2);vm.wait(lambda e:e[:2]==(17,2),after=start)
        report['checks']['fragmented_upload_bytes']=len(large)+7
        vm.ws.send_binary(bytes([251,32,7,100,0,1]));time.sleep(.35)
        start=len(vm.events);vm.short(26,94);vm.wait(lambda e:e[:2]==(26,94),after=start)
        report['checks']['partial_frame_timeout_recovery']=True
        loop=words([op(9),op(2,3),op(8,5),op(22,-3)])
        vm.upload(5,loop);start=len(vm.events);vm.short(3,5)
        vm.wait(lambda e:e[:2]==(16,5),after=start);time.sleep(.1)
        vm.short(4,5);value=vm.variable(5);time.sleep(.2)
        assert value>0 and vm.variable(5)==value
        report['checks']['stop_and_variable_inspection']=True
        startup=words([op(9),op(2,85),op(7,9),0])
        crcs[4]=vm.upload(4,startup,kind=4)
        for chunk,crc in crcs.items():assert vm.crc(chunk)==crc
        vm.close();vm=None;time.sleep(.2)
        reconnect_start=time.monotonic()
        vm=VM(args.host,private['pair']);assert vm.run_reporter(0)==12
        report['checks']['reconnect_arithmetic']=True
        report['checks']['reconnect_seconds']=round(time.monotonic()-reconnect_start,3)
        time.sleep(5)
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        status=json.loads(opener.open('http://'+args.host+'/api/status',timeout=3).read())
        report['checks']['saved_generation']=status['saved_generation'];assert status['saved_generation']>0
        if args.reboot_port:
            vm.close();vm=None
            import serial
            from esptool.reset import HardReset
            port=serial.Serial(port=None,baudrate=115200,timeout=.1);port.dtr=False;port.rts=False
            port.port=args.reboot_port;port.open();HardReset(port,uses_usb=True).reset();port.close()
            until=time.monotonic()+45
            while True:
                try:vm=VM(args.host,private['pair']);break
                except (OSError,websocket.WebSocketException):
                    if time.monotonic()>until:raise
                    time.sleep(1)
            assert all(vm.crc(chunk)==crc for chunk,crc in crcs.items())
            assert vm.run_reporter(0)==12
            assert vm.variable(9)==42
            report['checks']['reboot_crc_and_arithmetic']=True
            report['checks']['saved_start_hat_autorun']=True
        report['result']='PASS'
    except Exception as exc:
        report['result']='FAIL';report['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        if vm:vm.close()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
