#!/usr/bin/env python3
"""Fail a hosted link if the bounded RPC pool/hook is not actually selected."""
# SPDX-License-Identifier: MIT
import argparse,json,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser();p.add_argument('--elf',type=Path,required=True);p.add_argument('--objdump',required=True);a=p.parse_args()
with a.elf.open('rb') as f:
 elf=ELFFile(f);assert elf.elfclass==32 and elf['e_machine']=='EM_RISCV'
 symbols={s.name:s for s in elf.get_section_by_name('.symtab').iter_symbols()}
 result={}
 for name in ['rpc_pool','rpc_state','rpc_allocator_lock']:
  s=symbols[name];result[name]={'address':hex(s['st_value']),'bytes':s['st_size']}
  if name!='rpc_allocator_lock':assert 0x48000000<=s['st_value']<0x4a000000
 assert result['rpc_pool']['bytes']==65536
 assert symbols['esp_hosted_mcu_decode_rpc']['st_info']['bind']=='STB_GLOBAL'
 assert symbols['_libc_heap_size']['st_value']>=8192
 result['libc_arena_bytes']=symbols['_libc_heap_size']['st_value']
for name,target in [('allocate_field','p4_rpc_realloc'),('pb_release_single_field','p4_rpc_free')]:
 dis=subprocess.check_output([a.objdump,'-d',f'--disassemble={name}',str(a.elf)],text=True)
 assert '<'+target+'>' in dis,(name,'allocator hook absent')
 for banned in ['malloc','realloc','free','k_malloc','k_calloc']:
  assert '<'+banned+'>' not in dis,(name,'unexpected shared allocator')
result.update(result='PASS',nanopb_uses_isolated_pool=True,decode_hook='strong',physical_tested=False)
print(json.dumps(result))
