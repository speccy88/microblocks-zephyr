#!/usr/bin/env python3
"""USB MBNW v2 setup for an explicitly identified compatible board.

Does not flash, reset, upload bytecode or retrieve stored keys. The installed
board must answer a matching board/protocol probe before a key is requested.
Secrets are entered locally with getpass; never pass them as CLI arguments.
"""
# SPDX-License-Identifier: MIT
import argparse
import getpass
import json
import secrets
import struct
import time


def encode(operation, request_id, ssid=None, key=None, remember=False):
    if operation not in (1,2,3) or not 0<request_id<=0xffffffff:
        raise ValueError('Invalid setup operation/request')
    body=bytearray(b'MBNW'+bytes([2,operation])+struct.pack('<I',request_id))
    try:
        if operation==2:
            if ssid is None or key is None or not 1<=len(ssid)<=32 or not 8<=len(key)<=64 or 0 in ssid or 0 in key:
                raise ValueError('Invalid SSID/key length or NUL byte')
            if len(key)==64 and any(c not in b'0123456789abcdefABCDEF' for c in key):
                raise ValueError('64-byte key must be hexadecimal')
            body.extend((1 if remember else 0,len(ssid),len(key)));body.extend(ssid);body.extend(key)
        elif ssid is not None or key is not None or remember:
            raise ValueError('Unexpected setup values')
        packet=bytearray([251,205,0]);packet.extend(struct.pack('<H',len(body)+1));packet.extend(body);packet.append(254)
        return packet
    finally:
        body[:]=b'\0'*len(body)


class Client:
    def __init__(self, port, usb_serial, expected_board):
        import serial
        from serial.tools import list_ports
        candidates=[p for p in list_ports.comports() if p.device.casefold()==port.casefold() and
                    p.serial_number==usb_serial and p.vid==0x2fe3 and p.pid==4]
        if len(candidates)!=1:
            raise RuntimeError('Expected exact Zephyr USB VID/PID, port and serial; inspect inventory first')
        self.board=expected_board;self.buffer=bytearray()
        self.port=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=2)
        self.port.port=port;self.port.dtr=False;self.port.rts=False
        try:
            self.port.open();self.port.dtr=True
            reply=self.request(1)
            if not reply.get('accepted') or reply.get('status',{}).get('board')!=expected_board or reply['status'].get('setup_protocol')!=2:
                raise RuntimeError('Installed firmware did not identify as the expected MBNW v2 board')
        except BaseException:
            self.close();raise

    def request(self, operation, ssid=None, key=None, remember=False):
        ident=secrets.randbits(32) or 1
        packet=encode(operation,ident,ssid,key,remember)
        try:
            if self.port.write(packet)!=len(packet):raise RuntimeError('Short setup write')
        finally:
            packet[:]=b'\0'*len(packet)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            self.buffer.extend(self.port.read(min(4096,self.port.in_waiting or 1)))
            if len(self.buffer)>8192:raise RuntimeError('Unbounded VM response')
            while self.buffer:
                if self.buffer[0]==250:
                    if len(self.buffer)<3:break
                    del self.buffer[:3];continue
                if self.buffer[0]!=251:raise RuntimeError('Not a binary VM response; no further requests sent')
                if len(self.buffer)<5:break
                size=int.from_bytes(self.buffer[3:5],'little')
                if size>4096:raise RuntimeError('Invalid VM response length')
                if len(self.buffer)<5+size:break
                kind=self.buffer[1];payload=bytes(self.buffer[5:5+size]);del self.buffer[:5+size]
                if kind==205:
                    reply=json.loads(payload)
                    if reply.get('request')==ident:return reply
        raise RuntimeError('Setup response timeout')

    def close(self):
        self.buffer[:]=b'\0'*len(self.buffer)
        if self.port.is_open:
            self.port.dtr=False;self.port.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--usb-serial',required=True)
    parser.add_argument('--board',choices=['xrp-rp2350'],required=True)
    parser.add_argument('--connect',action='store_true')
    parser.add_argument('--remember',action='store_true')
    args=parser.parse_args()
    if args.remember and not args.connect:parser.error('--remember requires --connect')
    client=Client(args.port,args.usb_serial,args.board)
    try:
        if args.connect:
            caps=client.request(1)
            if args.remember and not caps['status'].get('persistence_supported'):
                raise RuntimeError('Board does not advertise persistent settings')
            ssid=bytearray();key=bytearray()
            try:
                ssid.extend(input('SSID (sent only to this USB board): ').encode('utf8'))
                key.extend(getpass.getpass('Wi-Fi key: ').encode('utf8'))
                reply=client.request(2,ssid,key,args.remember)
            finally:ssid[:]=b'\0'*len(ssid);key[:]=b'\0'*len(key)
            if not reply.get('accepted'):raise RuntimeError('Board rejected setup request: '+str(reply.get('command_error')))
            for _ in range(60):
                time.sleep(1);reply=client.request(3)
                if not reply['status'].get('busy'):break
        else:reply=client.request(3)
        # Explicit field selection prevents unknown future status data leaking.
        status=reply.get('status',{})
        print(json.dumps({k:status.get(k) for k in ('board','setup_protocol','persistence_supported','state','busy','ip','error')},indent=2))
        if args.connect and status.get('state')!='connected':raise RuntimeError('Connection/persistence did not complete successfully')
    finally:client.close()

if __name__=='__main__':main()
