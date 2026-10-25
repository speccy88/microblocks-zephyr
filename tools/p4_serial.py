#!/usr/bin/env python3
"""COM5-only binary SmallVM transport. Never opens COM12 or auto-selects a port."""
# SPDX-License-Identifier: MPL-2.0
import struct,time,zlib
import serial
from serial.tools import list_ports
from test_wireless_vm import VM,op,words
from p2_serial import primitive

def require_com5():
 items=[p for p in list_ports.comports() if p.device.upper()=='COM5']
 if len(items)!=1 or (items[0].vid,items[0].pid)!=(0x1a86,0x55d3):raise RuntimeError('Expected COM5 CH343 1a86:55d3')
 return dict(port='COM5',vid=0x1a86,pid=0x55d3)

class P4SerialVM(VM):
 def __init__(self):
  self.identity=require_com5();self.host='COM5'
  self.serial=serial.Serial(port=None,baudrate=115200,timeout=.03,write_timeout=3)
  self.serial.port='COM5';self.serial.dtr=self.serial.rts=False;self.serial.open()
  self.serial.reset_input_buffer();self.buffer=bytearray();self.events=[];self.last_ping=0
  self.sent_bytes=self.received_bytes=0;self.upload_seconds=[]
  try:
   self.short(12);body=self.wait(lambda e:e[:2]==(22,0),seconds=5,after=0)[2]
   self.version=body[1:].decode()
   if 'Waveshare ESP32-P4 WIFI6 Zephyr' not in self.version:raise RuntimeError('Unexpected firmware: '+self.version)
  except BaseException:self.close();raise
 def send(self,data):
  if self.serial.write(data)!=len(data):raise RuntimeError('Short COM5 write')
  self.sent_bytes+=len(data)
 def short(self,kind,index=0):self.send(bytes([250,kind,index]))
 def pump(self):
  if time.monotonic()-self.last_ping>.5:self.short(26,73);self.last_ping=time.monotonic()
  data=self.serial.read(min(4096,self.serial.in_waiting or 1));self.received_bytes+=len(data);self.buffer.extend(data)
  if len(self.buffer)>16384:raise RuntimeError('P4 input buffer limit')
  while self.buffer:
   if self.buffer[0]==250:
    if len(self.buffer)<3:return
    self.events.append((self.buffer[1],self.buffer[2],b''));del self.buffer[:3]
   elif self.buffer[0]==251:
    if len(self.buffer)<5:return
    n=int.from_bytes(self.buffer[3:5],'little')
    if n>4096:raise RuntimeError('P4 invalid frame size')
    if len(self.buffer)<5+n:return
    self.events.append((self.buffer[1],self.buffer[2],bytes(self.buffer[5:5+n])));del self.buffer[:5+n]
   else:raise RuntimeError('Unframed COM5 output: '+self.buffer[:48].hex())
 def upload(self,chunk,code,kind=2,fragmented=False):
  if len(code)%4:raise ValueError('Complete words required')
  body=bytes([kind])+code+b'\xfe';packet=bytes([251,32,chunk])+struct.pack('<H',len(body))+body
  start=len(self.events);began=time.monotonic()
  if fragmented:
   for pos in range(0,len(packet),37):self.send(packet[pos:pos+37]);time.sleep(.003)
  else:self.send(packet)
  actual=int.from_bytes(self.wait(lambda e:e[:2]==(23,chunk),seconds=8,after=start)[2],'little')
  self.upload_seconds.append(time.monotonic()-began)
  if actual!=zlib.crc32(code):raise AssertionError('P4 upload CRC mismatch')
  return actual
 def call(self,name,*args):self.upload(10,primitive(name,args),2);return self.run_reporter(10)
 def all_crcs(self):
  start=len(self.events);self.short(38,1);body=self.wait(lambda e:e[:2]==(39,0),after=start)[2]
  if len(body)%5:raise RuntimeError('Invalid CRC table')
  return {body[i]:int.from_bytes(body[i+1:i+5],'little') for i in range(0,len(body),5)}
 def image_request(self,operation,handle,offset=0,count=0):
  body=b'P4IM'+bytes([37,operation])+struct.pack('<IIH',handle,offset,count)
  packet=bytes([251,206,0,len(body)+1,0])+body+b'\xfe';start=len(self.events);self.send(packet)
  response=self.wait(lambda e:e[0]==206 and e[2][0]==37,after=start)[2]
  if response[1]:raise ValueError('Image request rejected')
  return response[2:]
 def close(self):self.serial.close()
