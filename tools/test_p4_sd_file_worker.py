#!/usr/bin/env python3
"""Reuse real SD worker tests and exercise its optional file snapshot ownership."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json, os, runpy, subprocess
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'tools/test_p4_sd_backend.py'),run_name='__main__')
out=root/'build-artifacts/p4-sd-worker-tests'
source=(out/'test.c').read_text()
extra='''
static unsigned file_calls;
int p4_sd_file_io(mb_sd_file_op op,const char *name,const uint8_t *input,size_t size,uint8_t *output,mb_sd_file_result *r,int(*check)(void*),void *context) {
 file_calls++;memset(r,0,sizeof(*r));r->error=check(context);
 if(r->error)return r->error;
 assert(!strcmp(name,"OWN.TXT"));
 if(op==MB_SD_FILE_CREATE||op==MB_SD_FILE_REMOVE_OWN){assert(size==3&&!memcmp(input,"abc",3));memcpy(output,input,size);r->bytes=size;}
 else {memcpy(output,"opened",6);r->bytes=6;}
 r->verified=true;r->created=op==MB_SD_FILE_CREATE;r->synced=r->created;r->removed=op==MB_SD_FILE_REMOVE_OWN;return 0;
}
'''
source=source.replace('int main(void){',extra+'\nint main(void){',1)
source=source.replace(' CHECK(allocations==frees&&stacks==stack_frees);CHECK(probes==25);','''
 CHECK(mb_sd_file_available());CHECK(!mb_sd_file_view(NULL));CHECK(!mb_sd_file_result_get(NULL));
 CHECK(!mb_sd_file_start(MB_SD_FILE_CREATE,"../A",4,(const uint8_t*)"abc",3));
 CHECK(!mb_sd_file_start(MB_SD_FILE_CREATE,"OWN.TXT",7,NULL,3));
 CHECK(!mb_sd_file_start(MB_SD_FILE_REMOVE_OWN,"OWN.TXT",7,NULL,0));
 uint8_t data[3]={'a','b','c'};
 CHECK(mb_sd_file_start(MB_SD_FILE_CREATE,"OWN.TXT",7,data,3));
 memset(data,0,3);CHECK(mb_sd_busy());CHECK(!mb_sd_start());CHECK(!mb_sd_file_view(NULL));finish();
 mb_sd_file_result file_result;
 CHECK(mb_sd_file_result_get(&file_result)&&file_result.created&&file_result.verified&&file_result.bytes==3);
 size_t length;const uint8_t *view=mb_sd_file_view(&length);CHECK(view&&length==3&&!memcmp(view,"abc",3));
 CHECK(!mb_sd_file_start(MB_SD_FILE_CREATE,"OWN.TXT",7,(const uint8_t*)"abc",3));
 CHECK(mb_sd_file_start(MB_SD_FILE_READ,"OWN.TXT",7,NULL,0));finish();
 view=mb_sd_file_view(&length);CHECK(view&&length==6&&!memcmp(view,"opened",6));
 CHECK(!mb_sd_file_start(MB_SD_FILE_REMOVE_OWN,"OTHER.TXT",9,NULL,0));
 CHECK(mb_sd_file_start(MB_SD_FILE_REMOVE_OWN,"OWN.TXT",7,NULL,0));finish();
 CHECK(mb_sd_file_result_get(&file_result)&&file_result.removed);
 CHECK(!mb_sd_file_start(MB_SD_FILE_REMOVE_OWN,"OWN.TXT",7,NULL,0));
 CHECK(mb_sd_file_start(MB_SD_FILE_CREATE,"OWN.TXT",7,(const uint8_t*)"abc",3));mb_sd_cancel();finish();
 CHECK(mb_sd_file_result_get(&file_result)&&file_result.error==-ECANCELED);
 CHECK(!mb_sd_file_view(NULL));CHECK(!mb_sd_file_start(MB_SD_FILE_REMOVE_OWN,"OWN.TXT",7,NULL,0));
 CHECK(file_calls==4);CHECK(allocations==frees&&stacks==stack_frees);CHECK(probes==25);
''',1)
test=out/'files.c';test.write_text(source)
binary=out/'files-test'
flags=['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-fno-pie','-no-pie',
 '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DCONFIG_P4_SD_FILES=1',
 '-DCONFIG_FS_FATFS_MOUNT_MKFS=0','-DCONFIG_DYNAMIC_THREAD_POOL_SIZE=0',
 '-I'+str(out/'include'),'-I'+str(root/'boards/waveshare_esp32p4_wifi6/zephyr/src'),
 '-I'+str(root/'boards/waveshare_esp32p4_wifi6/diagnostics/sd_readonly/src'),'-I'+str(root/'common/storage')]
subprocess.run(flags+[str(test),str(root/'common/storage/sd_file.c'),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,check=True,timeout=20,
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(run.stdout)
report.update(result='PASS',file_worker_runs=4,scope='actual optional worker with synthetic threads/files only',
 sanitizers=['address','undefined'],physical_tested=False)
(out/'files-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
