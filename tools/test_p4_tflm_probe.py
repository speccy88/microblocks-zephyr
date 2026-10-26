#!/usr/bin/env python3
"""Bounded COM5 native TFLM sine fixture; UART data only, no actuation/audio."""
# SPDX-License-Identifier: MIT
import argparse,datetime,hashlib,json,math,re,time
from pathlib import Path
import serial
from p4_serial import require_com5
def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'profile':'standalone native Zephyr TFLM fixture, not SmallVM model import',
 'zephyr_commit':'a915b2f12675b48b16d56653ea145dcd8f20cbbf','tflm_commit':'43b2a106a391dd8a099ac47f2ae858630a397264',
 'backend':'TFLM reference INT8 FullyConnected','image_sha256':hashlib.sha256(a.image.read_bytes()).hexdigest(),
 'configured_tensor_arena_bytes':2000,'camera_or_microphone_used':False,'actuation':False,'COM12_accessed':False}
 port=None
 try:
  model_source=a.model_source.read_text();array=model_source.split('g_model[] = {',1)[1].split('};',1)[0]
  model=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',array))
  assert model and a.image.read_bytes().count(model)==1,'Fixture model differs from flashed image'
  report['model_bytes']=len(model);report['model_sha256']=hashlib.sha256(model).hexdigest()
  require_com5();port=serial.Serial(port=None,baudrate=115200,timeout=.1);port.port='COM5';port.dtr=False;port.rts=False;port.open()
  port.reset_input_buffer();port.rts=True;time.sleep(.1);port.rts=False
  raw=bytearray();deadline=time.monotonic()+8
  while time.monotonic()<deadline and len(raw)<16384:
   raw.extend(port.read(min(2048,port.in_waiting or 1)))
   if len(re.findall(rb'x_value:',raw))>=10:break
  text=raw.decode('utf8',errors='replace');points=[]
  for x,y in re.findall(r'x_value:\s*([-+\d.eE]+),\s*y_value:\s*([-+\d.eE]+)',text):
   x,y=float(x),float(y);assert math.isfinite(x) and math.isfinite(y)
   points.append({'x':x,'y':y,'expected_sin':round(math.sin(x),6),'absolute_error':round(abs(y-math.sin(x)),6)})
  report['points']=points;assert len(points)==10,'Expected ten bounded native inference outputs'
  assert all(abs(p['x']-i*2*math.pi/20)<.001 for i,p in enumerate(points)),'Unexpected fixture input order'
  report['maximum_absolute_error']=max(p['absolute_error'] for p in points)
  report['acceptance_absolute_tolerance']=.2
  assert report['maximum_absolute_error']<=.2,'Sine fixture exceeds its stated approximation tolerance'
  assert 'Invoke failed' not in text and 'AllocateTensors() failed' not in text
  report['result']='PASS';raw[:]=b'\0'*len(raw)
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if port:port.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--image',type=Path,required=True);p.add_argument('--model-source',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute required for COM5 reset/read')
 main(a)
