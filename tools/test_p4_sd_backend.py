#!/usr/bin/env python3
"""Actual SD worker lifecycle with synthetic Zephyr primitives, no device I/O."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json, os, subprocess
root=Path(__file__).resolve().parents[1]
out=root/'build-artifacts/p4-sd-worker-tests';out.mkdir(parents=True,exist_ok=True)
inc=out/'include';(inc/'zephyr/sys').mkdir(parents=True,exist_ok=True)
(inc/'zephyr/kernel.h').write_text('''#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#define BUILD_ASSERT(c,m) _Static_assert(c,m)
#define DT_NODELABEL(n) 1
#define DT_NODE_HAS_STATUS(n,s) 1
#define IS_ENABLED(x) (x)
#define ARG_UNUSED(x) (void)(x)
#define K_KERNEL_STACK_LEN(n) (n)
#define K_NO_WAIT 0
typedef uint8_t k_thread_stack_t;
struct k_thread {bool dead;void (*entry)(void*,void*,void*);void *arg;};
void *k_calloc(size_t,size_t);
void k_free(void*);
k_thread_stack_t *k_thread_stack_alloc(size_t,int);
int k_thread_stack_free(k_thread_stack_t*);
int k_thread_join(struct k_thread*,int);
int k_thread_stack_space_get(struct k_thread*,size_t*);
struct k_thread *k_thread_create(struct k_thread*,k_thread_stack_t*,size_t,void(*)(void*,void*,void*),void*,void*,void*,int,int,int);
void k_thread_name_set(struct k_thread*,const char*);
int64_t k_uptime_get(void);
''')
(inc/'zephyr/device.h').write_text('''struct device {int ready;};
extern struct device synthetic_sd;
#define DEVICE_DT_GET(n) (&synthetic_sd)
static inline int device_is_ready(const struct device *d){return d->ready;}
''')
(inc/'zephyr/sys/atomic.h').write_text('''typedef int atomic_t;
static inline int atomic_get(const atomic_t *a){return *a;}
static inline void atomic_set(atomic_t *a,int b){*a=b;}
''')
(inc/'esp_memory_utils.h').write_text('#include <stdbool.h>\nbool esp_ptr_internal(const void*);\n')
test=out/'test.c'
test.write_text('''#include <assert.h>
#include <stdlib.h>
#include "sd_backend.c"
struct device synthetic_sd={1};
static int64_t now;
static unsigned checks,allocations,frees,stacks,stack_frees,probes;
static int fail_job,fail_stack,not_internal,release_error,probe_error;
static struct k_thread *pending;
#define CHECK(c) do{assert(c);checks++;}while(0)
void *k_calloc(size_t a,size_t b){if(fail_job)return NULL;void *p=calloc(a,b);if(p)allocations++;return p;}
void k_free(void *p){if(p)frees++;free(p);}
k_thread_stack_t *k_thread_stack_alloc(size_t n,int f){assert(!f&&n==4096);if(fail_stack)return NULL;void *p=malloc(n);if(p)stacks++;return p;}
int k_thread_stack_free(k_thread_stack_t *p){if(release_error)return release_error;stack_frees++;free(p);return 0;}
int k_thread_join(struct k_thread *t,int wait){assert(!wait);return t->dead?0:-EBUSY;}
int k_thread_stack_space_get(struct k_thread *t,size_t *n){assert(t->dead);*n=1234;return 0;}
struct k_thread *k_thread_create(struct k_thread *t,k_thread_stack_t *s,size_t n,void(*entry)(void*,void*,void*),void *a,void *b,void *c,int priority,int flags,int delay){
 assert(s&&n==4096&&!b&&!c&&priority==9&&!flags&&!delay);t->entry=entry;t->arg=a;pending=t;return t;
}
void k_thread_name_set(struct k_thread *t,const char *n){assert(t&&n);}
int64_t k_uptime_get(void){return now;}
bool esp_ptr_internal(const void *p){return p&&!not_internal;}
int p4_sd_readonly_probe_controlled(struct p4_sd_probe_result *r,int(*check)(void*),void *ctx){
 probes++;memset(r,0,sizeof(*r));r->error=check(ctx);if(!r->error)r->error=probe_error;
 if(!r->error){r->card_bytes=32*1024*1024;r->entries=3;r->free_space_error=-ENOTSUP;}return r->error;
}
static void finish(void){assert(pending);pending->entry(pending->arg,NULL,NULL);pending->dead=true;pending=NULL;mb_sd_poll();}
int main(void){
 char status[512];uint64_t bytes;unsigned entries;
 CHECK(!mb_sd_result(NULL,NULL));mb_sd_status(status,sizeof(status));CHECK(strstr(status,"not probed")!=NULL);CHECK(!probes);
 synthetic_sd.ready=0;CHECK(!mb_sd_start());CHECK(!allocations);synthetic_sd.ready=1;
 fail_job=1;CHECK(!mb_sd_start());CHECK(!mb_sd_busy());fail_job=0;
 fail_stack=1;CHECK(!mb_sd_start());CHECK(allocations==frees);fail_stack=0;
 not_internal=1;CHECK(!mb_sd_start());CHECK(allocations==frees&&stacks==stack_frees);not_internal=0;
 CHECK(mb_sd_start());CHECK(mb_sd_busy());CHECK(!mb_sd_start());CHECK(!mb_sd_result(NULL,NULL));
 mb_sd_cancel();finish();CHECK(!mb_sd_busy());CHECK(!mb_sd_result(NULL,NULL));CHECK(!strcmp(mb_sd_phase(),"cancelled"));
 CHECK(mb_sd_start());now+=30000;finish();CHECK(!strcmp(mb_sd_phase(),"deadline exceeded"));CHECK(!mb_sd_result(NULL,NULL));
 CHECK(mb_sd_start());finish();CHECK(mb_sd_result(&bytes,&entries));CHECK(bytes==32*1024*1024&&entries==3);
 mb_sd_status(status,sizeof(status));CHECK(strstr(status,"\\"stack_unused\\":1234")!=NULL);CHECK(strstr(status,"\\"busy\\":false")!=NULL);
 probe_error=-EIO;CHECK(mb_sd_start());finish();CHECK(!mb_sd_result(NULL,NULL));CHECK(!strcmp(mb_sd_phase(),"probe failed"));probe_error=0;
 CHECK(mb_sd_start());release_error=-EBUSY;finish();CHECK(mb_sd_busy());CHECK(!mb_sd_start());CHECK(!mb_sd_result(NULL,NULL));
 release_error=0;mb_sd_poll();CHECK(!mb_sd_busy());CHECK(mb_sd_result(NULL,NULL));
 for(unsigned i=0;i<20;i++){CHECK(mb_sd_start());finish();CHECK(!mb_sd_busy());CHECK(mb_sd_result(NULL,NULL));}
 CHECK(allocations==frees&&stacks==stack_frees);CHECK(probes==25);
 printf("{\\"checks\\":%u,\\"worker_runs\\":%u,\\"job_allocations\\":%u,\\"job_frees\\":%u,\\"stack_allocations\\":%u,\\"stack_frees\\":%u}\\n",checks,probes,allocations,frees,stacks,stack_frees);
}
''')
backend=root/'boards/waveshare_esp32p4_wifi6/zephyr/src'
probe=root/'boards/waveshare_esp32p4_wifi6/diagnostics/sd_readonly/src'
binary=out/'test'
flags=['cc','-std=c11','-g','-O1','-Wall','-Wextra','-Werror','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all',
       '-DCONFIG_FS_FATFS_READ_ONLY=1','-DCONFIG_FS_FATFS_MOUNT_MKFS=0','-DCONFIG_DYNAMIC_THREAD_POOL_SIZE=0',
       '-I'+str(inc),'-I'+str(backend),'-I'+str(probe),'-I'+str(root/'common/storage')]
subprocess.run(flags+[str(test),'-o',str(binary)],check=True)
run=subprocess.run([str(binary)],capture_output=True,text=True,check=True,timeout=20,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
report=json.loads(run.stdout)
report.update(result='PASS',scope='actual worker with synthetic Zephyr/thread/probe; no card/board access',sanitizers=['address','undefined'],physical_tested=False)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
