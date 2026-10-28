#!/usr/bin/env python3
"""Actual SD I/O adapter with an instrumented synthetic FatFs, no card access."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json, os, subprocess
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/p4-sd-file-tests';out.mkdir(parents=True,exist_ok=True)
inc=out/'include';(inc/'zephyr/fs').mkdir(parents=True,exist_ok=True)
(inc/'zephyr/fs/fs.h').write_text('''#define FS_FATFS 0
#define FS_MOUNT_FLAG_NO_FORMAT 1
struct fs_mount_t {int type;const char *mnt_point;void *fs_data;unsigned flags;};
int fs_mount(struct fs_mount_t *);int fs_unmount(struct fs_mount_t *);
''')
(inc/'ff.h').write_text('''#include <stddef.h>
#include <stdint.h>
typedef enum {FR_OK,FR_DISK_ERR,FR_NOT_READY,FR_NO_FILE,FR_NO_PATH,FR_EXIST,FR_DENIED,FR_TIMEOUT,FR_WRITE_PROTECTED,FR_INVALID_NAME} FRESULT;
typedef unsigned UINT;
typedef struct {unsigned char fs_type,data[512];} FATFS;
typedef struct {size_t position,size;unsigned mode;int valid;} FIL;
typedef struct {unsigned fattrib;char fname[13];uint32_t fsize;} FILINFO;
typedef struct {unsigned index,valid;} DIR;
#define f_size(f) ((f)->size)
#define FS_FAT12 1
#define FS_FAT16 2
#define FS_FAT32 3
#define FA_READ 1
#define FA_WRITE 2
#define FA_OPEN_EXISTING 0
#define FA_CREATE_NEW 4
#define AM_DIR 16
FRESULT f_stat(const char*,FILINFO*);FRESULT f_mkdir(const char*);
FRESULT f_open(FIL*,const char*,unsigned);FRESULT f_close(FIL*);
FRESULT f_write(FIL*,const void*,UINT,UINT*);FRESULT f_read(FIL*,void*,UINT,UINT*);
FRESULT f_sync(FIL*);FRESULT f_unlink(const char*);
FRESULT f_opendir(DIR*,const char*);FRESULT f_readdir(DIR*,FILINFO*);FRESULT f_closedir(DIR*);
''')
test=out/'test.c'
test.write_text('''#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "sd_file_io.c"
static unsigned checks,mounts,unmounts,opens,closes,writes,reads,syncs,unlinks;
static unsigned directory,present,open_file,short_write,short_read,oversized;
static int fail_mount,fail_unmount;
static unsigned fail_open,fail_close,fail_write,fail_read,fail_sync,fail_stat,fail_mkdir,fail_unlink;
static uint8_t disk_bytes[MB_SD_FILE_BYTES],original[19],input[MB_SD_FILE_BYTES],output[MB_SD_FILE_BYTES];
static size_t disk_length;
#define CHECK(c) do {assert(c);checks++;} while(0)
static void correct_path(const char *p) {assert(!strcmp(p,"SD:/MBFILES/TEST1234.TXT"));}
static void bounce_only(const void *p,size_t n) {
 assert(n<=512 && ((uintptr_t)p%64)==0);
 assert(p!=(const void*)input && p!=(const void*)output && p!=(const void*)disk_bytes);
}
int fs_mount(struct fs_mount_t *m){assert(m->flags==FS_MOUNT_FLAG_NO_FORMAT);assert(!strcmp(m->mnt_point,"/SD:"));mounts++;file_system.fs_type=FS_FAT32;return fail_mount;}
int fs_unmount(struct fs_mount_t *m){assert(m==&file_mount&&!open_file);unmounts++;return fail_unmount;}
FRESULT f_stat(const char *p,FILINFO *i){
 if(fail_stat)return FR_DISK_ERR;
 if(!strcmp(p,"SD:/MBFILES")){i->fattrib=AM_DIR;return directory?FR_OK:FR_NO_FILE;}
 correct_path(p);return present?FR_OK:FR_NO_FILE;
}
FRESULT f_mkdir(const char *p){assert(!strcmp(p,"SD:/MBFILES")&&!directory);if(fail_mkdir)return FR_DISK_ERR;directory=1;return FR_OK;}
FRESULT f_open(FIL *f,const char *p,unsigned mode){
 correct_path(p);assert(!open_file);assert(mode==(FA_WRITE|FA_CREATE_NEW)||mode==(FA_READ|FA_OPEN_EXISTING));
 opens++;if(fail_open&&opens==fail_open)return FR_DISK_ERR;
 if(mode&FA_CREATE_NEW){if(present)return FR_EXIST;present=1;disk_length=0;}
 else if(!present)return FR_NO_FILE;
 *f=(FIL){0,oversized?MB_SD_FILE_BYTES+1:disk_length,mode,1};open_file=1;return FR_OK;
}
FRESULT f_close(FIL *f){assert(f->valid&&open_file);open_file=0;f->valid=0;closes++;return fail_close?FR_DISK_ERR:FR_OK;}
FRESULT f_write(FIL *f,const void *p,UINT n,UINT *count){
 assert(f->valid&&(f->mode&FA_WRITE));bounce_only(p,n);writes++;if(fail_write){*count=0;return FR_DISK_ERR;}
 *count=short_write?n-1:n;assert(f->position+*count<=sizeof(disk_bytes));memcpy(disk_bytes+f->position,p,*count);
 f->position+=*count;disk_length=f->size=f->position;return FR_OK;
}
FRESULT f_read(FIL *f,void *p,UINT n,UINT *count){
 assert(f->valid&&f->mode==FA_READ);bounce_only(p,n);reads++;if(fail_read){*count=0;return FR_DISK_ERR;}
 *count=short_read?n-1:n;assert(f->position+*count<=disk_length);memcpy(p,disk_bytes+f->position,*count);f->position+=*count;return FR_OK;
}
FRESULT f_sync(FIL *f){assert(f->valid&&(f->mode&FA_WRITE));syncs++;return fail_sync?FR_DISK_ERR:FR_OK;}
FRESULT f_unlink(const char *p){correct_path(p);assert(!open_file&&present);unlinks++;if(fail_unlink)return FR_DISK_ERR;present=0;disk_length=0;return FR_OK;}
FRESULT f_opendir(DIR *d,const char *p){assert(!strcmp(p,"SD:/MBFILES"));*d=(DIR){0,1};return directory?FR_OK:FR_NO_PATH;}
FRESULT f_readdir(DIR *d,FILINFO *info){assert(d->valid);memset(info,0,sizeof(*info));if(!d->index++&&present){strcpy(info->fname,"TEST1234.TXT");info->fsize=disk_length;}return FR_OK;}
FRESULT f_closedir(DIR *d){assert(d->valid);d->valid=0;return FR_OK;}
static void reset(void){
 mounts=unmounts=opens=closes=writes=reads=syncs=unlinks=directory=present=open_file=short_write=short_read=oversized=0;
 fail_mount=fail_unmount=fail_open=fail_close=fail_write=fail_read=fail_sync=fail_stat=fail_mkdir=fail_unlink=0;
 disk_length=0;memset(disk_bytes,0,sizeof(disk_bytes));memset(output,0,sizeof(output));
 for(size_t i=0;i<sizeof(input);i++)input[i]=(uint8_t)(i*17+3);
 memcpy(original,"PRIVATE-UNRELATED",18);
}
struct stopping {unsigned at,calls;int error;};
static int stop(void *v){struct stopping *s=v;return ++s->calls>=s->at?s->error:0;}
static int run(mb_sd_file_op op,size_t bytes,mb_sd_file_result *r){return p4_sd_file_io(op,"TEST1234.TXT",input,bytes,output,r,NULL,NULL);}
int main(void){
 mb_sd_file_result r;
 const char *valid[]={"A","A.TXT","TEST1234.TXT","_1234567.BIN","12345678.123"};
 const char *invalid[]={"",".","..","a.txt","A.","A..TXT","123456789.TXT","A.1234","../A","SD:/A","/A","A/B","A B","A\\\\B","A%20B"};
 for(unsigned i=0;i<sizeof(valid)/sizeof(*valid);i++)CHECK(mb_sd_file_name(valid[i],strlen(valid[i])));
 for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++)CHECK(!mb_sd_file_name(invalid[i],strlen(invalid[i])));
 const size_t sizes[]={0,1,511,512,513,8192};
 for(unsigned i=0;i<sizeof(sizes)/sizeof(*sizes);i++){
  reset();size_t size=sizes[i];CHECK(!run(MB_SD_FILE_CREATE,size,&r));CHECK(r.created&&r.synced&&r.verified&&!r.error&&r.bytes==size);
  CHECK(present&&directory&&disk_length==size&&!memcmp(disk_bytes,input,size));CHECK(mounts==unmounts&&opens==closes&&!open_file);
  CHECK(run(MB_SD_FILE_CREATE,size,&r)==-EEXIST);CHECK(!r.created&&disk_length==size&&!memcmp(disk_bytes,input,size));
  memset(output,0,sizeof(output));CHECK(!run(MB_SD_FILE_READ,0,&r));CHECK(r.verified&&r.bytes==size&&!memcmp(output,input,size));
  CHECK(!run(MB_SD_FILE_LIST,0,&r));CHECK(r.verified&&output[0]==1&&r.bytes==18&&!r.truncated);
  CHECK(!memcmp(output+6,"TEST1234.TXT",12));
  CHECK(!run(MB_SD_FILE_REMOVE_OWN,size,&r));CHECK(r.removed&&r.verified&&!present&&!open_file&&mounts==unmounts);
  CHECK(!memcmp(original,"PRIVATE-UNRELATED",18));
 }
 reset();CHECK(p4_sd_file_io(MB_SD_FILE_CREATE,"../A",input,1,output,&r,NULL,NULL)==-EINVAL);CHECK(!mounts);
 CHECK(run(MB_SD_FILE_CREATE,8193,&r)==-EINVAL);CHECK(!mounts);
 CHECK(p4_sd_file_io(MB_SD_FILE_CREATE,"A",NULL,1,output,&r,NULL,NULL)==-EINVAL);CHECK(!mounts);
 reset();fail_mount=-ENODEV;CHECK(run(MB_SD_FILE_CREATE,5,&r)==-ENODEV);CHECK(!unmounts&&!present);
 reset();fail_mkdir=1;CHECK(run(MB_SD_FILE_CREATE,5,&r)==-EIO);CHECK(!present&&unmounts==1);
 reset();fail_stat=1;CHECK(run(MB_SD_FILE_CREATE,5,&r)==-EIO);CHECK(!present&&unmounts==1);
 for(unsigned mode=0;mode<7;mode++){
  reset();
  if(mode==0)fail_open=1;
  if(mode==1)fail_write=1;
  if(mode==2)short_write=1;
  if(mode==3)fail_sync=1;
  if(mode==4)fail_close=1;
  if(mode==5)fail_open=2;
  if(mode==6)fail_unmount=-EIO;
  CHECK(run(MB_SD_FILE_CREATE,513,&r)!=0);CHECK(!open_file&&unmounts==1&&!unlinks);CHECK(mode==0?!present:r.created);
 }
 reset();CHECK(!run(MB_SD_FILE_CREATE,513,&r));input[0]^=1;
 CHECK(run(MB_SD_FILE_REMOVE_OWN,513,&r)==-ESTALE);CHECK(present&&!unlinks);input[0]^=1;
 CHECK(run(MB_SD_FILE_REMOVE_OWN,512,&r)==-ESTALE);CHECK(present&&!unlinks);
 fail_read=1;CHECK(run(MB_SD_FILE_REMOVE_OWN,513,&r)==-EIO);CHECK(present&&!unlinks);fail_read=0;
 short_read=1;CHECK(run(MB_SD_FILE_READ,0,&r)==-EIO);CHECK(present);short_read=0;
 oversized=1;CHECK(run(MB_SD_FILE_READ,0,&r)==-EFBIG);CHECK(present);oversized=0;
 fail_unlink=1;CHECK(run(MB_SD_FILE_REMOVE_OWN,513,&r)==-EIO);CHECK(present&&!r.removed);fail_unlink=0;
 CHECK(!run(MB_SD_FILE_REMOVE_OWN,513,&r));CHECK(!present);
 unsigned boundaries=0;
 for(unsigned mode=0;mode<2;mode++)for(unsigned at=1;at<=16;at++){
  reset();struct stopping s={at,0,mode?-ETIMEDOUT:-ECANCELED};
  int e=p4_sd_file_io(MB_SD_FILE_CREATE,"TEST1234.TXT",input,513,output,&r,stop,&s);
  if(e){CHECK(e==s.error);CHECK(r.error==s.error);boundaries++;}else CHECK(r.verified);
  CHECK(!unlinks&&!open_file&&mounts==unmounts);CHECK(!memcmp(original,"PRIVATE-UNRELATED",18));
 }
 printf("{\\"checks\\":%u,\\"cancellation_boundaries\\":%u,\\"physical_tested\\":false}\\n",checks,boundaries);
}
''')
flags=['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-fno-pie','-no-pie',
 '-fsanitize=address,undefined','-fno-sanitize-recover=all','-DCONFIG_P4_SD_FILES=1',
 '-I'+str(inc),'-I'+str(root/'common/storage'),'-I'+str(root/'boards/waveshare_esp32p4_wifi6/zephyr/src')]
binary=out/'test'
subprocess.run(flags+[str(test),str(root/'common/storage/sd_file.c'),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,timeout=20,
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
if run.returncode:print(run.stderr)
run.check_returncode()
report=json.loads(run.stdout)
report.update(result='PASS',scope='actual file I/O and validation with synthetic filesystem only',
 sanitizers=['address','undefined'],no_card_or_board_access=True)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
