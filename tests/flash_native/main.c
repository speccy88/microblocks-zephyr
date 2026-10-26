/* SPDX-License-Identifier: MIT */
#include "zephyr_flash.h"
#include <zephyr/ztest.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/storage/flash_map.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(lfs);
static struct fs_mount_t mount={.type=FS_LITTLEFS,.fs_data=&lfs,
    .storage_dev=(void *)PARTITION_ID(mb_test_flash),.mnt_point="/mbflash",
    .flags=FS_MOUNT_FLAG_NO_FORMAT};
static mb_flash_zephyr port={.mount=&mount};
static mb_flash store;
static uint8_t payload[MB_FLASH_BYTES],copy[1024];
static uint32_t revision;
#define OK(x) zassert_equal((x),0,"%s",#x)

static void fresh(void *unused) {
    (void)unused;
    if(store.mounted)OK(mb_flash_unmount(&store));
    port.fault=0;
    /* Only this guarded native_sim fixture has any formatting operation. */
    OK(fs_mkfs(FS_LITTLEFS,PARTITION_ID(mb_test_flash),NULL,0));
    mb_flash_init(&store,&mb_flash_zephyr_port,&port);OK(mb_flash_mount(&store));
    for(unsigned i=0;i<sizeof(payload);i++)payload[i]=(uint8_t)i;
}
static void remount(void) {OK(mb_flash_unmount(&store));mb_flash_init(&store,&mb_flash_zephyr_port,&port);OK(mb_flash_mount(&store));}
static uint32_t put(const char *p,uint32_t expected,const uint8_t *data,size_t n) {
    uint32_t rev;OK(mb_flash_put(&store,p,strlen(p),expected,data,n,&rev));return rev;
}
static void check(const char *p,const uint8_t *data,size_t n) {
    mb_flash_file f;OK(mb_flash_stat(&store,p,strlen(p),&f));zassert_equal(f.bytes,n);
    for(size_t off=0;off<n;) {
        size_t bytes=n-off;if(bytes>sizeof(copy))bytes=sizeof(copy);
        OK(mb_flash_read(&store,p,strlen(p),f.revision,off,copy,bytes));
        zassert_mem_equal(copy,data+off,bytes);off+=bytes;
    }
}
ZTEST(flashlocal,test_empty_utf8_binary_remount) {
    put("/Flash/empty",0,NULL,0);
    static const uint8_t text[]="Bonjour UTF-8: \xc3\xa9\n";
    put("/Flash/text",0,text,sizeof(text)-1);
    put("/Flash/sub/data.bin",0,payload,sizeof(payload));
    remount();check("/Flash/empty",NULL,0);check("/Flash/text",text,sizeof(text)-1);
    check("/Flash/sub/data.bin",payload,sizeof(payload));
    mb_flash_file files[8];size_t count=0;
    OK(mb_flash_list(&store,files,8,&count));zassert_equal(count,3);
    zassert_equal(mb_flash_list(&store,files,2,&count),-ENOBUFS);
    mb_flash_file empty;OK(mb_flash_stat(&store,"/Flash/empty",12,&empty));
    OK(mb_flash_read(&store,"/Flash/empty",12,empty.revision,0,NULL,0));
}
ZTEST(flashlocal,test_quota_and_full_replace) {
    char path[32];for(unsigned i=0;i<8;i++){snprintf(path,sizeof(path),"/Flash/f%u",i);put(path,0,payload,sizeof(payload));}
    uint32_t used;unsigned slots;uint64_t total,free;
    OK(mb_flash_capacity(&store,&used,&slots,&total,&free));
    zassert_equal(used,65536);zassert_equal(slots,0);zassert_true(total>=free&&total>65536);
    zassert_equal(mb_flash_put(&store,"/Flash/overflow",15,0,NULL,0,&revision),-ENOSPC);
    zassert_equal(mb_flash_put(&store,"/Flash/huge",11,0,payload,8193,&revision),-EFBIG);
    mb_flash_file f;OK(mb_flash_stat(&store,"/Flash/f0",9,&f));
    for(unsigned i=0;i<16;i++)f.revision=put("/Flash/f0",f.revision,payload,sizeof(payload));
    remount();check("/Flash/f0",payload,sizeof(payload));
}
ZTEST(flashlocal,test_revision_restart_delete_recreate) {
    uint32_t a=put("/Flash/a",0,(const uint8_t *)"old",3);remount();
    zassert_equal(mb_flash_put(&store,"/Flash/a",8,0,NULL,0,&revision),-EEXIST);
    uint32_t b=put("/Flash/a",a,(const uint8_t *)"new",3);zassert_true(b>a);
    zassert_equal(mb_flash_read(&store,"/Flash/a",8,a,0,copy,3),-ESTALE);
    zassert_equal(mb_flash_delete(&store,"/Flash/a",8,a),-ESTALE);
    OK(mb_flash_delete(&store,"/Flash/a",8,b));remount();
    uint32_t c=put("/Flash/a",0,(const uint8_t *)"last",4);zassert_true(c>b);
    zassert_equal(mb_flash_put(&store,"/Flash/a",8,b,NULL,0,&revision),-ESTALE);
    check("/Flash/a",(const uint8_t *)"last",4);
}
ZTEST(flashlocal,test_paths_bounds_busy) {
    const char *bad[]={"/RAM/a","/SD/a","/Flash/../a","/Flash/.hidden","/Flash/a\\b",
        "/Flash/a%2fb","/Flash/a/b/c/d/e","/Flash/a/","/Flash//a","/settings/password","/Flash/a:b","/Flash/"};
    for(unsigned i=0;i<ARRAY_SIZE(bad);i++)zassert_false(mb_flash_path(bad[i],strlen(bad[i])));
    zassert_false(mb_flash_path("/Flash/a\0b",10));
    zassert_true(mb_flash_path("/Flash/a/b/c/d.json",18));
    uint32_t rev=put("/Flash/a",0,payload,4);
    zassert_equal(mb_flash_read(&store,"/Flash/a",8,rev,SIZE_MAX,copy,1),-EINVAL);
    zassert_equal(mb_flash_read(&store,"/Flash/a",8,rev,0,copy,1025),-EINVAL);
    store.busy=true;
    zassert_equal(mb_flash_put(&store,"/Flash/b",8,0,NULL,0,&revision),-EBUSY);
    zassert_equal(mb_flash_unmount(&store),-EBUSY);store.busy=false;
    uint32_t x=1;char path[64];
    for(unsigned trial=0;trial<10000;trial++) {
        for(unsigned j=0;j<sizeof(path);j++){x=x*1664525u+1013904223u;path[j]=(char)(x>>24);}
        zassert_false(mb_flash_path(path,trial%65));
    }
}
ZTEST(flashlocal,test_faults_and_atomic_outcomes) {
    const unsigned faults[]={MB_FS_SHORT,MB_FS_WRITE,MB_FS_SYNC,MB_FS_CLOSE,MB_FS_RENAME_BEFORE,MB_FS_RENAME_AFTER};
    for(unsigned key=0;key<=1;key++)for(unsigned j=0;j<ARRAY_SIZE(faults);j++) {
        fresh(NULL);uint32_t rev=put("/Flash/a",0,(const uint8_t *)"old",3);
        port.fault=faults[j];port.fault_key=key;
        zassert_true(mb_flash_put(&store,"/Flash/a",8,rev,(const uint8_t *)"new",3,&revision)<0);
        zassert_false(store.ready);zassert_equal(port.fault,0);
        zassert_equal(mb_flash_put(&store,"/Flash/b",8,0,NULL,0,&revision),-ENODEV);
        remount();
        bool committed=key==1&&faults[j]==MB_FS_RENAME_AFTER;
        check("/Flash/a",(const uint8_t *)(committed?"new":"old"),3);
        mb_flash_file f;OK(mb_flash_stat(&store,"/Flash/a",8,&f));
        uint32_t next=put("/Flash/a",f.revision,(const uint8_t *)"next",4);zassert_true(next>rev);
    }
}
ZTEST(flashlocal,test_read_remove_and_counter_fail_closed) {
    uint32_t rev=put("/Flash/a",0,payload,8);port.fault_key=1;port.fault=MB_FS_READ;
    zassert_equal(mb_flash_read(&store,"/Flash/a",8,rev,0,copy,8),-EIO);zassert_false(store.ready);
    remount();port.fault=MB_FS_REMOVE;
    zassert_equal(mb_flash_delete(&store,"/Flash/a",8,rev),-EIO);remount();check("/Flash/a",payload,8);
    store.sequence=MB_FLASH_REV_MAX;
    zassert_equal(mb_flash_put(&store,"/Flash/b",8,0,NULL,0,&revision),-EOVERFLOW);
    remount();check("/Flash/a",payload,8);
}
static void raw(const char *path,const uint8_t *data,size_t n) {
    struct fs_file_t f;fs_file_t_init(&f);OK(fs_open(&f,path,FS_O_CREATE|FS_O_WRITE|FS_O_TRUNC));
    zassert_equal(fs_write(&f,data,n),(ssize_t)n);OK(fs_sync(&f));OK(fs_close(&f));
}
ZTEST(flashlocal,test_corrupt_unknown_and_missing_sequence) {
    put("/Flash/a",0,payload,8);raw("/mbflash/slot0",(const uint8_t *)"bad",3);
    OK(mb_flash_unmount(&store));zassert_equal(mb_flash_mount(&store),-EILSEQ);
    fresh(NULL);raw("/mbflash/unknown",payload,1);
    OK(mb_flash_unmount(&store));zassert_equal(mb_flash_mount(&store),-EILSEQ);
    fresh(NULL);put("/Flash/a",0,payload,8);OK(fs_unlink("/mbflash/seq"));
    OK(mb_flash_unmount(&store));zassert_equal(mb_flash_mount(&store),-EILSEQ);
    fresh(NULL);put("/Flash/a",0,payload,8);size_t size=0;
    OK(mb_flash_zephyr_port.read(&port,1,payload,sizeof(payload),&size));
    payload[80]^=1;raw("/mbflash/slot0",payload,size); /* valid header, bad payload CRC */
    OK(mb_flash_unmount(&store));zassert_equal(mb_flash_mount(&store),-EILSEQ);
    fresh(NULL);put("/Flash/a",0,payload,8);
    OK(mb_flash_zephyr_port.read(&port,1,payload,sizeof(payload),&size));
    raw("/mbflash/slot1",payload,size); /* valid CRC, duplicate path/revision */
    OK(mb_flash_unmount(&store));zassert_equal(mb_flash_mount(&store),-EILSEQ);
    fresh(NULL);put("/Flash/a",0,payload,8);
    OK(mb_flash_zephyr_port.read(&port,0,copy,sizeof(copy),&size));
    copy[8]^=1;raw("/mbflash/seq",copy,size); /* sequence corruption, never repair/reuse */
    OK(mb_flash_unmount(&store));zassert_equal(mb_flash_mount(&store),-EILSEQ);
}
ZTEST(flashlocal,test_no_autoformat_blank_or_corrupt) {
    OK(mb_flash_unmount(&store));const struct flash_area *area;
    OK(flash_area_open(PARTITION_ID(mb_test_flash),&area));OK(flash_area_erase(area,0,area->fa_size));
    for(unsigned pass=0;pass<2;pass++) {
        if(pass){memset(copy,0,sizeof(copy));OK(flash_area_write(area,0,copy,sizeof(copy)));}
        zassert_true(mb_flash_mount(&store)<0);zassert_false(store.ready);
        zassert_true(mount.flags&FS_MOUNT_FLAG_NO_FORMAT);
        for(size_t off=0;off<area->fa_size;off+=sizeof(copy)) {
            OK(flash_area_read(area,off,copy,sizeof(copy)));
            for(unsigned i=0;i<sizeof(copy);i++)zassert_equal(copy[i],pass&&off==0?0:255);
        }
    }
    flash_area_close(area);
}
ZTEST(flashlocal,test_filesystem_full_preserves_previous) {
    uint32_t rev=put("/Flash/a",0,(const uint8_t *)"old",3);
    struct fs_file_t file;fs_file_t_init(&file);OK(fs_open(&file,"/mbflash/filler",FS_O_CREATE|FS_O_WRITE));
    int e=0;for(unsigned i=0;i<300;i++) {
        ssize_t n=fs_write(&file,payload,sizeof(payload));if(n<0){e=(int)n;break;}
        e=fs_sync(&file);if(e)break;
    }
    zassert_equal(e,-ENOSPC);(void)fs_close(&file);
    zassert_true(mb_flash_put(&store,"/Flash/a",8,rev,payload,sizeof(payload),&revision)<0);
    zassert_false(store.ready);
    /* Test-only raw filler removal; never a service recovery/autoformat path. */
    OK(fs_unlink("/mbflash/filler"));remount();check("/Flash/a",(const uint8_t *)"old",3);
}
ZTEST(flashlocal,test_memory_sizes) {
    size_t unused=0;OK(k_thread_stack_space_get(k_current_get(),&unused));
    printk("MB_FLASH_MEMORY store=%zu port=%zu littlefs=%zu mount=%zu caches=%u test_thread_unused=%zu\n",
        sizeof(store),sizeof(port),sizeof(lfs),sizeof(mount),
        2*CONFIG_FS_LITTLEFS_CACHE_SIZE+CONFIG_FS_LITTLEFS_LOOKAHEAD_SIZE,unused);
}
ZTEST_SUITE(flashlocal,NULL,NULL,fresh,NULL,NULL);

/* Run each of these in separate native_sim processes using the SAME test image. */
ZTEST(persist,test_seed) {
    fresh(NULL);put("/Flash/restart",0,(const uint8_t *)"process persistence",19);
    OK(mb_flash_unmount(&store));
}
ZTEST(persist,test_verify) {
    mb_flash_init(&store,&mb_flash_zephyr_port,&port);OK(mb_flash_mount(&store));
    check("/Flash/restart",(const uint8_t *)"process persistence",19);
    mb_flash_file f;OK(mb_flash_stat(&store,"/Flash/restart",14,&f));zassert_equal(f.revision,1);
    uint32_t r=put("/Flash/restart",f.revision,(const uint8_t *)"after restart",13);zassert_equal(r,2);
    OK(mb_flash_unmount(&store));
}
ZTEST_SUITE(persist,NULL,NULL,NULL,NULL,NULL);
