/* SPDX-License-Identifier: MIT */
#include "sd_service.h"
#include "probe.h"
#include "sd_file.h"
#if defined(CONFIG_P4_SD_FILES)
#include "sd_file_io.h"
#endif
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/sys/atomic.h>
#include <esp_memory_utils.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

BUILD_ASSERT(DT_NODE_HAS_STATUS(DT_NODELABEL(sdhc0),okay),"SD slot0 must be enabled");
#if !defined(CONFIG_P4_SD_FILES)
BUILD_ASSERT(CONFIG_FS_FATFS_READ_ONLY,"This backend must not link FAT writes");
#endif
BUILD_ASSERT(!IS_ENABLED(CONFIG_FS_FATFS_MOUNT_MKFS),"Formatting is forbidden");
BUILD_ASSERT(CONFIG_DYNAMIC_THREAD_POOL_SIZE==0,"No hidden permanent stack reservation");
#define STACK_BYTES 4096
#define DEADLINE_MS 30000
struct sd_job {
    struct k_thread thread;
    k_thread_stack_t *stack;
    atomic_t cancelled;
    int64_t began,deadline;
    struct p4_sd_probe_result result;
#if defined(CONFIG_P4_SD_FILES)
    mb_sd_file_op operation;
    char name[MB_SD_NAME_BYTES];
    size_t length;
    mb_sd_file_result file_result;
#endif
};
/* The VM owns active. Only its worker accesses job.result until thread join.
 * These CPU-only report bytes never become disk/DMA buffers. */
static struct {
    struct sd_job *active;
    struct p4_sd_probe_result result;
    const char *phase;
    uint64_t elapsed;
    size_t unused_stack;
    int stack_error;
    bool attempted;
} sd_state __attribute__((section(".ext_ram.bss.sd_state"),aligned(16)));
#if defined(CONFIG_P4_SD_FILES)
/* VM-owned staging is immutable while the worker runs. Only the worker writes
 * output; only the joined VM reads it. No DMA/ISR sees these PSRAM bytes. */
static struct {
    uint8_t input[MB_SD_FILE_BYTES],output[MB_SD_FILE_BYTES];
    char name[MB_SD_NAME_BYTES];
    struct {uint8_t data[MB_SD_FILE_BYTES];char name[MB_SD_NAME_BYTES];size_t bytes;bool present;} owned[8];
    uint32_t generation;
    mb_sd_file_result result;
    bool finished;
} sd_files __attribute__((section(".ext_ram.bss.sd_files"),aligned(16)));
#endif

static int stop(void *context)
{
    struct sd_job *job=context;
    if(atomic_get(&job->cancelled))return -ECANCELED;
    return k_uptime_get()>=job->deadline?-ETIMEDOUT:0;
}
static void worker(void *a,void *b,void *c)
{
    ARG_UNUSED(b);ARG_UNUSED(c);
    struct sd_job *job=a;
#if defined(CONFIG_P4_SD_FILES)
    if(job->operation) {
        (void)p4_sd_file_io(job->operation,job->name,sd_files.input,job->length,
                           sd_files.output,&job->file_result,stop,job);
    } else
#endif
    (void)p4_sd_readonly_probe_controlled(&job->result,stop,job);
    /* Never abort this thread while an SD controller/filesystem lock is held. */
}
bool mb_sd_available(void)
{return device_is_ready(DEVICE_DT_GET(DT_NODELABEL(sdhc0)));}
void mb_sd_poll(void)
{
    struct sd_job *job=sd_state.active;
    if(!job||k_thread_join(&job->thread,K_NO_WAIT))return;
    sd_state.result=job->result;sd_state.elapsed=k_uptime_get()-job->began;
    sd_state.stack_error=k_thread_stack_space_get(&job->thread,&sd_state.unused_stack);
    /* A failed free keeps ownership so no second job can reuse a live stack. */
    int error=k_thread_stack_free(job->stack);
    if(error){sd_state.phase="stack release failed";sd_state.stack_error=error;return;}
#if defined(CONFIG_P4_SD_FILES)
    if(job->operation) {
        sd_files.result=job->file_result;sd_files.finished=true;
        if(!job->file_result.error) {
            if(job->operation==MB_SD_FILE_CREATE) {
                for(unsigned i=0;i<8;i++)if(!sd_files.owned[i].present) {
                    memcpy(sd_files.owned[i].data,sd_files.input,job->length);
                    memcpy(sd_files.owned[i].name,job->name,sizeof(job->name));
                    sd_files.owned[i].bytes=job->length;sd_files.owned[i].present=true;break;
                }
            } else if(job->operation==MB_SD_FILE_REMOVE_OWN) {
                for(unsigned i=0;i<8;i++)if(sd_files.owned[i].present&&!strcmp(sd_files.owned[i].name,job->name)) {
                    memset(&sd_files.owned[i],0,sizeof(sd_files.owned[i]));break;
                }
            }
        }
        sd_state.phase=job->file_result.error==-ECANCELED?"cancelled":
            job->file_result.error==-ETIMEDOUT?"deadline exceeded":
            job->file_result.error?"SD file operation failed":"SD file operation complete";
        sd_state.result.error=job->file_result.error;
        memset(sd_files.input,0,sizeof(sd_files.input));
        sd_state.active=NULL;k_free(job);return;
    }
#endif
    sd_state.active=NULL;k_free(job);
    sd_state.phase=sd_state.result.error==-ECANCELED?"cancelled":
        sd_state.result.error==-ETIMEDOUT?"deadline exceeded":
        sd_state.result.error?"probe failed":"read-only probe complete";
}
bool mb_sd_start(void)
{
    mb_sd_poll();
    if(sd_state.active)return false;
    if(!mb_sd_available()){sd_state.phase="SD controller unavailable";sd_state.result.error=-ENODEV;return false;}
    struct sd_job *job=k_calloc(1,sizeof(*job));
    if(!job){sd_state.phase="internal worker allocation failed";sd_state.result.error=-ENOMEM;return false;}
    job->stack=k_thread_stack_alloc(STACK_BYTES,0);
    if(!job->stack){k_free(job);sd_state.phase="internal stack allocation failed";sd_state.result.error=-ENOMEM;return false;}
    if(!esp_ptr_internal(job)||!esp_ptr_internal(job->stack)||
       !esp_ptr_internal((uint8_t *)job->stack+K_KERNEL_STACK_LEN(STACK_BYTES)-1)){
        (void)k_thread_stack_free(job->stack);k_free(job);
        sd_state.phase="internal stack memory required";sd_state.result.error=-EFAULT;return false;
    }
    job->began=k_uptime_get();job->deadline=job->began+DEADLINE_MS;
    sd_state.active=job;sd_state.attempted=true;sd_state.phase="reading SD; no file contents or writes";
    memset(&sd_state.result,0,sizeof(sd_state.result));sd_state.elapsed=0;
    k_thread_create(&job->thread,job->stack,STACK_BYTES,worker,job,NULL,NULL,9,0,K_NO_WAIT);
    k_thread_name_set(&job->thread,"sd_readonly");return true;
}
bool mb_sd_busy(void){mb_sd_poll();return sd_state.active!=NULL;}
void mb_sd_cancel(void){if(sd_state.active)atomic_set(&sd_state.active->cancelled,1);}
const char *mb_sd_phase(void){mb_sd_poll();return sd_state.phase?sd_state.phase:"Not checked yet";}
bool mb_sd_result(uint64_t *bytes,unsigned *entries)
{
    mb_sd_poll();
    if(sd_state.active||!sd_state.attempted||sd_state.result.error||!sd_state.result.card_bytes)return false;
    if(bytes)*bytes=sd_state.result.card_bytes;
    if(entries)*entries=sd_state.result.entries;
    return true;
}
void mb_sd_status(char *out,size_t size)
{
    mb_sd_poll();
    const struct p4_sd_probe_result *r=&sd_state.result;
    snprintf(out,size,"{\"available\":%s,\"phase\":\"%s\",\"busy\":%s,\"attempted\":%s,"
        "\"error\":%d,\"card_bytes\":%" PRIu64 ",\"free_available\":%s,\"free_error\":%d,"
        "\"entries\":%u,\"fat_type\":%u,\"truncated\":%s,\"close_error\":%d,\"unmount_error\":%d,"
        "\"elapsed_ms\":%" PRIu64 ",\"stack_unused\":%zu,\"stack_error\":%d,\"read_only\":%s}",
        mb_sd_available()?"true":"false",sd_state.phase?sd_state.phase:"not probed",sd_state.active?"true":"false",
        sd_state.attempted?"true":"false",r->error,r->card_bytes,r->free_space_available?"true":"false",
        r->free_space_error,r->entries,r->filesystem_type,r->truncated?"true":"false",r->close_error,r->unmount_error,
        sd_state.elapsed,sd_state.unused_stack,sd_state.stack_error,
        mb_sd_file_available()?"false":"true");
}

bool mb_sd_file_available(void) {
#if defined(CONFIG_P4_SD_FILES)
    return mb_sd_available();
#else
    return false;
#endif
}
bool mb_sd_file_start(mb_sd_file_op operation,const char *name,size_t n,const uint8_t *data,size_t length) {
#if defined(CONFIG_P4_SD_FILES)
    mb_sd_poll();
    if(sd_state.active||sd_files.generation==UINT32_MAX||!mb_sd_available()||(operation!=MB_SD_FILE_LIST&&!mb_sd_file_name(name,n))||length>MB_SD_FILE_BYTES||
       (operation!=MB_SD_FILE_READ&&operation!=MB_SD_FILE_CREATE&&operation!=MB_SD_FILE_REMOVE_OWN&&operation!=MB_SD_FILE_LIST)||
       (operation==MB_SD_FILE_CREATE&&!data&&length))return false;
    int owned=-1,free_slot=-1;
    for(unsigned i=0;i<8;i++) {
        if(!sd_files.owned[i].present){free_slot=(int)i;continue;}
        if(strlen(sd_files.owned[i].name)==n&&!memcmp(sd_files.owned[i].name,name,n))owned=(int)i;
    }
    if(operation==MB_SD_FILE_REMOVE_OWN&&owned<0)return false;
    /* Retain exact successful snapshots. No old deletion authority is evicted.
     * At most eight creations may be retained in one firmware session. */
    if(operation==MB_SD_FILE_CREATE&&(owned>=0||free_slot<0))return false;
    struct sd_job *job=k_calloc(1,sizeof(*job));if(!job)return false;
    job->stack=k_thread_stack_alloc(STACK_BYTES,0);
    if(!job->stack){k_free(job);return false;}
    if(!esp_ptr_internal(job)||!esp_ptr_internal(job->stack)||
       !esp_ptr_internal((uint8_t*)job->stack+K_KERNEL_STACK_LEN(STACK_BYTES)-1)) {
        (void)k_thread_stack_free(job->stack);k_free(job);return false;
    }
    memset(sd_files.input,0,sizeof(sd_files.input));memset(sd_files.output,0,sizeof(sd_files.output));
    if(operation==MB_SD_FILE_CREATE&&length)memcpy(sd_files.input,data,length);
    if(operation==MB_SD_FILE_REMOVE_OWN) {
        length=sd_files.owned[owned].bytes;memcpy(sd_files.input,sd_files.owned[owned].data,length);
    }
    if(operation!=MB_SD_FILE_LIST)memcpy(job->name,name,n);
    memcpy(sd_files.name,job->name,sizeof(job->name));
    job->operation=operation;job->length=length;job->began=k_uptime_get();job->deadline=job->began+DEADLINE_MS;
    sd_files.finished=false;sd_files.generation++;memset(&sd_files.result,0,sizeof(sd_files.result));
    sd_state.active=job;sd_state.phase="SD file operation running";
    memset(&sd_state.result,0,sizeof(sd_state.result));sd_state.elapsed=0;
    k_thread_create(&job->thread,job->stack,STACK_BYTES,worker,job,NULL,NULL,9,0,K_NO_WAIT);
    k_thread_name_set(&job->thread,"sd_files");return true;
#else
    (void)operation;(void)name;(void)n;(void)data;(void)length;return false;
#endif
}
bool mb_sd_file_result_get(mb_sd_file_result *out) {
#if defined(CONFIG_P4_SD_FILES)
    mb_sd_poll();if(sd_state.active||!sd_files.finished)return false;
    if(out)*out=sd_files.result;
    return true;
#else
    (void)out;return false;
#endif
}
bool mb_sd_file_copy(size_t offset,uint8_t *out,size_t length) {
#if defined(CONFIG_P4_SD_FILES)
    mb_sd_poll();if(sd_state.active||!sd_files.finished||sd_files.result.error||
       offset>sd_files.result.bytes||length>sd_files.result.bytes-offset||(!out&&length))return false;
    if(length)memcpy(out,sd_files.output+offset,length);
    return true;
#else
    (void)offset;(void)out;(void)length;return false;
#endif
}
const uint8_t *mb_sd_file_view(size_t *length) {
#if defined(CONFIG_P4_SD_FILES)
    mb_sd_poll();
    if(sd_state.active||!sd_files.finished||sd_files.result.error)return NULL;
    if(length)*length=sd_files.result.bytes;
    return sd_files.output;
#else
    (void)length;return NULL;
#endif
}
const char *mb_sd_file_last_name(void) {
#if defined(CONFIG_P4_SD_FILES)
    return sd_files.name;
#else
    return "";
#endif
}
uint32_t mb_sd_file_generation(void) {
#if defined(CONFIG_P4_SD_FILES)
    return sd_files.generation;
#else
    return 0;
#endif
}
