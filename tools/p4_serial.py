#!/usr/bin/env python3
"""COM5-only binary SmallVM transport. Never opens COM12 or auto-selects a port."""
# SPDX-License-Identifier: MPL-2.0
import struct,time,zlib,secrets
from p4_link import rate_packet,rate_reply
import serial
from serial.tools import list_ports
from test_wireless_vm import VM,op,words
def primitive(name,arguments=(),primitive_set=3):
 """Real IOPrims bytecode, including full SmallVM integers for typed handles.

 Follows the repository's P2 encoder; P4 adds pushHugeInteger (opcode 4).
 No device access occurs while assembling bytecode.
 """
 ops=[op(9)];literals=[]
 def string(text,reference,prim=False):
  raw=text.encode()+b'\0';raw+=b'\0'*(-len(raw)%4)
  literals.append((reference,struct.pack('<I',(len(raw)//4<<4)|4)+raw,prim))
 for value in arguments:
  if isinstance(value,str):ops.extend([op(5),0]);string(value,len(ops)-1)
  elif isinstance(value,bool):ops.append(op(2,4 if value else 0))
  elif -64<=value<=63:ops.append(op(2,2*value+1))
  elif -4194304<=value<=4194303:
   tagged=2*value+1;ops.extend([op(3,tagged&255),tagged>>8&65535])
  elif -0x40000000<=value<=0x3fffffff:
   tagged=(2*value+1)&0xffffffff;ops.extend([op(4),tagged&65535,tagged>>16])
  else:raise ValueError('Argument outside SmallVM integer range')
 ops.extend([op(37,len(arguments)),0,op(35),op(127)]);string(name,len(ops)-3,True)
 if len(ops)%2:ops.append(0)
 out=bytearray(words(ops))
 for reference,literal,prim in literals:
  offset=len(out)//2-reference+(primitive_set<<10 if prim else 0)
  struct.pack_into('<H',out,reference*2,offset);out.extend(literal)
 return bytes(out)

def require_com5():
 items=[p for p in list_ports.comports() if p.device.upper()=='COM5']
 if len(items)!=1 or (items[0].vid,items[0].pid)!=(0x1a86,0x55d3):raise RuntimeError('Expected COM5 CH343 1a86:55d3')
 return dict(port='COM5',vid=0x1a86,pid=0x55d3)

class P4SerialVM(VM):
 def __init__(self,baudrate=115200):
  if baudrate not in (115200,460800,921600):raise ValueError('P4 baud must be 115200, 460800 or 921600')
  self.identity=require_com5();self.host='COM5'
  self.serial=serial.Serial(port=None,baudrate=115200,timeout=.03,write_timeout=3)
  self.serial.port='COM5';self.serial.dtr=self.serial.rts=False;self.serial.open()
  self.serial.reset_input_buffer();self.buffer=bytearray();self.events=[];self.last_ping=0
  self.sent_bytes=self.received_bytes=0;self.upload_seconds=[]
  self.link_token=0;self.link_baud=115200;self.last_link_ping=0;self.link_fallback=None
  try:
   body=self.baseline_version()
   self.version=body[1:].decode()
   if 'Waveshare ESP32-P4 WIFI6 Zephyr' not in self.version:raise RuntimeError('Unexpected firmware: '+self.version)
   if baudrate!=115200:self.negotiate_baud(baudrate)
  except BaseException:self.close();raise
 def baseline_version(self):
  # A previous fast controller can have crashed. Only its valid lease frames
  # renew the rate, so baseline discovery waits out at most the 5s lease.
  deadline=time.monotonic()+6.5
  while time.monotonic()<deadline:
   self.serial.reset_input_buffer();self.buffer.clear();self.events.clear();self.short(12)
   try:return self.wait(lambda e:e[:2]==(22,0),seconds=.24,after=0)[2]
   except TimeoutError:pass
   except RuntimeError as error:
    if not str(error).startswith('Unframed COM5 output'):raise
  raise TimeoutError('P4 baseline version handshake failed')
 def rate_request(self,operation,token=0,baud=0,seconds=.7):
  start=len(self.events);self.send(rate_packet(operation,token,baud))
  body=self.wait(lambda e:e[0]==214 and len(e[2])==16 and e[2][5]==operation and int.from_bytes(e[2][8:12],'little')==token,after=start,seconds=seconds)[2]
  return rate_reply(body,operation,token)
 def negotiate_baud(self,baudrate):
  if baudrate not in (115200,460800,921600):raise ValueError('Unsupported P4 baud')
  if baudrate==self.link_baud:return
  if self.link_baud!=115200:self.restore_baud()
  if baudrate==115200:return
  prepared=False
  try:
   status,state,actual=self.rate_request(0)
   if status or state or actual!=115200:raise RuntimeError('Fast serial unavailable in this firmware/profile')
   token=secrets.randbelow(0xffffffff)+1
   status,state,_=self.rate_request(1,token,baudrate)
   if status or state!=1:raise RuntimeError('Fast serial preparation rejected')
   prepared=True;self.serial.flush();self.serial.baudrate=baudrate;time.sleep(.08)
   self.serial.reset_input_buffer();self.buffer.clear();self.events.clear()
   status,state,actual=self.rate_request(2,token,baudrate)
   if status or state!=3 or actual!=baudrate:raise RuntimeError('Fast serial confirmation failed')
   self.link_token=token;self.link_baud=actual;self.last_link_ping=time.monotonic()
  except (TimeoutError,RuntimeError,ValueError,serial.SerialException) as error:
   self.link_fallback=str(error);self.link_token=0;self.link_baud=115200;self.serial.baudrate=115200
   if prepared:time.sleep(1.95)
   self.baseline_version()
 def restore_baud(self):
  if not self.link_token:return
  status,_,_=self.rate_request(3,self.link_token,115200)
  if status:raise RuntimeError('Baseline serial restore rejected')
  self.serial.flush();time.sleep(.08);self.link_token=0;self.link_baud=115200;self.serial.baudrate=115200
  self.baseline_version()
 def keep_link_alive(self):
  # Caller must be between complete VM frames (pump or an empty FrameMux).
  if self.link_token and time.monotonic()-self.last_link_ping>.5:
   self.send(rate_packet(4,self.link_token,self.link_baud));self.last_link_ping=time.monotonic()
 def send(self,data):
  if self.serial.write(data)!=len(data):raise RuntimeError('Short COM5 write')
  self.sent_bytes+=len(data)
 def short(self,kind,index=0):self.send(bytes([250,kind,index]))
 def pump(self):
  self.keep_link_alive()
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
 def run_reporter(self,chunk):
  start=len(self.events);self.short(3,chunk)
  body=self.wait(lambda e:e[0]==18 and e[1]==chunk,after=start)[2]
  if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
  if body[0]==2:return body[1:].decode()
  if body[0]==3:return bool(body[1])
  if body[0]==5:
   total=int.from_bytes(body[1:3],'little');sent=body[3]
   if total!=sent or len(body)!=sent+4:raise RuntimeError('Reporter bytearray truncated; request at most 100 bytes')
   return body[4:]
  raise RuntimeError('Unexpected P4 reporter value type')
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
 def close(self):
  if getattr(self,'link_token',0) and self.serial.is_open:
   try:
    self.send(rate_packet(3,self.link_token,115200));self.serial.flush();time.sleep(.08)
   except (OSError,serial.SerialException):pass
   self.link_token=0
  self.serial.close()
