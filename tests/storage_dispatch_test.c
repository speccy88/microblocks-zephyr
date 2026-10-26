/* SPDX-License-Identifier: MIT */
#include "wire.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define OK(x) assert((x)==MB_STORE_OK)
static mb_store store;
static mb_files_dispatcher dispatcher;
static mb_files_request request;
static mb_files_reply reply;
static mb_files_wire_workspace workspace;
static unsigned cases;
static uint32_t id,session;
static mb_files_status call(unsigned op,const char *path,uint32_t token,uint32_t arg,const uint8_t *data,size_t count) {
    memset(&request,0,sizeof(request));request.op=(uint8_t)op;request.id=++id;request.session=session;
    request.token=token;request.arg=arg;request.count=(uint16_t)count;
    if(path){request.path_length=(uint8_t)strlen(path);memcpy(request.path,path,request.path_length);}
    if(data)memcpy(request.data,data,count);
    mb_files_dispatch(&dispatcher,7,100,&request,&reply);return reply.status;
}
static uint32_t legacy(const char *path,const char *value,bool replace) {
    uint32_t job;OK(mb_store_begin(&store,path,strlen(path),strlen(value),replace,&job));
    OK(mb_store_append(&store,job,0,(const uint8_t *)value,strlen(value)));
    OK(mb_store_finish(&store,job));assert(mb_store_poll(&store));assert(store.state==MB_WRITE_DONE);
    const mb_ram_file *f;OK(mb_store_view(&store,path,strlen(path),&f));return f->revision;
}
static uint32_t begin(const char *path,uint32_t revision,size_t length) {
    assert(call(MB_FILES_BEGIN,path,revision,(uint32_t)length,NULL,0)==MB_FILES_OK);return reply.token;
}
int main(void) {
    mb_store_init(&store);mb_files_init(&dispatcher,&store);
    uint32_t old=legacy("/RAM/a","old",false),job;uint8_t bytes[32];
    assert(old==1);assert(mb_store_begin_revision(&store,"/RAM/a",6,3,old+1,&job)==MB_STORE_CONFLICT);
    assert(mb_store_begin_revision(&store,"/RAM/missing",12,0,old,&job)==MB_STORE_CONFLICT);
    assert(mb_store_begin_revision(&store,"/RAM/a",6,3,0,&job)==MB_STORE_EXISTS);cases++;
    OK(mb_store_read_revision(&store,"/RAM/a",6,old,0,bytes,3));assert(!memcmp(bytes,"old",3));
    uint32_t newer=legacy("/RAM/a","new",true);assert(newer>old);
    memset(bytes,0xcc,sizeof(bytes));assert(mb_store_read_revision(&store,"/RAM/a",6,old,0,bytes,3)==MB_STORE_CONFLICT);
    assert(bytes[0]==0xcc);assert(mb_store_read_revision(&store,"/RAM/a",6,0,0,bytes,0)==MB_STORE_CONFLICT);cases++;
    OK(mb_store_delete(&store,"/RAM/a",6));uint32_t recreated=legacy("/RAM/a","again",false);
    assert(recreated>newer);assert(mb_store_begin_revision(&store,"/RAM/a",6,0,newer,&job)==MB_STORE_CONFLICT);cases++;
    OK(mb_store_begin_revision(&store,"/RAM/a",6,0,recreated,&job));OK(mb_store_finish(&store,job));OK(mb_store_cancel(&store,job));
    assert(store.revision_counter==recreated);cases++;
    /* A future backend violating the captured version still fails at commit. */
    OK(mb_store_begin_revision(&store,"/RAM/a",6,0,recreated,&job));OK(mb_store_finish(&store,job));
    store.files[0].revision++;assert(mb_store_poll(&store));assert(store.state==MB_WRITE_FAILED&&store.job_error==MB_STORE_CONFLICT);
    assert(store.files[0].length==5);store.files[0].revision=recreated;cases++;
    store.revision_counter=MB_FILE_REFERENCE_MAX;
    assert(mb_store_begin(&store,"/RAM/b",6,0,false,&job)==MB_STORE_EXHAUSTED);
    assert(store.files[0].length==5);store.revision_counter=recreated;cases++;

    assert(mb_files_open(&dispatcher,0,100,&session)==MB_FILES_PROTOCOL);
    assert(mb_files_open(&dispatcher,7,100,&session)==MB_FILES_OK);uint32_t first_session=session;
    assert(mb_files_open(&dispatcher,8,100,&job)==MB_FILES_BUSY);cases++;
    assert(call(MB_FILES_CAPS,NULL,0,0,NULL,0)==MB_FILES_OK&&reply.count==512&&reply.file_count==8);cases++;
    assert(call(MB_FILES_LIST,NULL,0,0,NULL,0)==MB_FILES_OK&&reply.file_count==1&&reply.used==5);
    assert(reply.files[0].revision==recreated&&!strcmp(reply.files[0].path,"/RAM/a"));cases++;
    assert(call(MB_FILES_STAT,"/SD/a",0,0,NULL,0)==MB_FILES_UNAVAILABLE);
    assert(call(MB_FILES_STAT,"/RAM/../a",0,0,NULL,0)==MB_FILES_PATH);cases++;
    job=begin("/RAM/a",recreated,3);
    assert(call(MB_FILES_APPEND,NULL,job,1,(const uint8_t *)"bad",3)==MB_FILES_STATE);
    assert(call(MB_FILES_APPEND,NULL,job,0,(const uint8_t *)"yes",3)==MB_FILES_OK&&reply.count==3);
    assert(!mb_files_close(&dispatcher,8,session));
    request.id=++id;request.op=MB_FILES_CANCEL;request.arg=0;request.count=0;
    mb_files_dispatch(&dispatcher,8,100,&request,&reply);assert(reply.status==MB_FILES_DISCONNECTED&&dispatcher.job==job);
    mb_files_dispatch(&dispatcher,7,100,&request,&reply);assert(reply.status==MB_FILES_OK);
    assert(store.files[0].revision==recreated&&store.files[0].length==5);cases++;
    mb_files_dispatch(&dispatcher,7,100,&request,&reply);assert(reply.status==MB_FILES_PROTOCOL);cases++;

    job=begin("/RAM/a",recreated,3);assert(call(MB_FILES_APPEND,NULL,job,0,(const uint8_t *)"yes",3)==MB_FILES_OK);
    assert(call(MB_FILES_FINISH,NULL,job,0,NULL,0)==MB_FILES_OK);
    uint32_t committed=reply.files[0].revision;assert(committed>recreated&&reply.files[0].bytes==3);
    mb_files_dispatch(&dispatcher,7,100,&request,&reply);assert(reply.status==MB_FILES_PROTOCOL);
    assert(store.revision_counter==committed);cases++;
    assert(call(MB_FILES_READ,"/RAM/a",recreated,0,NULL,3)==MB_FILES_CONFLICT);
    assert(call(MB_FILES_READ,"/RAM/a",committed,0,NULL,3)==MB_FILES_OK&&!memcmp(reply.data,"yes",3));cases++;
    job=begin("/RAM/new",0,1);assert(call(MB_FILES_APPEND,NULL,job,0,(const uint8_t *)"x",1)==MB_FILES_OK);
    assert(mb_files_close(&dispatcher,7,session));assert(store.state==MB_WRITE_CANCELLED&&mb_store_count(&store)==1);
    for(size_t i=0;i<MB_FILE_BYTES;i++) { assert(store.staging[i]==0); }
    cases++;
    assert(mb_files_open(&dispatcher,7,100,&session)==MB_FILES_OK&&session!=first_session);id=0;
    request.session=first_session;request.id=1;mb_files_dispatch(&dispatcher,7,100,&request,&reply);
    assert(reply.status==MB_FILES_DISCONNECTED);cases++;
    job=begin("/RAM/new",0,1);assert(!mb_files_expire(&dispatcher,30099));assert(mb_files_expire(&dispatcher,30100));
    assert(store.state==MB_WRITE_CANCELLED&&mb_store_count(&store)==1);cases++;
    assert(mb_files_open(&dispatcher,7,100,&session)==MB_FILES_OK);id=0;job=begin("/RAM/new",0,0);
    assert(mb_files_expire(&dispatcher,99));assert(store.state==MB_WRITE_CANCELLED);cases++;

    assert(mb_files_open(&dispatcher,7,100,&session)==MB_FILES_OK);id=0;
    OK(mb_store_begin(&store,"/RAM/vm",7,1,false,&job));
    assert(call(MB_FILES_BEGIN,"/RAM/new",0,0,NULL,0)==MB_FILES_BUSY);
    assert(call(MB_FILES_CANCEL,NULL,job,0,NULL,0)==MB_FILES_STATE);
    assert(mb_files_close(&dispatcher,7,session));assert(store.state==MB_WRITE_RECEIVING);mb_store_stop(&store);cases++;
    assert(mb_files_open(&dispatcher,7,100,&session)==MB_FILES_OK);id=0;job=begin("/RAM/new",0,0);
    mb_store_stop(&store);assert(call(MB_FILES_FINISH,NULL,job,0,NULL,0)==MB_FILES_STATE);
    job=begin("/RAM/new",0,0);assert(call(MB_FILES_FINISH,NULL,job,0,NULL,0)==MB_FILES_OK);cases++;
    request.id=UINT32_MAX;request.op=MB_FILES_CAPS;request.token=0;request.arg=0;request.count=0;
    mb_files_dispatch(&dispatcher,7,100,&request,&reply);assert(reply.status==MB_FILES_OK);
    request.id=1;mb_files_dispatch(&dispatcher,7,100,&request,&reply);assert(reply.status==MB_FILES_PROTOCOL);cases++;
    assert(mb_files_close(&dispatcher,7,session));dispatcher.generation=MB_FILE_REFERENCE_MAX;
    assert(mb_files_open(&dispatcher,7,100,&session)==MB_FILES_FULL);cases++;

    mb_store_init(&store);mb_files_init(&dispatcher,&store);assert(mb_files_open(&dispatcher,7,0,&session)==MB_FILES_OK);
    uint8_t input[MB_FILES_REQUEST_MAX],output[MB_FILES_RESPONSE_MAX+2];size_t length;
    memset(input,0,sizeof(input));memcpy(input,"MBFS",4);input[4]=1;input[5]=MB_FILES_CAPS;input[6]=1;input[10]=1;
    memset(output,0xcc,sizeof(output));
    assert(!mb_files_wire(&dispatcher,7,0,input,26,output+1,MB_FILES_RESPONSE_MAX-1,&length,&workspace));
    assert(!length&&!dispatcher.last_id);
    assert(mb_files_wire(&dispatcher,7,0,input,26,output+1,MB_FILES_RESPONSE_MAX,&length,&workspace));
    assert(length==23&&!memcmp(output+1,"MBFR",4)&&output[0]==0xcc&&output[MB_FILES_RESPONSE_MAX+1]==0xcc);cases++;
    uint32_t random=17;
    for(unsigned i=0;i<10000;i++){
        for(size_t j=0;j<sizeof(input);j++){random=random*1664525u+1013904223u;input[j]=(uint8_t)(random>>24);}
        size_t n=i%(sizeof(input)+1);if(i%4==0&&n>=26){memcpy(input,"MBFS",4);input[4]=1;input[25]=0;}
        memset(output,0xcc,sizeof(output));
        (void)mb_files_wire(&dispatcher,7,0,input,n,output+1,MB_FILES_RESPONSE_MAX,&length,&workspace);
        assert(length<=MB_FILES_RESPONSE_MAX&&output[0]==0xcc&&output[MB_FILES_RESPONSE_MAX+1]==0xcc);
    }
    printf("{\"result\":\"PASS\",\"scenario_groups\":%u,\"malformed_packets\":10000,\"store_bytes\":%zu,\"dispatcher_bytes\":%zu,\"wire_workspace_bytes\":%zu,\"hardware_access\":false}\n",cases,sizeof(store),sizeof(dispatcher),sizeof(workspace));
}
