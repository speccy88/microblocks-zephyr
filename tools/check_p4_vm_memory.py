#!/usr/bin/env python3
"""Guard CPU-owned VM task placement separately from native call stacks."""
# SPDX-License-Identifier: MIT
import argparse,json
from pathlib import Path
from elftools.elf.elffile import ELFFile

def check(path):
 with Path(path).open('rb') as stream:
  elf=ELFFile(stream)
  if elf.elfclass!=32 or elf['e_machine']!='EM_RISCV':raise ValueError('Expected native RV32 P4 ELF')
  table=elf.get_section_by_name('.symtab')
  tasks=table.get_symbol_by_name('tasks')
  if not tasks or len(tasks)!=1:raise ValueError('Expected one VM task array')
  task=tasks[0];start=task['st_value'];size=task['st_size']
  if size!=5240 or not 0x48000000<=start<start+size<=0x4a000000:raise ValueError('VM task size or external RAM placement changed')
  section=elf.get_section(task['st_shndx'])
  if not section['sh_flags']&1:raise ValueError('Task state must remain writable')
  stacks={}
  for name in ['z_main_stack','_k_thread_stack_whistle_thread','_k_thread_stack_http_server_tid']:
   found=table.get_symbol_by_name(name)
   if not found:continue
   symbol=found[0];address=symbol['st_value'];length=symbol['st_size']
   if not 0x4ff40000<=address<address+length<=0x4ffa0000:raise ValueError('Audited native stack moved: '+name)
   stacks[name]={'bytes':length,'address':hex(address)}
  if 'z_main_stack' not in stacks:raise ValueError('Main native stack missing')
  return {'result':'PASS','VM_task_bytes':size,'VM_task_address':hex(start),'native_stacks':stacks,'physical_tested':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--elf',required=True,type=Path);a=p.parse_args();print(json.dumps(check(a.elf)))
