/* SPDX-License-Identifier: MIT */
#include "zephyr_flash.h"
#include <errno.h>
#include <string.h>

/* Internal names are fixed; untrusted logical paths never reach VFS. */
static const char *const paths[]={"/mbflash/seq","/mbflash/slot0","/mbflash/slot1",
    "/mbflash/slot2","/mbflash/slot3","/mbflash/slot4","/mbflash/slot5","/mbflash/slot6","/mbflash/slot7"};
static const char tmp[]="/mbflash/.mbtmp";
static bool fault(mb_flash_zephyr *p,unsigned key,unsigned code) {
#ifdef CONFIG_ZTEST
    if(p->fault==code&&p->fault_key==key){p->fault=0;return true;}
#else
    (void)p;(void)key;(void)code;
#endif
    return false;
}
#ifndef CONFIG_ZTEST
enum { MB_FS_SHORT=1, MB_FS_WRITE, MB_FS_SYNC, MB_FS_CLOSE,
       MB_FS_RENAME_BEFORE, MB_FS_RENAME_AFTER, MB_FS_READ, MB_FS_REMOVE };
#endif
static int mount_port(void *context) {
    mb_flash_zephyr *p=context;
    if(!p||!p->mount||p->mount->type!=FS_LITTLEFS||
       !p->mount->mnt_point||strcmp(p->mount->mnt_point,"/mbflash"))return -EINVAL;
    /* Never inherit Zephyr's optional automatic formatting behavior. */
    p->mount->flags|=FS_MOUNT_FLAG_NO_FORMAT;
    int e=fs_mount(p->mount);if(e)return e;
    struct fs_dir_t dir;struct fs_dirent ent;fs_dir_t_init(&dir);
    e=fs_opendir(&dir,"/mbflash");
    if(!e) {
        unsigned count=0;
        for(;;) {
            e=fs_readdir(&dir,&ent);if(e||!ent.name[0])break;
            bool known=!strcmp(ent.name,".mbtmp");
            for(unsigned i=0;i<9;i++)if(!strcmp(ent.name,paths[i]+9))known=true;
            if(++count>10||ent.type!=FS_DIR_ENTRY_FILE||!known){e=-EILSEQ;break;}
        }
        int c=fs_closedir(&dir);if(!e)e=c;
    }
    if(e) {int u=fs_unmount(p->mount);return u?u:e;}
    return 0;
}
static int unmount_port(void *context) {
    return fs_unmount(((mb_flash_zephyr *)context)->mount);
}
static int read_port(void *context,unsigned key,uint8_t *out,size_t cap,size_t *size) {
    mb_flash_zephyr *p=context;
    if(key>=9||!out||!size)return -EINVAL;
    if(fault(p,key,MB_FS_READ))return -EIO;
    struct fs_dirent ent;int e=fs_stat(paths[key],&ent);if(e)return e;
    if(ent.type!=FS_DIR_ENTRY_FILE||ent.size>cap)return -EFBIG;
    struct fs_file_t file;fs_file_t_init(&file);
    e=fs_open(&file,paths[key],FS_O_READ);if(e)return e;
    size_t got=0;
    while(got<ent.size) {
        size_t n=ent.size-got;if(n>1024)n=1024;
        ssize_t r=fs_read(&file,out+got,n);
        if(r<=0){e=r<0?(int)r:-EIO;break;}
        got+=(size_t)r;
    }
    if(!e) {uint8_t extra;ssize_t r=fs_read(&file,&extra,1);if(r)e=r<0?(int)r:-EFBIG;}
    int c=fs_close(&file);if(!e)e=c;
    if(!e)*size=got;
    return e;
}
static int replace_port(void *context,unsigned key,const uint8_t *data,size_t size) {
    mb_flash_zephyr *p=context;
    if(key>=9||(!data&&size)||size>MB_FLASH_RECORD)return -EINVAL;
    struct fs_file_t file;fs_file_t_init(&file);
    int e=fs_open(&file,tmp,FS_O_CREATE|FS_O_WRITE|FS_O_TRUNC);if(e)return e;
    for(size_t at=0;at<size;) {
        size_t n=size-at;if(n>1024)n=1024;
        if(fault(p,key,MB_FS_WRITE)){e=-ENOSPC;break;}
        bool short_write=fault(p,key,MB_FS_SHORT);
        ssize_t r=fs_write(&file,data+at,short_write?n-1:n);
        if(r!=(ssize_t)n){e=r<0?(int)r:-EIO;break;}
        at+=n;
    }
    if(!e)e=fs_sync(&file);
    if(!e&&fault(p,key,MB_FS_SYNC))e=-EIO;
    int c=fs_close(&file);
    if(fault(p,key,MB_FS_CLOSE))c=-EIO;
    if(!e)e=c;
    if(e)return e; /* old target remains; no automatic mutation retry */
    if(fault(p,key,MB_FS_RENAME_BEFORE))return -EIO;
    e=fs_rename(tmp,paths[key]);
    if(!e&&fault(p,key,MB_FS_RENAME_AFTER))return -EIO;
    return e;
}
static int remove_port(void *context,unsigned key) {
    mb_flash_zephyr *p=context;
    if(key<1||key>=9)return -EINVAL;
    if(fault(p,key,MB_FS_REMOVE))return -EIO;
    return fs_unlink(paths[key]);
}
static int space_port(void *context,uint64_t *total,uint64_t *free) {
    (void)context;struct fs_statvfs stat;
    int e=fs_statvfs("/mbflash",&stat);if(e)return e;
    *total=(uint64_t)stat.f_frsize*stat.f_blocks;
    *free=(uint64_t)stat.f_frsize*stat.f_bfree;
    return 0;
}
const mb_flash_port mb_flash_zephyr_port={mount_port,unmount_port,read_port,replace_port,remove_port,space_port};
