#!/usr/bin/env python3
"""Actual VM SD frame routing with pinned sender and synthetic filesystem worker."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json, os, runpy, subprocess
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'tools/test_storage_controller.py'),run_name='__main__')
out=root/'build-artifacts/storage-controller'
fake=out/'sd_fakes.c'
fake.write_text('''#include "sd_file.h"
#include <string.h>
#include <assert.h>
unsigned sd_starts,sd_cancels;
static uint32_t generation;static uint8_t bytes[8192];static mb_sd_file_result result;
bool mb_sd_file_available(void){return true;}
bool mb_sd_busy(void){return false;}
void mb_sd_cancel(void){sd_cancels++;}
uint32_t mb_sd_file_generation(void){return generation;}
bool mb_sd_file_result_get(mb_sd_file_result *r){*r=result;return true;}
bool mb_sd_file_copy(size_t offset,uint8_t *out,size_t n){assert(offset+n<=result.bytes);memcpy(out,bytes+offset,n);return true;}
bool mb_sd_file_start(mb_sd_file_op op,const char *name,size_t n,const uint8_t *data,size_t length){
 assert(op==MB_SD_FILE_CREATE&&n==7&&!memcmp(name,"OWN.TXT",7));
 sd_starts++;generation++;memcpy(bytes,data,length);memset(&result,0,sizeof(result));result.bytes=length;result.created=result.synced=result.verified=true;return true;
}
''')
source=(root/'tests/storage_controller_test.c').read_text()
source=source.replace(' mb_storage_protocol_reset();\n printf(',''' mb_storage_protocol_reset();
 extern unsigned sd_starts,sd_cancels;
 r=call(9,0,77,0,NULL,NULL,0,100);fresh=get32(r+16);assert(!r[14]);
 r=call(11,fresh,0,0,NULL,NULL,0,100);assert(!r[14]&&r[16]==1);cases++;
 r=call(12,fresh,0,3,"OWN.TXT",NULL,0,100);assert(!r[14]);job=get32(r+16);
 r=call(13,fresh,job,0,NULL,"abc",3,100);assert(!r[14]);
 test_output_capacity=0;assert(!call(14,fresh,job,0,NULL,NULL,0,100));test_output_capacity=1024;assert(!sd_starts);cases++;
 r=call(14,fresh,job,0,NULL,NULL,0,100);assert(!r[14]&&sd_starts==1);cases++;
 r=call(16,fresh,job,0,NULL,NULL,0,100);assert(!r[14]&&!r[16]&&r[21]==3&&r[23]==7);cases++;
 r=call(17,fresh,job,0,NULL,NULL,3,100);assert(!r[14]&&r[16]==3&&!memcmp(r+18,"abc",3));cases++;
 mb_storage_protocol_poll(101,false);assert(sd_cancels==1);
 r=call(9,0,78,0,NULL,NULL,0,102);uint32_t replacement=get32(r+16);assert(!r[14]&&replacement>fresh);
 r=call(17,fresh,job,0,NULL,NULL,3,102);assert(r[14]==MB_FILES_DISCONNECTED);cases++;
 r=call(17,replacement,job,0,NULL,NULL,3,102);assert(r[14]==MB_FILES_CONFLICT);cases++;
 mb_storage_protocol_reset();
 printf(''',1)
test=out/'sd_bridge.c';test.write_text(source)
flags=['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fno-pie','-no-pie',
 '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DCONFIG_P4_SD_FILES=1',
 '-I'+str(out),'-I'+str(root/'common/storage')]
sources=[root/'common/storage'/name for name in ['storage.c','dispatcher.c','wire.c','controller.c','storage_protocol.c','sd_wire.c','sd_file.c']]
binary=out/'sd-bridge-test'
subprocess.run(flags+list(map(str,sources))+[str(root/'tests/storage_vm_fakes.c'),str(fake),str(test),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=20,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
if run.returncode:print(run.stderr)
run.check_returncode();report=json.loads(run.stdout)
report.update(scope='actual VM frame bridge; synthetic worker; no board/card',sanitizers=['address','undefined'])
(out/'sd-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
