#!/usr/bin/env python3
"""Exercise the actual isolated SD probe with synthetic filesystem calls only."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json, os, subprocess
root=Path(__file__).resolve().parents[1]
source=root/'boards/waveshare_esp32p4_wifi6/diagnostics/sd_readonly/src'
out=root/'build-artifacts/p4-sd-readonly-tests';out.mkdir(parents=True,exist_ok=True)
inc=out/'include';(inc/'zephyr/fs').mkdir(parents=True,exist_ok=True)
(inc/'zephyr/storage').mkdir(parents=True,exist_ok=True)
(inc/'zephyr/storage/disk_access.h').write_text('''#define DISK_IOCTL_GET_SECTOR_COUNT 1
#define DISK_IOCTL_GET_SECTOR_SIZE 2
int disk_access_ioctl(const char *, unsigned char, void *);
''')
(inc/'ff.h').write_text('#define FS_FAT12 1\n#define FS_FAT16 2\n#define FS_FAT32 3\ntypedef struct {unsigned char fs_type,data[512];} FATFS;\n')
(inc/'zephyr/fs/fs.h').write_text('''#include <stdint.h>
#include <stddef.h>
#define FS_FATFS 0
#define FS_MOUNT_FLAG_NO_FORMAT 1
#define FS_MOUNT_FLAG_READ_ONLY 2
#define FS_DIR_ENTRY_DIR 1
#define FS_DIR_ENTRY_FILE 0
struct fs_mount_t {int type;const char *mnt_point;void *fs_data;unsigned flags;};
struct fs_statvfs {uint64_t f_frsize,f_blocks,f_bfree;};
struct fs_dir_t {int valid;};
struct fs_dirent {unsigned type;char name[256];};
static inline void fs_dir_t_init(struct fs_dir_t *d){d->valid=0;}
int fs_mount(struct fs_mount_t*);
int fs_unmount(struct fs_mount_t*);
int fs_statvfs(const char*,struct fs_statvfs*);
int fs_opendir(struct fs_dir_t*,const char*);
int fs_readdir(struct fs_dir_t*,struct fs_dirent*);
int fs_closedir(struct fs_dir_t*);
''')
test=out/'test.c'
test.write_text('''#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include "probe.c"
static int fail_mount,fail_stat,fail_open,fail_read,fail_close,fail_unmount,fail_geometry;
static unsigned mounted,unmounted,opened,closed,reads,available,checks;
static uint32_t sectors,sector_bytes;
static struct fs_statvfs stats;
#define CHECK(x) do {assert(x);checks++;} while(0)
int fs_mount(struct fs_mount_t *m){assert(m->flags==(FS_MOUNT_FLAG_NO_FORMAT|FS_MOUNT_FLAG_READ_ONLY));assert(!strcmp(m->mnt_point,"/SD:"));filesystem.fs_type=FS_FAT32;mounted++;return fail_mount;}
int fs_unmount(struct fs_mount_t *m){assert(m==&mountpoint);unmounted++;return fail_unmount;}
int fs_statvfs(const char *p,struct fs_statvfs *s){assert(!strcmp(p,"/SD:"));*s=stats;return fail_stat;}
int disk_access_ioctl(const char *p,unsigned char op,void *arg){assert(!strcmp(p,"SD"));assert(op==DISK_IOCTL_GET_SECTOR_COUNT || op==DISK_IOCTL_GET_SECTOR_SIZE);if(fail_geometry==op)return -EIO;*(uint32_t *)arg=op==DISK_IOCTL_GET_SECTOR_COUNT?sectors:sector_bytes;return 0;}
int fs_opendir(struct fs_dir_t *d,const char *p){assert(!strcmp(p,"/SD:") && !d->valid);opened++;d->valid=1;return fail_open;}
int fs_readdir(struct fs_dir_t *d,struct fs_dirent *entry){assert(d->valid);reads++;if(fail_read && reads==2)return fail_read;if(reads<=available){strcpy(entry->name,"PRIVATE-NAME-NEVER-LOGGED");entry->type=(reads%2)?FS_DIR_ENTRY_FILE:FS_DIR_ENTRY_DIR;}return 0;}
int fs_closedir(struct fs_dir_t *d){assert(d->valid);d->valid=0;closed++;return fail_close;}
static void reset(void){mounted=unmounted=opened=closed=reads=0;fail_mount=fail_open=fail_read=fail_close=fail_unmount=fail_geometry=0;fail_stat=-ENOTSUP;available=0;sectors=16000;sector_bytes=512;stats=(struct fs_statvfs){4096,1000,700};}
struct stopping {unsigned calls,at;int code;};
static int stop(void *ctx){struct stopping *s=ctx;return ++s->calls>=s->at?s->code:0;}
int main(void){
 struct p4_sd_probe_result r;
 CHECK(p4_sd_readonly_probe(NULL)==-EINVAL);
 const unsigned counts[]={0,1,32,33,500};
 for(unsigned i=0;i<5;i++){
  reset();available=counts[i];CHECK(!p4_sd_readonly_probe(&r));
  CHECK(r.card_bytes==8192000 && !r.free_space_available && r.free_space_error==-ENOTSUP && !r.free_bytes);
  CHECK(r.filesystem_type==FS_FAT32);
  CHECK(r.entries==(available<32?available:32));CHECK(r.truncated==(available>32));
  CHECK(r.files+r.directories==r.entries);CHECK(reads==(available<33?available+1:33));
  CHECK(mounted==1 && unmounted==1 && opened==1 && closed==1);
 }
 reset();fail_mount=-ENODEV;CHECK(p4_sd_readonly_probe(&r)==-ENODEV);CHECK(!unmounted && !opened);
 reset();fail_mount=-ENOENT;CHECK(p4_sd_readonly_probe(&r)==-ENOENT);CHECK(!unmounted && !opened);
 reset();fail_stat=-EIO;CHECK(p4_sd_readonly_probe(&r)==-EIO);CHECK(unmounted==1 && !opened && !closed);
 reset();fail_open=-EMFILE;CHECK(p4_sd_readonly_probe(&r)==-EMFILE);CHECK(unmounted==1 && !closed);
 reset();fail_read=-EIO;available=9;CHECK(p4_sd_readonly_probe(&r)==-EIO);CHECK(closed==1 && unmounted==1 && reads==2);
 reset();fail_close=-EIO;CHECK(p4_sd_readonly_probe(&r)==-EIO);CHECK(r.close_error==-EIO && unmounted==1);
 reset();fail_unmount=-EBUSY;CHECK(p4_sd_readonly_probe(&r)==-EBUSY);CHECK(r.unmount_error==-EBUSY && closed==1);
 reset();available=9;fail_read=-EIO;fail_close=-EBADF;fail_unmount=-EBUSY;
 CHECK(p4_sd_readonly_probe(&r)==-EIO);CHECK(r.close_error==-EBADF && r.unmount_error==-EBUSY);
 reset();sectors=0;CHECK(p4_sd_readonly_probe(&r)==-EOVERFLOW);CHECK(unmounted==1 && !opened);
 reset();sector_bytes=0;CHECK(p4_sd_readonly_probe(&r)==-EOVERFLOW);CHECK(unmounted==1 && !opened);
 for(int op=1;op<=2;op++){reset();fail_geometry=op;CHECK(p4_sd_readonly_probe(&r)==-EIO);CHECK(unmounted==1 && !opened);}
 reset();fail_stat=0;CHECK(!p4_sd_readonly_probe(&r));CHECK(r.free_space_available && r.free_bytes==2867200 && r.filesystem_bytes==4096000);
 reset();fail_stat=0;stats.f_frsize=0;CHECK(p4_sd_readonly_probe(&r)==-EOVERFLOW);CHECK(unmounted==1 && !opened);
 reset();fail_stat=0;stats.f_bfree=1001;CHECK(p4_sd_readonly_probe(&r)==-EOVERFLOW);CHECK(unmounted==1 && !opened);
 reset();fail_stat=0;stats.f_frsize=UINT64_MAX;stats.f_blocks=2;stats.f_bfree=1;
 CHECK(p4_sd_readonly_probe(&r)==-EOVERFLOW);CHECK(unmounted==1 && !opened);
 reset();fail_stat=0;sectors=1;CHECK(p4_sd_readonly_probe(&r)==-EOVERFLOW);CHECK(unmounted==1 && !opened);
 for(unsigned i=0;i<5;i++){reset();CHECK(!p4_sd_readonly_probe(&r));CHECK(!r.entries && !r.error && unmounted==1);}
 for(unsigned at=1;at<=10;at++)for(unsigned mode=0;mode<2;mode++){
  reset();available=3;struct stopping s={0,at,mode?-ETIMEDOUT:-ECANCELED};
  CHECK(p4_sd_readonly_probe_controlled(&r,stop,&s)==s.code);CHECK(r.error==s.code);
  CHECK(mounted==(at==1?0u:1u));CHECK(unmounted==mounted);CHECK(closed==opened);CHECK(reads<=4);
 }
 printf("{\\"checks\\":%u,\\"max_root_reads\\":33,\\"file_content_reads\\":0,\\"writes\\":0}\\n",checks);
}
''')
flags=['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-fno-pie','-no-pie',
       '-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(inc),'-I'+str(source)]
binary=out/'test'
subprocess.run(flags+['-DCONFIG_FS_FATFS_READ_ONLY=1',str(test),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,check=True,timeout=20,
                   env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(run.stdout)
for name,defines in [('not-read-only',[]),('mkfs',['-DCONFIG_FS_FATFS_READ_ONLY=1','-DCONFIG_FS_FATFS_MKFS=1']),('auto-format',['-DCONFIG_FS_FATFS_READ_ONLY=1','-DCONFIG_FS_FATFS_MOUNT_MKFS=1'])]:
    r=subprocess.run(flags+defines+['-c',str(source/'probe.c'),'-o',str(out/'rejected.o')],capture_output=True,text=True)
    assert r.returncode and 'requires read-only FatFs' in r.stderr,name
report.update(result='PASS',scope='actual probe with synthetic filesystem; no card/device access',
              rejected_unsafe_configurations=3,sanitizers=['address','undefined'],physical_tested=False)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
