/* SPDX-License-Identifier: MIT */
#include "sd_file_io.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/fs/fs.h>
#include <ff.h>
#if !defined(CONFIG_P4_SD_FILES) || defined(CONFIG_FS_FATFS_READ_ONLY) || defined(CONFIG_FS_FATFS_MKFS) || defined(CONFIG_FS_FATFS_MOUNT_MKFS)
#error "SD files require the explicit writable profile with all formatting disabled"
#endif
/* No long filenames, shared VFS users or other SD filesystem owner in this
 * profile. f_open(FA_CREATE_NEW) supplies semantics missing in fs_open flags.
 * Mount lifecycle stays in Zephyr. Direct FatFs access never renames/replaces
 * an existing file. The kernel SDMMC transaction mutex arbitrates C6 slot1. */
static FATFS file_system;
static struct fs_mount_t file_mount={
    .type=FS_FATFS,.mnt_point="/SD:",.fs_data=&file_system,
    .flags=FS_MOUNT_FLAG_NO_FORMAT
};
static int translated(FRESULT r) {
    switch(r) {
    case FR_OK:return 0;
    case FR_EXIST:return -EEXIST;
    case FR_NO_FILE:case FR_NO_PATH:return -ENOENT;
    case FR_WRITE_PROTECTED:return -EROFS;
    case FR_DENIED:return -ENOSPC;
    case FR_NOT_READY:return -ENODEV;
    case FR_TIMEOUT:return -ETIMEDOUT;
    case FR_INVALID_NAME:return -EINVAL;
    default:return -EIO;
    }
}
static int native(mb_sd_file_result *r,FRESULT fr) {
    if(fr)r->native_result=(int)fr;
    return translated(fr);
}
static int stopped(int (*stop)(void *),void *context) {return stop?stop(context):0;}
int p4_sd_file_io(mb_sd_file_op op,const char *name,const uint8_t *input,
                 size_t expected,uint8_t *output,mb_sd_file_result *r,
                 int (*stop)(void *),void *context) {
    if(!r)return -EINVAL;
    memset(r,0,sizeof(*r));
    size_t n=0;if(name)while(n<MB_SD_NAME_BYTES&&name[n])n++;
    if((op!=MB_SD_FILE_LIST&&!mb_sd_file_name(name,n))||expected>MB_SD_FILE_BYTES||!output||
       (op!=MB_SD_FILE_READ&&op!=MB_SD_FILE_CREATE&&op!=MB_SD_FILE_REMOVE_OWN&&op!=MB_SD_FILE_LIST)||
       ((op==MB_SD_FILE_CREATE||op==MB_SD_FILE_REMOVE_OWN)&&!input&&expected))return r->error=-EINVAL;
    int e=stopped(stop,context);if(e)return r->error=e;
    e=fs_mount(&file_mount);if(e)return r->error=e;
    char path[32];snprintf(path,sizeof(path),"SD:/MBFILES/%s",name);
    FIL file;bool opened=false;
    DIR directory;bool directory_open=false;
    /* These objects and every DMA-facing partial-sector buffer stay on the
     * worker's checked internal stack, not in PSRAM staging. */
    uint8_t bounce[512] __attribute__((aligned(64)));
    if(file_system.fs_type<FS_FAT12||file_system.fs_type>FS_FAT32){e=-ENOTSUP;goto cleanup;}
    e=stopped(stop,context);if(e)goto cleanup;
    if(op==MB_SD_FILE_LIST) {
        FRESULT fr=f_opendir(&directory,"SD:/MBFILES");
        if(fr==FR_NO_PATH||fr==FR_NO_FILE){output[0]=0;r->bytes=1;r->verified=true;goto cleanup;}
        e=native(r,fr);if(e)goto cleanup;
        directory_open=true;unsigned files=0;size_t used=1;output[0]=0;
        for(unsigned i=0;i<=32;i++) {
            e=stopped(stop,context);if(e)goto cleanup;
            FILINFO info;e=native(r,f_readdir(&directory,&info));if(e)goto cleanup;
            if(!info.fname[0])break;
            if(i==32){r->truncated=true;break;}
            if(info.fattrib&AM_DIR)continue;
            size_t size=0;while(size<MB_SD_NAME_BYTES&&info.fname[size])size++;
            if(!mb_sd_file_name(info.fname,size))continue;
            if(files==8){r->truncated=true;break;}
            uint32_t bytes=(uint32_t)info.fsize;
            for(unsigned k=0;k<4;k++)output[used++]=(uint8_t)(bytes>>(8*k));
            output[used++]=(uint8_t)size;memcpy(output+used,info.fname,size);used+=size;files++;
        }
        output[0]=(uint8_t)files;r->bytes=used;r->verified=true;goto cleanup;
    }
    if(op==MB_SD_FILE_CREATE) {
        FILINFO info;FRESULT fr=f_stat("SD:/MBFILES",&info);
        if(fr==FR_NO_FILE||fr==FR_NO_PATH) {
            e=stopped(stop,context);if(e)goto cleanup;
            e=native(r,f_mkdir("SD:/MBFILES"));if(e)goto cleanup;
        } else if(fr!=FR_OK) {e=native(r,fr);goto cleanup;}
        else if(!(info.fattrib&AM_DIR)){e=-ENOTDIR;goto cleanup;}
        e=stopped(stop,context);if(e)goto cleanup;
        e=native(r,f_open(&file,path,FA_CREATE_NEW|FA_WRITE));
        if(e)goto cleanup;
        opened=true;r->created=true;
        for(size_t offset=0;offset<expected;) {
            e=stopped(stop,context);if(e)goto cleanup;
            size_t part=expected-offset;if(part>sizeof(bounce))part=sizeof(bounce);
            memcpy(bounce,input+offset,part);UINT written=0;
            e=native(r,f_write(&file,bounce,(UINT)part,&written));
            r->bytes+=written;
            if(e)goto cleanup;
            if(written!=part){e=-ENOSPC;goto cleanup;}
            offset+=part;
        }
        e=stopped(stop,context);if(e)goto cleanup;
        e=native(r,f_sync(&file));if(e)goto cleanup;
        r->synced=true;
        r->close_error=translated(f_close(&file));opened=false;
        if(r->close_error){e=r->close_error;goto cleanup;}
    }
    e=stopped(stop,context);if(e)goto cleanup;
    e=native(r,f_open(&file,path,FA_READ|FA_OPEN_EXISTING));if(e)goto cleanup;
    opened=true;
    size_t length=(size_t)f_size(&file);
    if(length>MB_SD_FILE_BYTES){e=-EFBIG;goto cleanup;}
    if(op!=MB_SD_FILE_READ&&length!=expected){e=-ESTALE;goto cleanup;}
    for(size_t offset=0;offset<length;) {
        e=stopped(stop,context);if(e)goto cleanup;
        size_t part=length-offset;if(part>sizeof(bounce))part=sizeof(bounce);
        UINT count=0;e=native(r,f_read(&file,bounce,(UINT)part,&count));
        if(e)goto cleanup;
        if(count!=part){e=-EIO;goto cleanup;}
        if(op!=MB_SD_FILE_READ&&memcmp(bounce,input+offset,part)){e=-ESTALE;goto cleanup;}
        memcpy(output+offset,bounce,part);offset+=part;
    }
    e=stopped(stop,context);if(e)goto cleanup;
    r->close_error=translated(f_close(&file));opened=false;
    if(r->close_error){e=r->close_error;goto cleanup;}
    r->bytes=length;r->verified=true;
    if(op==MB_SD_FILE_REMOVE_OWN) {
        e=stopped(stop,context);if(e)goto cleanup;
        e=native(r,f_unlink(path));if(e)goto cleanup;
        r->removed=true;
        FILINFO info;FRESULT fr=f_stat(path,&info);
        if(fr!=FR_NO_FILE){e=fr==FR_OK?-EIO:native(r,fr);goto cleanup;}
    }
cleanup:
    if(opened){int close=translated(f_close(&file));if(!r->close_error)r->close_error=close;if(!e)e=close;}
    if(directory_open){int close=translated(f_closedir(&directory));if(!r->close_error)r->close_error=close;if(!e)e=close;}
    r->unmount_error=fs_unmount(&file_mount);if(!e)e=r->unmount_error;
    memset(bounce,0,sizeof(bounce));r->error=e;return e;
}
