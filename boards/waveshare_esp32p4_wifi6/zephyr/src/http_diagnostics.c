/* SPDX-License-Identifier: MIT */
/* Numeric observations only: never receive a URL, request body or credentials. */
#include "http_diagnostics.h"
#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
struct record {uint32_t stage,time;int32_t result;};
static struct {uint32_t counts[7];uint8_t next,used;struct record recent[8];} state;
static struct k_spinlock lock;
void p4_http_diag(unsigned stage,int result)
{
 if(stage<1||stage>7)return;
 k_spinlock_key_t key=k_spin_lock(&lock);
 if(state.counts[stage-1]!=UINT32_MAX)state.counts[stage-1]++;
 state.recent[state.next]=(struct record){stage,k_uptime_get_32(),result};
 state.next=(state.next+1)%8;
 if(state.used<8)state.used++;
 k_spin_unlock(&lock,key);
}
void p4_http_diag_json(char *out,size_t n)
{
 if(!n)return;
 uint32_t counts[7];unsigned next,count;struct record records[8];
 k_spinlock_key_t key=k_spin_lock(&lock);
 memcpy(counts,state.counts,sizeof(counts));memcpy(records,state.recent,sizeof(records));next=state.next;count=state.used;
 k_spin_unlock(&lock,key);
 int written=snprintf(out,n,"{\"counts\":[%u,%u,%u,%u,%u,%u,%u],\"recent\":[",counts[0],counts[1],counts[2],counts[3],counts[4],counts[5],counts[6]);
 if(written<0 || (size_t)written>=n){out[0]=0;return;}
 size_t used=(size_t)written;
 for(unsigned i=0;i<count;i++){
  const struct record *r=&records[(next+8-count+i)%8];
  written=snprintf(out+used,n-used,"%s[%u,%d,%u]",i?",":"",r->stage,r->result,r->time);
  if(written<0 || (size_t)written>=n-used){out[0]=0;return;}used+=(size_t)written;
 }
 if(n-used<3){out[0]=0;return;}memcpy(out+used,"]}",3);
}
