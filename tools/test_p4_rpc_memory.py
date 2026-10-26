#!/usr/bin/env python3
"""Observe pinned decoder expansion with synthetic data and a bounded allocator."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,os,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];out=root/'build-artifacts/p4-rpc-memory';out.mkdir(parents=True,exist_ok=True)
np=a.workspace/'modules/lib/nanopb';gen=a.workspace/'build-p4-station/zephyr/drivers/misc/esp_hosted_mcu'
# Assert the payload accounting against this linked target, not a host ABI guess.
target_record_bytes=None
with (a.workspace/'build-p4-station/zephyr/zephyr.elf').open('rb') as stream:
 dwarf=ELFFile(stream).get_dwarf_info()
 for cu in dwarf.iter_CUs():
  for die in cu.iter_DIEs():
   name=die.attributes.get('DW_AT_name');size=die.attributes.get('DW_AT_byte_size')
   if name and name.value==b'_wifi_ap_record' and size:
    target_record_bytes=size.value;break
  if target_record_bytes is not None:break
assert target_record_bytes==128,'Re-audit RPC fixture accounting for this target ABI'
override=out/'alloc.h';override.write_text('#include <stddef.h>\nvoid *audit_realloc(void *,size_t);\nvoid audit_free(void *);\n#define pb_realloc audit_realloc\n#define pb_free audit_free\n')
sources=[root/'tests/p4_rpc_memory_test.c',np/'pb_common.c',np/'pb_decode.c',gen/'esp_hosted_mcu_rpc.pb.c']
command=['gcc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-DPB_ENABLE_MALLOC=1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie','-include',str(override),'-I'+str(np),'-I'+str(gen),*map(str,sources),'-o',str(out/'test')]
subprocess.run(command,check=True)
r=subprocess.run([str(out/'test')],text=True,capture_output=True,check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(r.stdout);report['rv32_size_verified_from_elf']=True;report['sources_sha256']={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sources};report['sanitizers']=['address','undefined']
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
