#!/usr/bin/env python3
"""Inventory actual P4 ELF allocations; this does not measure runtime safety."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile

BEGIN, END = 0x4ff40000, 0x4ffa0000


def inventory(path):
    with path.open('rb') as stream:
        elf=ELFFile(stream); symbols=elf.get_section_by_name('.symtab')
        arena=symbols.get_symbol_by_name('_libc_heap_size')[0]['st_value']
        sections=[{'name':s.name,'address':hex(s['sh_addr']),'bytes':s['sh_size']}
                  for s in elf.iter_sections() if s['sh_flags']&2 and BEGIN<=s['sh_addr']<END and s['sh_size']]
        objects={}
        for s in symbols.iter_symbols():
            address,size=s['st_value'],s['st_size']
            if s['st_info']['type']=='STT_OBJECT' and size and BEGIN<=address<address+size<=END:
                objects.setdefault((address,size),[]).append(s.name)
        largest=[{'names':names,'address':hex(address),'bytes':size}
                 for (address,size),names in sorted(objects.items(),key=lambda p:p[0][1],reverse=True)[:30]]
        const=[]
        for name in ('s_perm1','s_perm2'):
            s=symbols.get_symbol_by_name(name)[0];owner=elf.get_section(s['st_shndx'])
            const.append({'name':name,'address':hex(s['st_value']),'bytes':s['st_size'],
                          'section':owner.name,'writable':bool(owner['sh_flags']&1)})
    return {'elf_sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'region_bytes':END-BEGIN,
            'static_occupied_bytes':END-BEGIN-arena,'static_occupied_percent':round(100*(END-BEGIN-arena)/(END-BEGIN),3),
            'libc_arena_reserved_bytes':arena,'allocated_sections':sections,'largest_internal_objects':largest,
            'permutations':const,'physical_tested':False,'runtime_free_heap_measured':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--elf',type=Path,required=True);p.add_argument('--baseline',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();report={'after':inventory(a.elf)}
    if a.baseline:
        report['before']=inventory(a.baseline)
        report['static_reduction_bytes']=report['before']['static_occupied_bytes']-report['after']['static_occupied_bytes']
    raw=json.dumps(report,indent=2)+'\n'
    if a.output:a.output.write_text(raw,encoding='utf-8',newline='\n')
    print(json.dumps({key:value for key,value in report['after'].items()
                      if key not in ('allocated_sections','largest_internal_objects')}) if a.output else raw)
