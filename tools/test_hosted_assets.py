#!/usr/bin/env python3
"""Actual hosted asset handler with synthetic flash/OS, never opens a device."""
# SPDX-License-Identifier: MIT
import json,os,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/hosted-assets-memory';out.mkdir(parents=True,exist_ok=True)
stub=out/'include'
for name in ['kernel.h','net/http/server.h','net/http/service.h','storage/flash_map.h','sys/crc.h','sys/byteorder.h']:
 p=stub/'zephyr'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('/* Host interfaces supplied by forced include. */\n')
reports={}
for psram,diagnostic,latency in [(False,False,False),(True,False,False),(False,True,False),(True,True,False),(False,True,True),(True,True,True)]:
 name=('psram' if psram else 'internal')+('-diagnostic' if diagnostic else '')
 if latency:name+='-latency'
 binary=out/('handler-'+name)
 cmd=['gcc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-pthread','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie','-I'+str(stub),'-include',str(root/'tests/hosted_assets_fakes.h')]
 if psram:cmd+=['-DCONFIG_ESP_SPIRAM=1']
 if diagnostic:cmd+=['-DCONFIG_P4_WIFI_COMPAT_DIAGNOSTIC=1']
 if latency:cmd+=['-DCONFIG_P4_WIFI_LATENCY_DIAGNOSTIC=1']
 subprocess.run(cmd+[str(root/'tests/hosted_assets_test.c'),'-o',str(binary)],check=True)
 result=subprocess.run([str(binary)],text=True,capture_output=True,check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
 reports[name]=json.loads(result.stdout)
# Exercise the exact production linker assertion, including below-floor failure.
bad=subprocess.run(['gcc','-std=c11','-DCONFIG_ZVFS_POLL_MAX=3','-I'+str(stub),'-include',str(root/'tests/hosted_assets_fakes.h'),'-c',str(root/'tests/hosted_assets_test.c'),'-o',str(out/'bad-poll-budget.o')],capture_output=True,text=True)
assert bad.returncode and 'HTTP poll budget requires' in bad.stderr
reports['undersized_poll_budget']='rejected'
linker=(root/'boards/waveshare_esp32p4_wifi6/zephyr/sections-rom.ld').read_text()
guard=re.search(r'ASSERT\(_libc_heap_size[^\n]+',linker).group()
(out/'guard.ld').write_text(guard+'\n')
(out/'empty.c').write_text('void _start(void) {}\n')
subprocess.run(['gcc','-c',str(out/'empty.c'),'-o',str(out/'empty.o')],check=True)
guards={}
for size in [0,1760,8191,8192,9488,149360]:
 r=subprocess.run(['ld','-T',str(out/'guard.ld'),f'--defsym=_libc_heap_size={size}',str(out/'empty.o'),'-o',str(out/'guard.elf')],capture_output=True,text=True)
 assert (r.returncode==0)==(size>=8192),(size,r.stderr)
 if size<8192:assert 'below 8192-byte audit floor' in r.stderr
 guards[str(size)]='accepted' if not r.returncode else 'rejected'
reports.update(linker_guard=guards,sanitizers=['address','undefined'],hardware_access=False)
(out/'report.json').write_text(json.dumps(reports,indent=2)+'\n');print(json.dumps(reports,indent=2))
