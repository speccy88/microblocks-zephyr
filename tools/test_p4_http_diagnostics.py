#!/usr/bin/env python3
"""Actual numeric HTTP observer with synthetic OS only; no device access."""
# SPDX-License-Identifier: MIT
from pathlib import Path
import json,os,subprocess
repo=Path(__file__).resolve().parents[1];root=repo/'build-artifacts/http-diagnostics-tests';root.mkdir(parents=True,exist_ok=True)
inc=root/'diag-fakes/zephyr';inc.mkdir(parents=True,exist_ok=True)
(inc/'kernel.h').write_text('''#include <pthread.h>
#include <stdint.h>
struct k_spinlock {pthread_mutex_t mutex;};
typedef int k_spinlock_key_t;
static k_spinlock_key_t k_spin_lock(struct k_spinlock *p){pthread_mutex_lock(&p->mutex);return 0;}
static void k_spin_unlock(struct k_spinlock *p,k_spinlock_key_t k){(void)k;pthread_mutex_unlock(&p->mutex);}
static uint32_t k_uptime_get_32(void){static uint32_t n;return ++n;}
''')
source=repo/'boards/waveshare_esp32p4_wifi6/zephyr/src/http_diagnostics.c'
test=f'''#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include "{source.as_posix()}"
static void *worker(void *arg){{unsigned stage=(unsigned)(uintptr_t)arg;for(unsigned i=0;i<1000;i++)p4_http_diag(stage,-12);return NULL;}}
int main(void){{
 char empty[512];p4_http_diag_json(empty,sizeof(empty));assert(!strcmp(empty,"{{\\\"counts\\\":[0,0,0,0,0,0,0],\\\"recent\\\":[]}}"));
 pthread_t threads[4];for(unsigned i=0;i<4;i++)assert(!pthread_create(threads+i,NULL,worker,(void*)(uintptr_t)(i+1)));
 for(unsigned i=0;i<4;i++)assert(!pthread_join(threads[i],NULL));
 p4_http_diag(0,100);p4_http_diag(8,100);
 char small[64];memset(small,90,sizeof(small));p4_http_diag_json(small,0);assert(small[0]==90);
 p4_http_diag_json(small,1);assert(!small[0] && small[1]==90);
 memset(small,90,sizeof(small));p4_http_diag_json(small,32);assert(!small[0] && small[32]==90);
 char out[512];p4_http_diag_json(out,sizeof(out));assert(out[0]=='{{' && strlen(out)<sizeof(out));puts(out);
 for(unsigned i=0;i<7;i++)state.counts[i]=UINT32_MAX;
 for(unsigned i=0;i<8;i++)state.recent[i]=(struct record){{7,UINT32_MAX,INT32_MIN}};
 p4_http_diag(1,INT32_MIN);assert(state.counts[0]==UINT32_MAX);
 p4_http_diag_json(out,sizeof(out));assert(strstr(out,"4294967295") && strstr(out,"-2147483648") && strlen(out)<sizeof(out));
}}
'''
(root/'http_diag_test.c').write_text(test)
cmd=['cc','-std=c11','-g','-O1','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie','-I'+str(inc.parent),str(root/'http_diag_test.c'),'-o',str(root/'http_diag_test')]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
r=subprocess.run([str(root/'http_diag_test')],capture_output=True,text=True,timeout=15);assert r.returncode==0,r.stderr
d=json.loads(r.stdout);assert d['counts']==[1000,1000,1000,1000,0,0,0] and len(d['recent'])==8
report={'result':'PASS','concurrent_events':4000,'bounded_recent_records':8,'zero_tiny_and_normal_output_capacities':'PASS','invalid_stages_ignored':True,'counter_saturation_and_extreme_numeric_output':'PASS','sanitizers':['address','undefined'],'scope':'actual diagnostic functions; synthetic OS locks/clock; no hardware'}
(root/'http-diagnostics-tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
