#!/usr/bin/env python3
"""Verify actual linked model/app and asset bytes against all 32 MiB regions."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,re
from pathlib import Path
from elftools.elf.elffile import ELFFile
def check(elf_path,image_path,assets_path,dts_path,allow_no_model=False):
 image=image_path.read_bytes();assets=assets_path.read_bytes();dts=dts_path.read_text()
 regions={}
 for label,expected in [('p4_whistle_app',(0x2000,0xfde000)),('p4_assets',(0xfe0000,0x1000000)),('p4_settings',(0x1fe0000,0x20000))]:
  match=re.search(r'\b'+label+r':[^{}]*\{([^{}]*)\}',dts)
  if not match:raise ValueError('Missing generated DTS partition: '+label)
  reg=re.search(r'\breg\s*=\s*<\s*(0x[\da-fA-F]+)\s+(0x[\da-fA-F]+)\s*>',match[1])
  if not reg or tuple(int(x,16) for x in reg.groups())!=expected:raise ValueError('Unexpected generated flash region: '+label)
  regions[label]=expected
 intervals=sorted((off,off+size,name) for name,(off,size) in regions.items())
 assert all(0<=a<b<=0x2000000 for a,b,_ in intervals)
 assert all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1))
 if len(image)>regions['p4_whistle_app'][1] or len(assets)>regions['p4_assets'][1]:raise ValueError('Image or asset blob crosses its allocated region')
 model_info={'present':False}
 with elf_path.open('rb') as f:
  elf=ELFFile(f);symbols=elf.get_section_by_name('.symtab');items=symbols.get_symbol_by_name('p4_whistle_model_start')
  if not items and not allow_no_model:raise ValueError('Hosted target must preserve the requested Whistle model')
  if items:
   start=items[0]['st_value'];end=symbols.get_symbol_by_name('p4_whistle_model_end')[0]['st_value']
   section=next(s for s in elf.iter_sections() if s['sh_addr']<=start<end<=s['sh_addr']+s['sh_size'])
   if section['sh_flags']&1 or not 0x40000000<=start<end<=0x42000000:raise ValueError('Whistle model is not read-only flash-mapped data')
   model=section.data()[start-section['sh_addr']:end-section['sh_addr']]
   spec=json.loads((Path(__file__).resolve().parents[1]/'dependencies/p4-whistle.json').read_text())['model']
   digest=hashlib.sha256(model).hexdigest()
   if len(model)!=spec['bytes'] or digest!=spec['sha256']:raise ValueError('Linked model hash/size mismatch')
   offset=image.find(model)
   if offset<0 or image.find(model,offset+1)>=0:raise ValueError('Expected exactly one physical model copy in application image')
   physical_begin=0x2000+offset;physical_end=physical_begin+len(model)
   if not 0x2000<=physical_begin<physical_end<=0xfe0000:raise ValueError('Physical mapped model overlaps assets/settings')
   model_info={'present':True,'bytes':len(model),'sha256':digest,'mapped_begin':hex(start),'mapped_end':hex(end),'physical_begin':hex(physical_begin),'physical_end':hex(physical_end),'copied_to_psram':False}
 return {'flash_bytes':0x2000000,'regions':{k:{'offset':hex(v[0]),'bytes':v[1],'end_exclusive':hex(sum(v))} for k,v in regions.items()},'application_bytes':len(image),'application_sha256':hashlib.sha256(image).hexdigest(),'application_end_exclusive':hex(0x2000+len(image)),'assets_bytes':len(assets),'assets_sha256':hashlib.sha256(assets).hexdigest(),'assets_end_exclusive':hex(0xfe0000+len(assets)),'model':model_info,'overlap':False,'result':'PASS'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['elf','image','assets','dts']:p.add_argument('--'+key,type=Path,required=True)
 p.add_argument('--allow-no-model',action='store_true');p.add_argument('--evidence',type=Path);a=p.parse_args();report=check(a.elf,a.image,a.assets,a.dts,a.allow_no_model)
 if a.evidence:a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
 print(json.dumps(report))
