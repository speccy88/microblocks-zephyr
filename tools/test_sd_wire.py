#!/usr/bin/env python3
"""Actual SD transfer extension with synthetic worker, no device/network I/O."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json, os, subprocess
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/sd-wire-tests';out.mkdir(parents=True,exist_ok=True)
test=out/'test.c'
test.write_text('''#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "sd_wire.c"
static unsigned checks,starts,cancels;
static bool busy,available=true;
static uint32_t native_generation;
static mb_sd_file_result result;
static uint8_t snapshot[8192];
static char current_name[13];
bool mb_sd_available(void){return available;}
bool mb_sd_busy(void){return busy;}
void mb_sd_cancel(void){cancels++;busy=false;result.error=-99;}
bool mb_sd_file_available(void){return available;}
uint32_t mb_sd_file_generation(void){return native_generation;}
bool mb_sd_file_result_get(mb_sd_file_result *out){if(busy)return false;if(out)*out=result;return true;}
bool mb_sd_file_copy(size_t offset,uint8_t *out,size_t n){assert(!busy&&offset+n<=result.bytes);memcpy(out,snapshot+offset,n);return true;}
bool mb_sd_file_start(mb_sd_file_op op,const char *name,size_t length,const uint8_t *data,size_t bytes){
 assert(!busy);starts++;native_generation++;busy=true;memset(&result,0,sizeof(result));
 memset(current_name,0,sizeof(current_name));if(length)memcpy(current_name,name,length);
 if(op==MB_SD_FILE_CREATE){result.bytes=bytes;result.created=result.synced=result.verified=true;memcpy(snapshot,data,bytes);}
 else {result.bytes=3;memcpy(snapshot,"abc",3);result.verified=true;result.removed=op==MB_SD_FILE_REMOVE_OWN;}
 return true;
}
static mb_files_dispatcher d;
static uint8_t request[600],reply[640];static uint32_t id,session=5;static size_t written;
#define CHECK(x) do{assert(x);checks++;}while(0)
static size_t frame(unsigned op,const char *name,uint32_t token,uint32_t arg,const uint8_t *data,unsigned count){
 memset(request,0,sizeof(request));memcpy(request,"MBFS",4);request[4]=1;request[5]=op;
 p32(request+6,++id);p32(request+10,session);p32(request+14,token);p32(request+18,arg);p16(request+22,count);
 size_t length=name?strlen(name):0;request[24]=length;if(length)memcpy(request+26,name,length);
 if(op==MB_SD_APPEND&&count)memcpy(request+26+length,data,count);
 return 26+length+(op==MB_SD_APPEND?count:0);
}
static unsigned run(unsigned op,const char *name,uint32_t token,uint32_t arg,const uint8_t *data,unsigned count){
 size_t n=frame(op,name,token,arg,data,count);CHECK(mb_sd_files_wire(&d,1,1,request,n,reply,sizeof(reply),&written));return reply[14];
}
int main(void){
 d.owner=1;d.session=session;d.last_ms=0;
 CHECK(run(MB_SD_CAPS,NULL,0,0,NULL,0)==MB_FILES_OK);CHECK(written==23&&reply[16]==1&&u16(reply+17)==8192);
 available=false;CHECK(run(MB_SD_CAPS,NULL,0,0,NULL,0)==MB_FILES_OK&&reply[16]==0);
 CHECK(run(MB_SD_BEGIN,"NOTE.TXT",0,3,NULL,0)==MB_FILES_UNAVAILABLE);CHECK(!starts);available=true;
 CHECK(run(MB_SD_BEGIN,"../A",0,3,NULL,0)==MB_FILES_PATH);CHECK(!starts);
 CHECK(run(MB_SD_BEGIN,"NOTE.TXT",0,513,NULL,0)==MB_FILES_OK);uint32_t job=u32(reply+16);CHECK(job>0);
 CHECK(run(MB_SD_BEGIN,"OTHER.TXT",0,1,NULL,0)==MB_FILES_BUSY);
 uint8_t bytes[513];for(unsigned i=0;i<sizeof(bytes);i++)bytes[i]=i;
 CHECK(run(MB_SD_APPEND,NULL,job,1,bytes,1)==MB_FILES_SIZE);CHECK(!transfer.received);
 CHECK(run(MB_SD_APPEND,NULL,job,0,bytes,512)==MB_FILES_OK&&u16(reply+16)==512);
 CHECK(run(MB_SD_CREATE,NULL,job,0,NULL,0)==MB_FILES_STATE);
 CHECK(run(MB_SD_APPEND,NULL,job,512,bytes+512,1)==MB_FILES_OK);
 CHECK(run(MB_SD_CREATE,NULL,job+1,0,NULL,0)==MB_FILES_CONFLICT);
 CHECK(run(MB_SD_CREATE,NULL,job,0,NULL,0)==MB_FILES_OK&&starts==1&&busy);
 CHECK(!memcmp(snapshot,bytes,513));for(unsigned i=0;i<8192;i++)assert(!transfer.staging[i]);checks++;
 CHECK(run(MB_SD_STATUS,NULL,job,0,NULL,0)==MB_FILES_OK&&reply[16]==1);
 CHECK(run(MB_SD_CHUNK,NULL,job,0,NULL,512)==MB_FILES_BUSY);
 busy=false;CHECK(run(MB_SD_STATUS,NULL,job,0,NULL,0)==MB_FILES_OK&&reply[16]==0&&reply[23]==7);
 CHECK(run(MB_SD_CHUNK,NULL,job,0,NULL,512)==MB_FILES_OK&&written==530&&!memcmp(reply+18,bytes,512));
 CHECK(run(MB_SD_CHUNK,NULL,job,513,NULL,1)==MB_FILES_SIZE);
 CHECK(run(MB_SD_CHUNK,NULL,job,512,NULL,1)==MB_FILES_OK&&reply[18]==bytes[512]);
 native_generation++;CHECK(run(MB_SD_STATUS,NULL,job,0,NULL,0)==MB_FILES_CONFLICT);
 CHECK(run(MB_SD_OPEN_PLACEHOLDER,NULL,0,0,NULL,0)==0);
}
'''.replace(' CHECK(run(MB_SD_OPEN_PLACEHOLDER,NULL,0,0,NULL,0)==0);','''
 CHECK(run(MB_SD_READ,"NOTE.TXT",0,0,NULL,0)==MB_FILES_OK);job=u32(reply+16);CHECK(starts==2);
 CHECK(run(MB_SD_CANCEL,NULL,job,0,NULL,0)==MB_FILES_OK&&cancels==1);
 CHECK(run(MB_SD_BEGIN,"NEXT.TXT",0,3,NULL,0)==MB_FILES_OK);job=u32(reply+16);
 CHECK(run(MB_SD_APPEND,NULL,job,0,(const uint8_t*)"xyz",3)==MB_FILES_OK);
 size_t n=frame(MB_SD_CREATE,NULL,job,0,NULL,0);
 CHECK(!mb_sd_files_wire(&d,1,1,request,n,reply,639,&written));CHECK(starts==2);
 p32(request+10,session+1);CHECK(mb_sd_files_wire(&d,1,1,request,n,reply,640,&written)&&reply[14]==MB_FILES_DISCONNECTED);
 p32(request+10,session);CHECK(mb_sd_files_wire(&d,1,1,request,n,reply,640,&written)&&reply[14]==MB_FILES_OK);CHECK(starts==3);
 CHECK(mb_sd_files_wire(&d,1,1,request,n,reply,640,&written)&&reply[14]==MB_FILES_PROTOCOL);CHECK(starts==3);
 session=d.session=6;d.last_id=0;CHECK(run(MB_SD_CAPS,NULL,0,0,NULL,0)==MB_FILES_OK);CHECK(cancels==2);
 CHECK(run(MB_SD_STATUS,NULL,job,0,NULL,0)==MB_FILES_CONFLICT);
 CHECK(run(MB_SD_BEGIN,"NEXT.TXT",0,0,NULL,0)==MB_FILES_OK);job=u32(reply+16);
 CHECK(run(MB_SD_CANCEL,NULL,job,0,NULL,0)==MB_FILES_OK&&!transfer.receiving);
 d.last_ms=1;n=frame(MB_SD_CAPS,NULL,0,0,NULL,0);
 CHECK(mb_sd_files_wire(&d,1,40000,request,n,reply,640,&written)&&reply[14]==MB_FILES_TIMEOUT);CHECK(!d.owner&&!transfer.token);
 uint32_t random=17;for(unsigned i=0;i<10000;i++){
  for(unsigned k=0;k<sizeof(request);k++){random=random*1664525u+1013904223u;request[k]=(uint8_t)(random>>24);}
  (void)mb_sd_files_wire(&d,1,40001,request,i%sizeof(request),reply,sizeof(reply),&written);
 }
 CHECK(starts==3);printf("{\\"checks\\":%u,\\"malformed_frames\\":10000,\\"physical_tested\\":false}\\n",checks);
'''))
binary=out/'test'
flags=['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-fno-pie','-no-pie',
 '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(root/'common/storage')]
subprocess.run(flags+[str(test),str(root/'common/storage/storage.c'),str(root/'common/storage/dispatcher.c'),str(root/'common/storage/sd_file.c'),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],check=True,capture_output=True,text=True,timeout=20,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(run.stdout);report.update(result='PASS',sanitizers=['address','undefined'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
