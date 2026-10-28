#!/usr/bin/env python3
"""Reject oversized/non-mapped native Whistle images, using actual ELF symbols."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from p4_whistle_permutations import permutations
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--elf',type=Path,required=True);p.add_argument('--bin',type=Path,required=True);p.add_argument('--evidence',type=Path);a=p.parse_args()
 raw=a.bin.read_bytes()
 if len(raw)>0xfe0000-0x2000:raise ValueError('Application/model crosses reserved 0xfe0000 boundary')
 with a.elf.open('rb') as f:
  elf=ELFFile(f);symbols=elf.get_section_by_name('.symtab')
  start=symbols.get_symbol_by_name('p4_whistle_model_start')[0]['st_value']
  end=symbols.get_symbol_by_name('p4_whistle_model_end')[0]['st_value']
  if not 0x40000000<=start<end<=0x42000000:raise ValueError('Model is not in P4 flash-mapped DROM')
  section=next(s for s in elf.iter_sections() if s['sh_addr']<=start and end<=s['sh_addr']+s['sh_size'])
  if section['sh_flags']&1:raise ValueError('Model was placed in writable RAM')
  model=section.data()[start-section['sh_addr']:end-section['sh_addr']]
  tables=[]
  for i,expected in enumerate(permutations(model),1):
   name='s_perm'+str(i);matches=symbols.get_symbol_by_name(name)
   if not matches or len(matches)!=1:raise ValueError('Missing/ambiguous flash permutation '+name)
   symbol=matches[0];address=symbol['st_value'];size=symbol['st_size']
   owner=elf.get_section(symbol['st_shndx'])
   if size!=2048 or not 0x40000000<=address<address+size<=0x42000000 or owner['sh_flags']&1:
    raise ValueError('Permutation not const in flash: '+name)
   raw_table=owner.data()[address-owner['sh_addr']:address-owner['sh_addr']+size]
   if raw_table!=struct.pack('<512i',*expected):raise ValueError('Linked permutation differs from pinned model')
   tables.append({'name':name,'address':hex(address),'bytes':size})
 spec=json.loads((Path(__file__).resolve().parents[1]/'dependencies/p4-whistle.json').read_text())['model']
 if len(model)!=spec['bytes'] or hashlib.sha256(model).hexdigest()!=spec['sha256']:raise ValueError('Linked model hash mismatch')
 report={'native_elf':'RV32 Zephyr','image_bytes':len(raw),'flash_offset':'0x2000','reserved_boundary':'0xfe0000',
  'model_start':hex(start),'model_end':hex(end),'model_bytes':len(model),'model_sha256':spec['sha256'],
  'image_sha256':hashlib.sha256(raw).hexdigest(),'weights_copied_to_psram':False,'const_permutations':tables}
 if a.evidence:a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
 print(json.dumps(report))
