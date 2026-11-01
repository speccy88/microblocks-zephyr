/* SPDX-License-Identifier: MPL-2.0 */
/* The linked official interpreter executes these bytes. Only transport is local. */
#define _DEFAULT_SOURCE
#include "platform.h"
#include "vm/interp.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/utsname.h>
#include <unistd.h>
extern void vmSlice(unsigned cycles);
static uint8 received[8192];static size_t received_count;
static void pump(void){
 processMessage();vmSlice(1);
 for(;;){ssize_t n=read(linuxPlatformSlave(),received+received_count,sizeof(received)-received_count);
  if(n<0&&(errno==EINTR))continue;
  if(n<=0)break;
  received_count+=(size_t)n;
  if(received_count==sizeof(received))break;
 }
}
static int send_packet(const uint8 *p,size_t size){
 uint64 deadline=totalMicrosecs()+2000000;
 while(size){ssize_t n=write(linuxPlatformSlave(),p,size);if(n>0){p+=n;size-=(size_t)n;}else if(errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR)return 0;
  pump();if(totalMicrosecs()>deadline)return 0;
 }
 return 1;
}
static int find_message(unsigned kind,unsigned index,int value){
 for(size_t at=0;at<received_count;){
  unsigned prefix=received[at];if(prefix==250){if(received_count-at<3)return 0;if(received[at+1]==kind&&received[at+2]==index)return 1;at+=3;}
  else if(prefix==251){if(received_count-at<5)return 0;size_t count=received[at+3]+256u*received[at+4];if(count>sizeof(received)||received_count-at<5+count)return 0;
   if(received[at+1]==19)return -1;
   if(received[at+1]==kind&&received[at+2]==index&&count==5&&received[at+5]==1){int32_t got=(int32_t)((uint32)received[at+6]|((uint32)received[at+7]<<8)|((uint32)received[at+8]<<16)|((uint32)received[at+9]<<24));if(got==value)return 1;}
   at+=5+count;
  }else return -1;
 }
 return 0;
}
static int wait_message(unsigned kind,unsigned index,int value){
 uint64 deadline=totalMicrosecs()+3000000;
 while(totalMicrosecs()<deadline){pump();int found=find_message(kind,index,value);if(found)return found>0;usleep(500);}
 return 0;
}
int linuxPlatformSelfTest(void){
 const uint8 ping[]={250,26,73};
 const uint8 reporter[]={251,32,0,22,0,2,9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0,254};
 const uint8 run[]={250,3,0};
 const uint8 assign[]={251,32,1,10,0,1,9,0,2,85,7,2,0,0,254};
 const uint8 assign_run[]={250,3,1},get_variable[]={250,7,2};
 int good=send_packet(ping,sizeof(ping))&&wait_message(26,73,0);
 received_count=0;good=good&&send_packet(reporter,sizeof(reporter));
 for(int i=0;i<200;i++)pump();
 received_count=0;good=good&&send_packet(run,sizeof(run))&&wait_message(18,0,12);
 received_count=0;good=good&&send_packet(assign,sizeof(assign));
 for(int i=0;i<200;i++)pump();
 received_count=0;good=good&&send_packet(assign_run,sizeof(assign_run));for(int i=0;i<200;i++)pump();
 received_count=0;good=good&&send_packet(get_variable,sizeof(get_variable))&&wait_message(21,2,42);
 struct utsname system;if(uname(&system))strcpy(system.machine,"unknown");
 printf("{\"result\":\"%s\",\"scope\":\"real SmallVM v417; local PTY; no external peripherals\",\"architecture\":\"%s\",\"arithmetic\":%d,\"variable\":%d,\"network_listener\":false}\n",good?"PASS":"FAIL",system.machine,good?12:0,good?42:0);
 return good?0:1;
}
