/* SPDX-License-Identifier: MPL-2.0 */
/* Headless POSIX platform. Interface derives from MicroBlocks linux+pi/linux.c
 * and the repository's MPL-2.0 platform.c; no SDL or WiringPi dependency. */
#define _XOPEN_SOURCE 700
#define _DEFAULT_SOURCE
#include "platform.h"
#include "vm/interp.h"
#include "vm/persist.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#define PROGRAM_FILE "program.ucode"
#define LOCK_FILE ".smallvm.lock"
#define MAX_CODE_BYTES (16 * 1024 * 1024)
static int directory_fd=-1,lock_fd=-1,master_fd=-1,slave_fd=-1;
static int info_created;
static char info_name[NAME_MAX+1],info_path[PATH_MAX],pty_path[128];
static struct timespec clock_start;
static uint8 *disk_image;
static size_t disk_capacity,disk_used;
static uint32 staged_words[2],reset_header;
static unsigned staged_count,temp_counter;
static int resetting;

static int write_all(int fd,const void *buffer,size_t count) {
 const uint8 *p=buffer;
 while(count){ssize_t n=write(fd,p,count);if(n<0&&errno==EINTR)continue;if(n<=0)return -1;p+=n;count-=(size_t)n;}
 return 0;
}
void linuxPlatformFatal(const char *reason) {
 fprintf(stderr,"SmallVM Linux error: %s\n",reason);
 linuxPlatformClose();exit(EXIT_FAILURE);
}
static void need(int condition,const char *message){if(!condition)linuxPlatformFatal(message);}
static void private_file(int fd){struct stat s;need(fstat(fd,&s)==0&&S_ISREG(s.st_mode)&&s.st_uid==geteuid()&&s.st_nlink==1&&(s.st_mode&0077)==0,"refusing non-private or non-regular state file");}
static uint32 read_le32(const uint8 *p){return (uint32)p[0]|((uint32)p[1]<<8)|((uint32)p[2]<<16)|((uint32)p[3]<<24);}
static void put_le32(uint8 *p,uint32 v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static int known_record(unsigned type){return type==10||type==11||type==12||type==19||type==21||type==29||type==218;}
static int valid_image(const uint8 *p,size_t bytes){
 if(bytes<4||(bytes&3)||p[3]!='S'||!(read_le32(p)&0xffffffu))return 0;
 for(size_t at=4;at<bytes;){
  if(bytes-at<8||p[at+3]!='R'||!known_record(p[at+2]))return 0;
  uint32 words=read_le32(p+at+4);
  if(words>(bytes-at-8)/4)return 0;
  at+=8+(size_t)words*4;
 }
 return 1;
}
static void commit_image(void){
 need(directory_fd>=0&&disk_image&&disk_used<=disk_capacity&&valid_image(disk_image,disk_used),"invalid pending code-file image");
 char temporary[80];int fd=-1;
 for(int retry=0;retry<10&&fd<0;retry++){
  snprintf(temporary,sizeof(temporary),".program-%ld-%u.tmp",(long)getpid(),++temp_counter);
  fd=openat(directory_fd,temporary,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
  if(fd<0&&errno!=EEXIST)break;
 }
 need(fd>=0,"cannot create private program update");
 if(write_all(fd,disk_image,disk_used)||fsync(fd)||close(fd)){
  int saved=errno;close(fd);unlinkat(directory_fd,temporary,0);errno=saved;linuxPlatformFatal("cannot durably write program update");
 }
 if(renameat(directory_fd,temporary,directory_fd,PROGRAM_FILE)||fsync(directory_fd)){
  unlinkat(directory_fd,temporary,0);linuxPlatformFatal("cannot atomically install program update");
 }
}
int linuxPlatformOpen(const char *data_dir,const char *pty_info){
 need(data_dir&&data_dir[0]=='/',"--data-dir must be absolute");
 if(mkdir(data_dir,0700)&&errno!=EEXIST)linuxPlatformFatal("cannot create data directory (its parent must exist)");
 directory_fd=open(data_dir,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
 need(directory_fd>=0,"cannot open private data directory");
 struct stat s;need(fstat(directory_fd,&s)==0&&S_ISDIR(s.st_mode)&&s.st_uid==geteuid()&&(s.st_mode&0077)==0,"data directory must be private (0700) and owned by the current user");
 lock_fd=openat(directory_fd,LOCK_FILE,O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
 need(lock_fd>=0,"cannot open data lock");private_file(lock_fd);
 need(flock(lock_fd,LOCK_EX|LOCK_NB)==0,"another SmallVM owns this data directory");
 char resolved[PATH_MAX];need(realpath(data_dir,resolved)!=NULL,"cannot resolve data directory");
 if(pty_info){
  size_t n=strlen(resolved);need(!strncmp(pty_info,resolved,n)&&pty_info[n]=='/'&&pty_info[n+1]&&!strchr(pty_info+n+1,'/'),"--pty-info must name a file directly inside --data-dir");
  need(strlen(pty_info+n+1)<=NAME_MAX,"PTY info filename too long");strcpy(info_name,pty_info+n+1);
 }else snprintf(info_name,sizeof(info_name),"pty-%ld.json",(long)getpid());
 need(strcmp(info_name,".")&&strcmp(info_name,"..")&&strcmp(info_name,PROGRAM_FILE)&&strcmp(info_name,LOCK_FILE),"reserved PTY info filename");
 need(snprintf(info_path,sizeof(info_path),"%s/%s",resolved,info_name)<(int)sizeof(info_path),"PTY info path too long");
 need(clock_gettime(CLOCK_MONOTONIC,&clock_start)==0,"monotonic clock unavailable");
 master_fd=posix_openpt(O_RDWR|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);
 need(master_fd>=0&&grantpt(master_fd)==0&&unlockpt(master_fd)==0,"cannot allocate PTY");
 char *slave=ptsname(master_fd);need(slave&&strlen(slave)<sizeof(pty_path),"cannot resolve PTY slave");strcpy(pty_path,slave);
 slave_fd=open(pty_path,O_RDWR|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);need(slave_fd>=0,"cannot open PTY slave");
 need(fchmod(slave_fd,0600)==0,"cannot protect PTY slave");struct termios term;
 need(tcgetattr(slave_fd,&term)==0,"cannot read PTY attributes");cfmakeraw(&term);
 need(tcsetattr(slave_fd,TCSANOW,&term)==0,"cannot set binary PTY attributes");
 char info_temporary[80];snprintf(info_temporary,sizeof(info_temporary),".pty-info-%ld.tmp",(long)getpid());
 int fd=openat(directory_fd,info_temporary,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
 need(fd>=0,"cannot create private PTY info staging file");
 char json[512];int count=snprintf(json,sizeof(json),"{\"pty\":\"%s\",\"pid\":%ld,\"transport\":\"pty\",\"vm_version\":417,\"network_listener\":false}\n",pty_path,(long)getpid());
 if(count<=0||count>=(int)sizeof(json)||write_all(fd,json,(size_t)count)||fsync(fd)||close(fd)){
  close(fd);unlinkat(directory_fd,info_temporary,0);linuxPlatformFatal("cannot write PTY info");
 }
 // Publish complete JSON atomically without replacing an existing file/symlink.
 int published=linkat(directory_fd,info_temporary,directory_fd,info_name,0);
 unlinkat(directory_fd,info_temporary,0);
 need(published==0,"PTY info already exists or cannot be created");info_created=1;
 need(fsync(directory_fd)==0,"cannot sync PTY discovery file");
 return 0;
}
void linuxPlatformClose(void){
 if(directory_fd>=0&&info_created&&info_name[0])unlinkat(directory_fd,info_name,0);
 info_created=0;
 info_name[0]=0;
 if(slave_fd>=0)close(slave_fd);
 slave_fd=-1;
 if(master_fd>=0)close(master_fd);
 master_fd=-1;
 if(lock_fd>=0)close(lock_fd);
 lock_fd=-1;
 if(directory_fd>=0)close(directory_fd);
 directory_fd=-1;
 free(disk_image);disk_image=NULL;disk_capacity=disk_used=0;
}
int linuxPlatformSlave(void){return slave_fd;}
int linuxPlatformMaster(void){return master_fd;}
const char *linuxPlatformPty(void){return pty_path;}
const char *linuxPlatformInfo(void){return info_path;}

uint64 totalMicrosecs(void){
 struct timespec now;if(clock_gettime(CLOCK_MONOTONIC,&now))linuxPlatformFatal("monotonic clock read failed");
 return (uint64)(now.tv_sec-clock_start.tv_sec)*1000000u+(now.tv_nsec-clock_start.tv_nsec)/1000;
}
uint32 microsecs(void){return (uint32)totalMicrosecs();}
uint32 millisecs(void){return (uint32)(totalMicrosecs()/1000u);}
uint32 seconds(void){return (uint32)(totalMicrosecs()/1000000u);}
void handleMicosecondClockWrap(void){}
void smallvmDelay(unsigned long ms){struct timespec remain={(time_t)(ms/1000),(long)(ms%1000)*1000000L};while(nanosleep(&remain,&remain)&&errno==EINTR){}}
void delay(unsigned long ms){smallvmDelay(ms);}
void lightSleep(int ms){if(ms>0)smallvmDelay((unsigned long)ms);}
void deepSleep(int secs){if(secs>0)smallvmDelay((unsigned long)secs*1000u);}
int recvBytes(uint8 *buffer,int count){if(count<=0||master_fd<0)return 0;ssize_t n=read(master_fd,buffer,(size_t)count);if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR||errno==EIO))return 0;if(n<0)linuxPlatformFatal("PTY read failed");return (int)n;}
int sendBytes(uint8 *buffer,int start,int end){if(start<0||end<start||master_fd<0)return 0;ssize_t n=write(master_fd,buffer+start,(size_t)(end-start));if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR||errno==EIO))return 0;if(n<0)linuxPlatformFatal("PTY write failed");return (int)n;}
void restartSerial(void){}
void hardwareInit(void){initTasks();}

int initCodeFile(uint8 *flash,int capacity){
 need(directory_fd>=0&&capacity>=4&&capacity<=MAX_CODE_BYTES&&!(capacity&3),"invalid code store capacity");
 free(disk_image);disk_image=malloc((size_t)capacity);need(disk_image!=NULL,"cannot allocate persistence staging buffer");disk_capacity=(size_t)capacity;disk_used=0;staged_count=0;resetting=0;
 int fd=openat(directory_fd,PROGRAM_FILE,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
 if(fd<0){need(errno==ENOENT,"cannot open program file");put_le32(disk_image,0x53000001u);disk_used=4;commit_image();}
 else{
  private_file(fd);struct stat s;need(fstat(fd,&s)==0&&s.st_size>=4&&(uint64)s.st_size<=disk_capacity,"invalid code file size; existing file retained");
  disk_used=(size_t)s.st_size;size_t at=0;
  while(at<disk_used){ssize_t n=read(fd,disk_image+at,disk_used-at);if(n<0&&errno==EINTR)continue;need(n>0,"cannot read program file");at+=(size_t)n;}
  need(close(fd)==0,"cannot close program file");need(valid_image(disk_image,disk_used),"corrupt code file; existing file retained");
 }
 memset(flash,255,(size_t)capacity);memcpy(flash,disk_image,disk_used);return (int)disk_used;
}
void writeCodeFileWord(int word){need(disk_image&&staged_count<2&&!resetting,"invalid staged record header");staged_words[staged_count++]=(uint32)word;}
void clearCodeFile(int cycle){need(disk_image&&staged_count==0,"cannot compact with an incomplete record");reset_header=0x53000000u|((uint32)cycle&0xffffffu);if(!(reset_header&0xffffffu))reset_header|=1u;resetting=1;}
void writeCodeFile(uint8 *code,int count){
 need(disk_image&&count>=0&&!(count&3)&&(count==0||code),"invalid code-file payload");
 size_t base=resetting?4:disk_used,header=staged_count*4u;
 need((staged_count==0||staged_count==2)&&base+header<=disk_capacity&&(size_t)count<=disk_capacity-base-header,"code file capacity exceeded");
 if(resetting)put_le32(disk_image,reset_header);
 for(unsigned i=0;i<staged_count;i++)put_le32(disk_image+base+4*i,staged_words[i]);
 if(count)memcpy(disk_image+base+header,code,(size_t)count);
 disk_used=base+header+(size_t)count;staged_count=0;resetting=0;commit_image();
}
void initFileSystem(void){}
int hasStartupSnapshot(void){return 0;}
void loadCodeSnapshot(char *name){(void)name;fail(primitiveNotImplemented);}
void snapshotCodeToFile(char *name,int count){(void)name;(void)count;fail(primitiveNotImplemented);}
void createFile(const char *name){(void)name;fail(primitiveNotImplemented);}
void deleteFile(const char *name){(void)name;fail(primitiveNotImplemented);}
int fileExists(const char *name){(void)name;return 0;}
