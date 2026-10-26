/* SPDX-License-Identifier: MIT */
#include "controller.h"
#include "storage_protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
extern mb_store test_store;
extern unsigned char test_output[1024];extern unsigned test_output_length,test_output_capacity;
static uint8_t request[MB_FILES_REQUEST_MAX];static uint32_t id;
static unsigned cases;
static uint32_t get32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
static uint8_t *call(unsigned op,uint32_t session,uint32_t token,uint32_t arg,const char *path,const char *data,size_t count,uint64_t now){
 memset(request,0,sizeof(request));memcpy(request,"MBFS",4);request[4]=1;request[5]=(uint8_t)op;
 put32(request+6,++id);put32(request+10,session);put32(request+14,token);put32(request+18,arg);request[22]=(uint8_t)count;request[23]=(uint8_t)(count>>8);
 size_t n=path?strlen(path):0;request[24]=(uint8_t)n;if(n)memcpy(request+26,path,n);if(data)memcpy(request+26+n,data,count);
 test_output_length=0;mb_storage_protocol_message(217,26+n+(data?count:0),(const char *)request,now);
 if(!test_output_length)return NULL;
 assert(test_output[0]==251&&test_output[1]==217&&test_output[2]==0);
 assert(test_output_length==5+(unsigned)test_output[3]+256*(unsigned)test_output[4]);
 assert(get32(test_output+11)==id);return test_output+5;
}
int main(void){
 mb_store_init(&test_store);
 test_output_capacity=0;assert(!call(9,0,0xfe000001u,0,NULL,NULL,0,0));test_output_capacity=1024;
 uint8_t *r=call(9,0,0xfe000001u,0,NULL,NULL,0,0);assert(r&&r[14]==0&&test_output_length==29);
 uint32_t session=get32(r+16);assert(session==1&&get32(r+20)==0xfe000001u&&test_output[28]==254);cases++;
 r=call(9,0,99,0,NULL,NULL,0,0);assert(r[14]==MB_FILES_BUSY);cases++;
 r=call(9,0,0xfe000001u,0,NULL,NULL,0,0);assert(r[14]==0&&get32(r+16)==session);cases++;
 r=call(5,session,0,3,"/RAM/a",NULL,0,0);assert(r[14]==0);uint32_t job=get32(r+16);
 r=call(6,session,job,0,NULL,"old",3,0);assert(r[14]==0);r=call(7,session,job,0,NULL,NULL,0,0);assert(r[14]==0);uint32_t revision=get32(r+16);cases++;
 /* Ordinary VM writes share exactly the same backing store. */
 uint32_t vmjob;assert(mb_store_begin(&test_store,"/RAM/vm",7,0,false,&vmjob)==MB_STORE_OK);
 r=call(5,session,0,0,"/RAM/b",NULL,0,0);assert(r[14]==MB_FILES_BUSY);
 mb_storage_protocol_reset();assert(test_store.state==MB_WRITE_RECEIVING);mb_store_stop(&test_store);cases++;
 r=call(9,0,4,0,NULL,NULL,0,0);assert(r[14]==0);uint32_t fresh=get32(r+16);assert(fresh>session);
 r=call(3,session,0,0,"/RAM/a",NULL,0,0);assert(r[14]==MB_FILES_DISCONNECTED);cases++;
 r=call(5,fresh,revision,4,"/RAM/a",NULL,0,0);job=get32(r+16);assert(r[14]==0);
 r=call(6,fresh,job,0,NULL,"new!",4,0);assert(r[14]==0);
 r=call(9,0,4,0,NULL,NULL,0,0);assert(r[14]==0&&test_store.state==MB_WRITE_RECEIVING);
 mb_storage_protocol_poll(0,false);assert(test_store.state==MB_WRITE_CANCELLED&&test_store.files[0].revision==revision);cases++;
 r=call(9,0,5,0,NULL,NULL,0,10);fresh=get32(r+16);assert(r[14]==0);
 r=call(5,fresh,revision,0,"/RAM/a",NULL,0,10);assert(r[14]==0);
 mb_storage_protocol_poll(30009,true);assert(test_store.state==MB_WRITE_RECEIVING);
 mb_storage_protocol_poll(30010,true);assert(test_store.state==MB_WRITE_CANCELLED);cases++;
 r=call(9,0,6,0,NULL,NULL,0,100);fresh=get32(r+16);assert(r[14]==0);
 r=call(5,fresh,revision,0,"/RAM/a",NULL,0,100);assert(r[14]==0);
 mb_storage_protocol_poll(99,true);assert(test_store.state==MB_WRITE_CANCELLED);cases++;
 r=call(9,0,7,0,NULL,NULL,0,100);fresh=get32(r+16);
 r=call(10,fresh-1,0,0,NULL,NULL,0,100);assert(r[14]==MB_FILES_DISCONNECTED);
 r=call(3,fresh,0,0,"/RAM/a",NULL,0,100);assert(r[14]==0&&get32(r+16)==revision);cases++;
 r=call(10,fresh,0,0,NULL,NULL,0,100);assert(r[14]==0&&r[16]==1);cases++;
 r=call(9,0,8,0,NULL,NULL,0,100);fresh=get32(r+16);assert(r[14]==0);
 test_output_capacity=0;assert(!call(5,fresh,revision,0,"/RAM/a",NULL,0,100));test_output_capacity=1024;
 r=call(3,fresh,0,0,"/RAM/a",NULL,0,100);assert(r[14]==0&&get32(r+16)==revision&&test_store.files[0].length==3);cases++;
 mb_storage_protocol_reset();
 printf("{\"result\":\"PASS\",\"application_bridge_scenarios\":%u,\"native_sender\":\"pinned SmallVM sendMessage and waitAndSendMessage\",\"physical_tested\":false}\n",cases);
}
