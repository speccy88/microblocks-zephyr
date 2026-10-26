/* SPDX-License-Identifier: MIT */
/* Application bridge over stdio. Short 250/1/0 is a harness-only link reset. */
#include "storage_protocol.h"
#include "wire.h"
#include <stdio.h>
extern unsigned char test_output[1024];extern unsigned test_output_length;
static uint8_t input[MB_FILES_REQUEST_MAX+6];
int main(void){
 fputs("MBFS_APPLICATION_READY v1\n",stderr);fflush(stderr);
 while(fread(input,1,3,stdin)==3){
  if(input[0]==250&&input[1]==1&&input[2]==0){mb_storage_protocol_reset();continue;}
  if(input[0]!=251||input[1]!=217||input[2]||fread(input+3,1,2,stdin)!=2)return 2;
  size_t rest=input[3]|((size_t)input[4]<<8);
  if(!rest||rest>sizeof(input)-5||fread(input+5,1,rest,stdin)!=rest||input[4+rest]!=254)return 3;
  mb_storage_protocol_message(217,(int)rest-1,(const char *)input+5,0);
  if(test_output_length&&fwrite(test_output,1,test_output_length,stdout)!=test_output_length)return 4;
  test_output_length=0;if(fflush(stdout))return 5;
 }
 mb_storage_protocol_reset();return ferror(stdin)?6:0;
}
