/* SPDX-License-Identifier: MIT */
#include "probe.h"
#include <errno.h>
#include <string.h>
#include <zephyr/fs/fs.h>
#include <zephyr/storage/disk_access.h>
#include <ff.h>
#if (!defined(CONFIG_FS_FATFS_READ_ONLY) && !defined(CONFIG_P4_SD_FILES)) || defined(CONFIG_FS_FATFS_MKFS) || defined(CONFIG_FS_FATFS_MOUNT_MKFS)
#error "SD probe requires read-only FatFs with all formatting disabled"
#endif
static FATFS filesystem;
static struct fs_mount_t mountpoint={
 .type=FS_FATFS,.mnt_point="/SD:",.fs_data=&filesystem,
 .flags=FS_MOUNT_FLAG_READ_ONLY|FS_MOUNT_FLAG_NO_FORMAT
};
int p4_sd_readonly_probe_controlled(struct p4_sd_probe_result *r,int (*stop)(void *),void *context)
{
 if(!r)return -EINVAL;
 memset(r,0,sizeof(*r));
 int e=stop?stop(context):0;
 if(e){r->error=e;return e;}
 e=fs_mount(&mountpoint);
 if(e){r->error=e;return e;}
 struct fs_statvfs stat={0};
 struct fs_dir_t directory;fs_dir_t_init(&directory);
 bool opened=false;
 uint32_t sectors=0,sector_bytes=0;
 r->filesystem_type=filesystem.fs_type;
 if(r->filesystem_type<FS_FAT12||r->filesystem_type>FS_FAT32){e=-ENOTSUP;goto cleanup;}
 if(stop && (e=stop(context)))goto cleanup;
 e=disk_access_ioctl("SD",DISK_IOCTL_GET_SECTOR_COUNT,&sectors);
 if(e)goto cleanup;
 if(stop && (e=stop(context)))goto cleanup;
 e=disk_access_ioctl("SD",DISK_IOCTL_GET_SECTOR_SIZE,&sector_bytes);
 if(e)goto cleanup;
 if(!sectors || !sector_bytes){e=-EOVERFLOW;goto cleanup;}
 r->card_bytes=(uint64_t)sectors*sector_bytes;
 if(stop && (e=stop(context)))goto cleanup;
#if defined(CONFIG_P4_SD_FILES)
 /* f_getfree may scan the entire FAT on writable builds. This metadata check
  * deliberately keeps its former scope instead of silently adding that work. */
 e=-ENOTSUP;
#else
 e=fs_statvfs("/SD:",&stat);
#endif
 r->free_space_error=e;
 /* Pinned FatFs deliberately excludes f_getfree when FF_FS_READONLY=1. */
 if(e && e!=-ENOTSUP)goto cleanup;
 if(!e){
 if(!stat.f_frsize || stat.f_bfree>stat.f_blocks ||
    (uint64_t)stat.f_blocks>UINT64_MAX/(uint64_t)stat.f_frsize){e=-EOVERFLOW;goto cleanup;}
 r->filesystem_bytes=(uint64_t)stat.f_frsize*stat.f_blocks;
 if(r->filesystem_bytes>r->card_bytes){e=-EOVERFLOW;goto cleanup;}
 r->free_bytes=(uint64_t)stat.f_frsize*stat.f_bfree;
 r->free_space_available=true;
 }
 if(stop && (e=stop(context)))goto cleanup;
 e=fs_opendir(&directory,"/SD:");
 if(e)goto cleanup;
 opened=true;
 for(unsigned i=0;i<=32;i++){
  if(stop && (e=stop(context)))break;
  struct fs_dirent entry={0};e=fs_readdir(&directory,&entry);
  if(e || !entry.name[0])break;
  if(i==32){r->truncated=true;break;}
  r->entries++;
  if(entry.type==FS_DIR_ENTRY_DIR)r->directories++;
  else if(entry.type==FS_DIR_ENTRY_FILE)r->files++;
 }
 if(!e && stop)e=stop(context);
cleanup:
 if(opened){r->close_error=fs_closedir(&directory);if(!e)e=r->close_error;}
 r->unmount_error=fs_unmount(&mountpoint);if(!e)e=r->unmount_error;
 r->error=e;return e;
}
int p4_sd_readonly_probe(struct p4_sd_probe_result *r)
{return p4_sd_readonly_probe_controlled(r,NULL,NULL);}
