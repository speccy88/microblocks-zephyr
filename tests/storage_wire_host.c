/* SPDX-License-Identifier: MIT */
/* Synthetic stdio fixture only. Never links filesystem, serial or networking. */
#include "wire.h"
#include <stdio.h>
#include <string.h>
static mb_store store;
static mb_files_dispatcher dispatcher;
static mb_files_wire_workspace workspace;
static uint8_t input[MB_FILES_REQUEST_MAX+6],output[MB_FILES_RESPONSE_MAX+6];
int main(void){
    mb_store_init(&store);mb_files_init(&dispatcher,&store);uint32_t session;
    if(mb_files_open(&dispatcher,1,0,&session)!=MB_FILES_OK||session!=1)return 2;
    /* Separate process/WSL startup from request timeout assertions. */
    fputs("MBFS_HOST_READY v1\n",stderr);fflush(stderr);
    while(fread(input,1,5,stdin)==5){
        size_t rest=input[3]|((size_t)input[4]<<8);
        if(input[0]!=251||input[1]!=MB_FILES_MESSAGE||input[2]||!rest||rest>sizeof(input)-5)return 3;
        if(fread(input+5,1,rest,stdin)!=rest||input[4+rest]!=254)return 4;
        size_t n;
        if(!mb_files_wire(&dispatcher,1,0,input+5,rest-1,output+5,MB_FILES_RESPONSE_MAX,&n,&workspace))return 5;
        output[0]=251;output[1]=MB_FILES_MESSAGE;output[2]=0;output[3]=(uint8_t)n;output[4]=(uint8_t)(n>>8);
        if(fwrite(output,1,n+5,stdout)!=n+5||fflush(stdout))return 6;
    }
    (void)mb_files_close(&dispatcher,1,session);return ferror(stdin)?7:0;
}
