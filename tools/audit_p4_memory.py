#!/usr/bin/env python3
"""Read-only ELF/config/map audit. Never selects a device or changes a build."""
# SPDX-License-Identifier: MIT
import argparse, hashlib, json, re
from pathlib import Path
from elftools.elf.elffile import ELFFile

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(build):
    elf_path=build/'zephyr/zephyr.elf'
    config_path=build/'zephyr/.config'
    map_path=build/'zephyr/zephyr.map'
    with elf_path.open('rb') as stream:
        elf=ELFFile(stream)
        assert elf.elfclass==32 and elf['e_machine']=='EM_RISCV'
        sections=[]
        for s in elf.iter_sections():
            if s['sh_flags']&2:
                sections.append({'name':s.name,'address':s['sh_addr'],'bytes':s['sh_size']})
        objects=[]; symbols={}; source=''
        for s in elf.get_section_by_name('.symtab').iter_symbols():
            if s['st_info']['type']=='STT_FILE': source=s.name
            if s['st_info']['bind']=='STB_GLOBAL': symbols[s.name]=s['st_value']
            if s['st_info']['type']!='STT_OBJECT' or not s['st_size']: continue
            index=s['st_shndx']
            if not isinstance(index,int): continue
            section=elf.get_section(index)
            if not section['sh_flags']&2: continue
            address=s['st_value']
            region='internal' if 0x4ff40000<=address<0x4ffa0000 else 'psram' if 0x48000000<=address<0x4a000000 else 'other'
            objects.append({'name':s.name,'source':source if s['st_info']['bind']=='STB_LOCAL' else None,
                            'address':address,'bytes':s['st_size'],'section':section.name,'region':region})
    config={}
    for line in config_path.read_text().splitlines():
        if not line.startswith('CONFIG_') or '=' not in line: continue
        key,value=line.split('=',1)
        if any(word in key for word in ['STACK','HEAP','MALLOC','SPIRAM','PSRAM','CACHE']) or key in ['CONFIG_SMP','CONFIG_MAIN_THREAD_PRIORITY','CONFIG_P4_HOSTED']:
            config[key]=value
    internal=[s for s in sections if 0x4ff40000<=s['address']<0x4ffa0000]
    used=max(s['address']+s['bytes'] for s in internal)-0x4ff40000
    libc_size=symbols['_libc_heap_size']
    assert libc_size==393216-used
    storage=[o for o in objects if o['source'] in ['storage.c','storage_primitives.c','storage_protocol.c','controller.c','dispatcher.c','wire.c']]
    stacks=[o for o in objects if o['region']=='internal' and
            (o['name'].startswith('_k_thread_stack_') or re.search(r'_stacks?(?:\.\d+)?$',o['name']))]
    return {'elf_sha256':sha(elf_path),'config_sha256':sha(config_path),'map_sha256':sha(map_path),
            'static_internal_bytes':used,'internal_capacity':393216,'remaining_internal_bytes':393216-used,
            'libc_malloc_arena_bytes':libc_size,'libc_malloc_arena_policy':config['CONFIG_COMMON_LIBC_MALLOC_ARENA_SIZE'],
            'system_heap_requested_bytes':int(config['CONFIG_HEAP_MEM_POOL_SIZE']),
            'internal_sections':internal,'internal_objects_largest':sorted([o for o in objects if o['region']=='internal'],key=lambda o:o['bytes'],reverse=True)[:30],
            'stacks':stacks,'stack_reservations_total':sum(o['bytes'] for o in stacks),
            'storage_objects':storage,'storage_internal_object_bytes':sum(o['bytes'] for o in storage if o['region']=='internal'),
            'hosted_objects':[o for o in objects if o['source']=='hosted_server.c'],
            'rpc_objects':[o for o in objects if o['source']=='rpc_allocator.c' or o['name']=='rpc_allocator_lock'],
            'psram_sections':[s for s in sections if 0x48000000<=s['address']<0x4a000000],
            'psram_objects':sorted([o for o in objects if o['region']=='psram'],key=lambda o:o['address']),
            'psram_heap_start':symbols['_ext_ram_heap_start'],'psram_heap_end':symbols['_ext_ram_heap_end'],
            'configuration':config,'runtime_measured':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report={name:audit(a.workspace/build) for name,build in [('usb','build-p4-neural'),('station','build-p4-station')]}
    report['station_minus_usb_static_bytes']=report['station']['static_internal_bytes']-report['usb']['static_internal_bytes']
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:{n:v[n] for n in ['static_internal_bytes','libc_malloc_arena_bytes','storage_internal_object_bytes','stack_reservations_total']} for k,v in report.items() if isinstance(v,dict)},indent=2))
if __name__=='__main__': main()
