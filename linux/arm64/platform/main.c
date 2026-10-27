/* SPDX-License-Identifier: MPL-2.0 */
#define _XOPEN_SOURCE 700
#define _DEFAULT_SOURCE
#include "platform.h"
#include "vm/interp.h"
#include "vm/persist.h"
#include <errno.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <unistd.h>

extern void vmSlice(unsigned cycles);
extern void smallvmResetTransport(void);
static volatile sig_atomic_t stopping;
static void stop_signal(int sig){(void)sig;stopping=1;}
static void usage(FILE *out){fputs("Usage: smallvm --data-dir ABSOLUTE_PRIVATE_DIR [--pty-info FILE]\n       smallvm --self-test\n",out);}
static int idle_ms(void){
 int active=0;for(int i=0;i<taskCount;i++){
  if(tasks[i].status==running)return 0;
  if(tasks[i].status!=unusedTask)active=1;
 }
 return active?1:10;
}
int main(int argc,char **argv){
 const char *data_dir=NULL,*pty_info=NULL;int self_test=0;
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--self-test"))self_test=1;
  else if(!strcmp(argv[i],"--data-dir")||!strcmp(argv[i],"--pty-info")){
   const char *key=argv[i];if(++i>=argc){usage(stderr);return 2;}
   if(!strcmp(key,"--data-dir"))data_dir=argv[i];else pty_info=argv[i];
  }else if(!strcmp(argv[i],"--help")||!strcmp(argv[i],"-h")){usage(stdout);return 0;}
  else{usage(stderr);return 2;}
 }
 char test_directory[]="/tmp/smallvm-selftest-XXXXXX";
 if(self_test){
  if(data_dir||pty_info){fputs("--self-test uses an isolated temporary directory; do not combine with runtime paths\n",stderr);return 2;}
  data_dir=mkdtemp(test_directory);if(!data_dir){perror("self-test temporary directory");return 1;}
 }else if(!data_dir){usage(stderr);return 2;}
 struct sigaction action;memset(&action,0,sizeof(action));action.sa_handler=stop_signal;sigemptyset(&action.sa_mask);
 if(sigaction(SIGINT,&action,NULL)||sigaction(SIGTERM,&action,NULL)){perror("signal handler");return 1;}
 signal(SIGPIPE,SIG_IGN);
 linuxPlatformOpen(data_dir,pty_info);
 atexit(linuxPlatformClose);
 hardwareInit();memInit();primsInit();smallvmResetTransport();restoreScripts();
 int status=0;
 if(self_test)status=linuxPlatformSelfTest();
 else{
  startAll();
  fprintf(stdout,"SmallVM v417 headless Linux ready on %s\n",linuxPlatformPty());fflush(stdout);
  while(!stopping){
   processMessage();vmSlice(1);
   struct pollfd p={linuxPlatformMaster(),POLLIN,0};
   int result=poll(&p,1,idle_ms());if(result<0&&errno!=EINTR)linuxPlatformFatal("PTY poll failed");
  }
 }
 linuxPlatformClose();
 if(self_test){
  // Only files created inside this fresh mkdtemp directory are removed.
  char path[PATH_MAX];snprintf(path,sizeof(path),"%s/program.ucode",test_directory);unlink(path);
  snprintf(path,sizeof(path),"%s/.smallvm.lock",test_directory);unlink(path);rmdir(test_directory);
 }
 return status;
}
