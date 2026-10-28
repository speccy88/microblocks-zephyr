#!/usr/bin/env python3
"""Prove single volatile PS attempt, read-after confirmation and no uncertain replay."""
from pathlib import Path
import json,os,subprocess
repo=Path(__file__).resolve().parents[1];out=repo/'build-artifacts/p4-wifi-latency-policy-tests';out.mkdir(parents=True,exist_ok=True)
source=out/'test.c';source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include "wifi_latency_policy.h"
struct fake {int reads,sets,before,after,first_error,second_error,set_error;};
static unsigned checks;
#define CHECK(x) do{assert(x);checks++;}while(0)
static int read_state(void *context,int *enabled,int *mode){struct fake *f=context;int n=f->reads++;*enabled=n?f->after:f->before;*mode=0;return n?f->second_error:f->first_error;}
static int disable(void *context){struct fake *f=context;f->sets++;return f->set_error;}
static void again(struct p4_latency_policy *p,struct fake *f){int r=f->reads,s=f->sets,e=p->error;CHECK(p4_latency_policy_run(p,f,read_state,disable)==e);CHECK(f->reads==r&&f->sets==s);}
int main(void){
 struct p4_latency_policy p={0};struct fake f={.first_error=-ETIMEDOUT};
 CHECK(p4_latency_policy_run(&p,&f,read_state,disable)==-ETIMEDOUT);CHECK(p.complete&&!p.confirmed&&!p.set_requested&&f.reads==1&&!f.sets);again(&p,&f);
 p=(struct p4_latency_policy){0};f=(struct fake){.before=0};
 CHECK(!p4_latency_policy_run(&p,&f,read_state,disable));CHECK(p.confirmed&&!p.set_requested&&f.reads==1&&!f.sets);again(&p,&f);
 p=(struct p4_latency_policy){0};f=(struct fake){.before=1,.after=0};
 CHECK(!p4_latency_policy_run(&p,&f,read_state,disable));CHECK(p.confirmed&&p.set_requested&&f.reads==2&&f.sets==1&&p.after_enabled==0);again(&p,&f);
 p=(struct p4_latency_policy){0};f=(struct fake){.before=1,.after=0,.set_error=-ETIMEDOUT};
 CHECK(!p4_latency_policy_run(&p,&f,read_state,disable));CHECK(p.confirmed&&p.set_error==-ETIMEDOUT&&f.sets==1&&f.reads==2);again(&p,&f);
 p=(struct p4_latency_policy){0};f=(struct fake){.before=1,.after=1,.set_error=-ETIMEDOUT};
 CHECK(p4_latency_policy_run(&p,&f,read_state,disable)==-ETIMEDOUT);CHECK(!p.confirmed&&p.complete&&f.sets==1);again(&p,&f);
 p=(struct p4_latency_policy){0};f=(struct fake){.before=1,.after=1};
 CHECK(p4_latency_policy_run(&p,&f,read_state,disable)==-EIO);CHECK(!p.confirmed&&p.complete&&f.sets==1);again(&p,&f);
 p=(struct p4_latency_policy){0};f=(struct fake){.before=1,.second_error=-EIO};
 CHECK(p4_latency_policy_run(&p,&f,read_state,disable)==-EIO);CHECK(!p.confirmed&&p.complete&&f.sets==1&&f.reads==2);again(&p,&f);
 printf("{\"result\":\"PASS\",\"checks\":%u,\"physical_tested\":false}\n",checks);
}
''')
binary=out/'test';subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(repo/'boards/waveshare_esp32p4_wifi6/zephyr/src'),str(source),'-o',str(binary)],check=True)
result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1'))
if result.returncode:print(result.stderr)
result.check_returncode();report=json.loads(result.stdout);report.update(sanitizers=['address','undefined'],scope='actual volatile PS policy; errors and lost ACK are never retried')
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
