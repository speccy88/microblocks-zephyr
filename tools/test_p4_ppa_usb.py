#!/usr/bin/env python3
"""Real COM5 PPA generated-pixel acceptance; no camera or microphone use."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,time,zlib
from pathlib import Path
from p4_serial import P4SerialVM

def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'scope':'COM5 native PPA with generated images','camera_captured':False,'microphone_started':False,'COM12_accessed':False,'checks':{}}
 vm=None
 def pixels(h):
  m=json.loads(vm.image_request(1,h));raw=bytearray()
  for i in range(0,m['bytes'],512):raw.extend(vm.image_request(2,h,i,min(512,m['bytes']-i)))
  return m,bytes(raw)
 def run(h,w,hgt,angle=0,mirror=0,release=False):
  assert vm.call('ppaStart',h,w,hgt,angle,mirror) is True,vm.call('ppaStatus')
  if release:assert vm.call('imageRelease',h) is True
  began=time.monotonic();polls=0;maximum=0
  while vm.call('ppaBusy'):
   now=time.monotonic();vm.call('imageCount');maximum=max(maximum,time.monotonic()-now);polls+=1
   if time.monotonic()-began>3:raise TimeoutError(vm.call('ppaStatus'))
  status=vm.call('ppaStatus');out=vm.call('ppaResult');assert out>0,status
  assert vm.call('ppaResult')==0
  report['checks'].setdefault('jobs',[]).append({'status':status,'vm_roundtrips_while_busy':polls,'max_vm_roundtrip_s':maximum})
  return out
 try:
  vm=P4SerialVM();vm.short(15);time.sleep(.1);vm.call('imageReleaseAll')
  src=vm.call('imageTestPattern',48,32);assert src>0
  meta,raw=pixels(src);assert meta['format']==3
  identity=run(src,48,32);assert pixels(identity)[1]==raw;vm.call('imageRelease',identity)
  for angle,mirror in [(90,0),(180,0),(270,0),(0,1),(0,2),(0,3)]:
   out=run(src,48,32,angle,mirror);m,data=pixels(out)
   ow,oh=(32,48) if angle in (90,270) else (48,32)
   assert (m['width'],m['height'])==(ow,oh)
   expected=bytearray(len(raw))
   for y in range(32):
    for x in range(48):
     dx,dy=(y,47-x) if angle==90 else (47-x,31-y) if angle==180 else (31-y,x) if angle==270 else (x,y)
     if mirror&1:dx=ow-1-dx
     if mirror&2:dy=oh-1-dy
     expected[(dy*ow+dx)*3:(dy*ow+dx+1)*3]=raw[(y*48+x)*3:(y*48+x+1)*3]
   assert data==expected,('pixel mapping',angle,mirror,zlib.crc32(data),zlib.crc32(expected))
   vm.call('imageRelease',out)
  report['checks']['exact_identity_rotations_mirrors_rgb888']=True
  scaled=run(src,96,64);m,data=pixels(scaled);assert (m['width'],m['height'])==(96,64)
  # Interior constant quadrants retain their channels through bilinear scale.
  for x,y in [(16,16),(80,16),(16,48),(80,48)]:
   assert data[(y*96+x)*3:(y*96+x+1)*3]==raw[((y//2)*48+x//2)*3:((y//2)*48+x//2+1)*3]
  vm.call('imageRelease',scaled);report['checks']['bilinear_2x_geometry_and_quadrant_channels']=True
  assert any(0<x<255 for x in data),'Expected bilinear intermediate colors at fixture boundaries'
  report['checks']['bilinear_intermediate_boundary_colors']=True
  for args,word in [((-1,48,32,0,0),'invalid'),((src,49,32,0,0),'1/16'),((src,48,32,45,0),'Rotation'),((src,48,32,0,4),'Mirror'),((src,0,32,0,0),'dimensions')]:
   assert vm.call('ppaStart',*args) is False
   assert word in vm.call('ppaStatus'),vm.call('ppaStatus')
  gray=vm.call('imageGrayscale',src);assert vm.call('ppaStart',gray,48,32,0,0) is False
  assert 'RGB565 or RGB888' in vm.call('ppaStatus');vm.call('imageRelease',gray)
  native565=vm.call('imageTestPattern',48,32,2);raw565=pixels(native565)[1];out=run(native565,48,32)
  assert pixels(out)[1]==raw565;vm.call('imageRelease',out);vm.call('imageRelease',native565)
  report['checks']['rgb565_colored_identity']=True
  out=run(src,48,32,release=True);assert pixels(out)[1]==raw;vm.call('imageRelease',out)
  report['checks']['source_release_does_not_invalidate_owned_copy']=True
  for i in range(8):
   src=vm.call('imageTestPattern',320,192);assert src>0
   assert vm.call('ppaStart',src,640,384,0,0) is True
   vm.call('ppaCancel');vm.call('imageRelease',src)
   end=time.monotonic()+3
   while vm.call('ppaBusy'):
    assert time.monotonic()<end
   assert vm.call('ppaResult')==0
   src=vm.call('imageTestPattern',48,32);out=run(src,48,32);vm.call('imageRelease',src);vm.call('imageRelease',out)
  report['checks']['cancel_and_reuse_rounds']=8
  src=vm.call('imageTestPattern',48,32)
  others=[vm.call('imageCreate',8,8,3) for _ in range(2)];assert min(others)>0
  assert vm.call('ppaStart',src,48,32,0,0) is True
  extra=vm.call('imageCreate',8,8,3);assert extra>0
  end=time.monotonic()+3
  while vm.call('ppaBusy'):assert time.monotonic()<end
  assert vm.call('ppaResult')==0 and 'capacity exhausted' in vm.call('ppaStatus')
  for h in [src,*others,extra]:vm.call('imageRelease',h)
  report['checks']['result_capacity_race_releases_unadopted_output']=True
  assert vm.call('imageCount')==0 and vm.call('imageMemory')==0
  large=[vm.call('imageCreate',1280,720,3) for _ in range(3)];assert min(large)>0
  for h in large:vm.call('imageRelease',h)
  report['checks']['post_job_store_allocation_bytes']=8294400
  report['checks']['final_status']=vm.call('ppaStatus');report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('ppaCancel');vm.call('imageReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);main(p.parse_args())
