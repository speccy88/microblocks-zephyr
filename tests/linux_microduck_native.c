/* SPDX-License-Identifier: MPL-2.0
 * Native adapter tests with real Unix sockets and VM memory; no robot hardware.
 * The production source is included for bounded-ID/race white-box checks, not
 * copied or replaced. Peer/write fault providers are test-only wrappers. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>
static int wrongPeer;
static size_t sendLimit, sentBytes;
static int unitGetsockopt(int fd,int level,int option,void *value,socklen_t *length) {
    int result=getsockopt(fd,level,option,value,length);
    if (!result && wrongPeer && level==SOL_SOCKET && option==SO_PEERCRED) ((struct ucred *)value)->uid++;
    return result;
}
static ssize_t unitSend(int fd,const void *bytes,size_t length,int flags) {
    if (sendLimit && length>sendLimit) length=sendLimit;
    ssize_t count=send(fd,bytes,length,flags);
    if (count>0) sentBytes+=(size_t)count;
    return count;
}
#define getsockopt unitGetsockopt
#define send unitSend
#include "../linux/arm64/platform/microduck.c"
#undef getsockopt
#undef send

OBJ vars[MAX_VARS];
Task tasks[MAX_TASKS];
int taskCount;
OBJ lastBroadcast;
static uint8 vmError;
static unsigned checks;
#define CHECK(condition) do { assert(condition); ++checks; } while (0)
OBJ fail(uint8 error) { vmError=error; return falseObj; }
void captureIncomingBytes(void) {}
void updateMicrobitDisplay(void) {}
uint32 microsecs(void) { static uint32 ticks;return ++ticks; }
void outputString(const char *text) { (void)text; }
void addPrimitiveSet(PrimitiveSetIndex index,const char *name,int count,PrimEntry *table) {
    CHECK(index==MicroDuckPrims && index==22);
    CHECK(!strcmp(name,"microduck") && count==9);
    CHECK(!strcmp(table[0].primName,"configured"));
}

typedef struct { char directory[64],path[108]; int listener; } Fixture;
static int listenerAt(const char *path) {
    int fd=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0); assert(fd>=0);
    struct sockaddr_un address={.sun_family=AF_UNIX};strcpy(address.sun_path,path);
    CHECK(bind(fd,(struct sockaddr *)&address,sizeof(address))==0);
    CHECK(chmod(path,0600)==0);CHECK(listen(fd,4)==0);return fd;
}
static Fixture fixture(void) {
    Fixture result={.listener=-1};strcpy(result.directory,"/tmp/mb-microduck-native-XXXXXX");
    CHECK(mkdtemp(result.directory)!=NULL);CHECK(chmod(result.directory,0700)==0);
    snprintf(result.path,sizeof(result.path),"%s/gateway.sock",result.directory);
    result.listener=listenerAt(result.path);
    CHECK(linuxMicroduckConfigure(result.path)==0);sentBytes=0;wrongPeer=0;sendLimit=0;return result;
}
static void cleanup(Fixture *f) {
    linuxMicroduckClose();if(f->listener>=0)close(f->listener);unlink(f->path);rmdir(f->directory);f->listener=-1;
    wrongPeer=0;sendLimit=0;
}
static OBJ text(const char *value) { OBJ result=newStringFromBytes(value,(int)strlen(value));CHECK(result!=falseObj);return result; }
static uint32_t begin(const char *method,const char *params,int confirmed) {
    vmError=0;vars[0]=text(method);vars[1]=text(params);OBJ args[]={vars[0],vars[1],confirmed?trueObj:falseObj};
    OBJ result=beginPrimitive(3,args);return result? (uint32_t)obj2int(result):0;
}
static void release(uint32_t id) { OBJ arg=int2obj(id);vmError=0;releasePrimitive(1,&arg);CHECK(!vmError); }
static const char *status(uint32_t id) { OBJ arg=int2obj(id);vmError=0;OBJ result=statusPrimitive(1,&arg);CHECK(result && !vmError);return obj2str(result); }
static const char *result(uint32_t id) { OBJ arg=int2obj(id);vmError=0;OBJ answer=resultPrimitive(1,&arg);CHECK(answer && !vmError);return obj2str(answer); }
static void finish(uint32_t id) {
    for(unsigned i=0;i<1000 && findJob(id)->state==JOB_PENDING;++i){linuxMicroduckPoll();usleep(1000);}
    CHECK(findJob(id)->state!=JOB_PENDING);
}
static int acceptFixture(Fixture *f) {
    struct pollfd descriptor={.fd=f->listener,.events=POLLIN};
    if (poll(&descriptor,1,1000)!=1) return -1;
    return accept(f->listener,NULL,NULL);
}
static pid_t server(Fixture *f,const char *mode) {
    pid_t pid=fork();CHECK(pid>=0);if(pid)return pid;
    int fd=acceptFixture(f);if(fd<0)_exit(80);
    char request[8193];size_t used=0;
    while(used<8192){struct pollfd p={.fd=fd,.events=POLLIN};if(poll(&p,1,1000)!=1)_exit(81);ssize_t n=read(fd,request+used,8192-used);if(n<=0)_exit(82);used+=(size_t)n;if(memchr(request,'\n',used))break;}
    yyjson_doc *document=yyjson_read(request,used,0);if(!document)_exit(83);
    yyjson_val *rootValue=yyjson_doc_get_root(document);unsigned id=(unsigned)yyjson_get_uint(yyjson_obj_get(rootValue,"id"));
    if (!id || request[used-1]!='\n' || memchr(request,'\n',used-1))_exit(84);
    yyjson_doc_free(document);
    char reply[1024];int length=0;
    if(!strcmp(mode,"success"))length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"result\":{\"fixture\":true},\"gateway\":{\"service\":\"robot\",\"upstream_api_version\":44,\"expected_api_version\":44}}\n",id);
    else if(!strcmp(mode,"wrong-id"))length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"result\":true}\n",id+1);
    else if(!strcmp(mode,"duplicate"))length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"id\":%u,\"result\":true}\n",id,id);
    else if(!strcmp(mode,"secret-error"))length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"error\":{\"code\":-32003,\"message\":\"DO_NOT_REFLECT_PRIVATE\",\"data\":{\"outcome\":\"rejected\"}}}\n",id);
    else if(!strcmp(mode,"unknown-error"))length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"error\":{\"code\":-32008,\"message\":\"private\",\"data\":{\"outcome\":\"unknown\"}}}\n",id);
    else if(!strcmp(mode,"bad-utf8"))length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"result\":\"\xff\"}\n",id);
    else if(!strcmp(mode,"deep")){length=snprintf(reply,sizeof(reply),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"result\":",id);for(int i=0;i<24;i++)reply[length++]='[';reply[length++]='0';for(int i=0;i<24;i++)reply[length++]=']';reply[length++]='}';reply[length++]='\n';}
    else if(!strcmp(mode,"timeout"))usleep(150000);
    else if(strcmp(mode,"eof"))_exit(85);
    if(length>0){ssize_t written=write(fd,reply,(size_t)length);if(written!=length)_exit(86);}
    close(fd);close(f->listener);_exit(0);
}
static void reap(pid_t pid) {int code;CHECK(waitpid(pid,&code,0)==pid);CHECK(WIFEXITED(code)&&WEXITSTATUS(code)==0);}

static void primitiveValidation(void) {
    linuxMicroduckClose();CHECK(configuredPrimitive(0,NULL)==falseObj);
    CHECK(begin("robot.health","{}",0)==0 && vmError==primitiveNotImplemented);
    CHECK(linuxMicroduckConfigure("relative.sock")==-1);
    CHECK(linuxMicroduckConfigure("/tmp/a/../b.sock")==-1);
    CHECK(linuxMicroduckConfigure("/tmp//b.sock")==-1);
    Fixture f=fixture();CHECK(configuredPrimitive(0,NULL)==trueObj);
    for(const char **p=(const char *[]){"system.authenticate","net.connect","robot.move","update.apply","exec",NULL};*p;++p)CHECK(begin(*p,"{}",1)==0 && vmError==argIndexOutOfRange);
    CHECK(begin("robot.sound","{\"tag\":\"chirp\"}",0)==0 && vmError==argIndexOutOfRange);
    CHECK(begin("robot.health","{\"x\":1,\"x\":2}",0)==0 && vmError==argIndexOutOfRange);
    CHECK(begin("robot.health","{}{}",0)==0 && vmError==argIndexOutOfRange);
    CHECK(begin("system.logs","{\"unit\":\"--directory=/etc\"}",0)==0 && vmError==argIndexOutOfRange);
    CHECK(sentBytes==0);cleanup(&f);
}
static void repliesAndFraming(void) {
    const char *modes[]={"success","wrong-id","duplicate","secret-error","unknown-error","bad-utf8","deep","eof","timeout"};
    for(size_t i=0;i<sizeof(modes)/sizeof(modes[0]);++i){
        Fixture f=fixture();pid_t pid=server(&f,modes[i]);
        uint32_t id=begin("robot.health"," {\r\n } \n",0);CHECK(id>0 && !vmError);CHECK(!strcmp(status(id),"pending"));
        OBJ arg=int2obj(id);vmError=0;CHECK(resultPrimitive(1,&arg)==falseObj && vmError==argIndexOutOfRange);
        /* Pending job owns native request bytes, not the two VM strings. */
        vars[0]=vars[1]=zeroObj;gc();finish(id);CHECK(sentBytes>0);
        const char *terminal=status(id);
        if(!strcmp(modes[i],"success")){CHECK(!strcmp(terminal,"ready"));CHECK(strstr(result(id),"\"fixture\":true")!=NULL);}
        else if(!strcmp(modes[i],"secret-error")){CHECK(!strcmp(terminal,"error"));CHECK(strstr(result(id),"DO_NOT_REFLECT_PRIVATE")==NULL);CHECK(strstr(result(id),"rejected")!=NULL);}
        else {CHECK(!strcmp(terminal,"unknown"));CHECK(strstr(result(id),"\"outcome\":\"unknown\"")!=NULL);}
        release(id);vmError=0;CHECK(statusPrimitive(1,&arg)==falseObj && vmError==indexOutOfRangeError);
        reap(pid);cleanup(&f);
    }
}
static void securityBeforeFirstByte(void) {
    Fixture f=fixture();CHECK(chmod(f.directory,0755)==0);uint32_t id=begin("robot.health","{}",0);finish(id);
    CHECK(!strcmp(status(id),"error") && !sentBytes);CHECK(strstr(result(id),"not_sent")!=NULL);CHECK(chmod(f.directory,0700)==0);release(id);
    CHECK(chmod(f.path,0666)==0);id=begin("robot.health","{}",0);finish(id);CHECK(!strcmp(status(id),"error")&&!sentBytes);CHECK(chmod(f.path,0600)==0);release(id);
    wrongPeer=1;id=begin("robot.health","{}",0);finish(id);CHECK(!strcmp(status(id),"error")&&!sentBytes);release(id);wrongPeer=0;
    /* Replace the socket after connect but before its first send. */
    id=begin("robot.health","{}",0);Job *job=findJob(id);
    for(unsigned i=0;i<20 && job->stage!=ST_SENDING;++i) { linuxMicroduckPoll(); }
    CHECK(job->stage==ST_SENDING && !job->sent);
    CHECK(unlink(f.path)==0);int replacement=listenerAt(f.path);linuxMicroduckPoll();CHECK(job->state==JOB_ERROR && !job->sent && !sentBytes);close(replacement);release(id);
    cleanup(&f);
    f=fixture();char alias[90],path[108];snprintf(alias,sizeof(alias),"%s-link",f.directory);CHECK(symlink(f.directory,alias)==0);snprintf(path,sizeof(path),"%s/gateway.sock",alias);
    CHECK(linuxMicroduckConfigure(path)==0);id=begin("robot.health","{}",0);finish(id);CHECK(!strcmp(status(id),"error")&&!sentBytes);unlink(alias);cleanup(&f);
}
static void cancellationSlotsAndRecovery(void) {
    Fixture f=fixture();uint32_t ids[4];
    for(unsigned i=0;i<4;++i){ids[i]=begin("robot.health","{}",0);CHECK(ids[i]>0);}
    CHECK(begin("robot.health","{}",0)==0 && vmError==insufficientMemoryError);
    linuxMicroduckCancelPending();CHECK(!sentBytes);
    OBJ list=jobsPrimitive(0,NULL);CHECK(TYPE(list)==ListType && obj2int(FIELD(list,0))==4);
    for(unsigned i=0;i<4;++i){CHECK(obj2int(FIELD(list,i+1))==(int)ids[i]);CHECK(!strcmp(status(ids[i]),"error"));}
    release(ids[0]);uint32_t newer=begin("robot.health","{}",0);CHECK(newer>ids[3]);linuxMicroduckCancelPending();release(newer);
    for(unsigned i=1;i<4;++i)release(ids[i]);
    /* One real partial send, then StopAll-style cancellation: outcome unknown. */
    sendLimit=3;uint32_t id=begin("robot.health","{}",0);Job *job=findJob(id);
    for(unsigned i=0;i<20 && !job->sent;++i) { linuxMicroduckPoll(); }
    CHECK(job->sent==3);linuxMicroduckCancelPending();
    CHECK(!strcmp(status(id),"unknown"));CHECK(strstr(result(id),"unknown")!=NULL);release(id);cleanup(&f);
}
static void quoteAndIdentifierBoundary(void) {
    vmError=0;OBJ input=text("quote \" and \\ newline\n caf\xc3\xa9"),quoted=quotePrimitive(1,&input);CHECK(quoted && !vmError);
    const char *serialized=obj2str(quoted);yyjson_doc *doc=yyjson_read(serialized,strlen(serialized),0);CHECK(doc!=NULL);CHECK(!strcmp(yyjson_get_str(yyjson_doc_get_root(doc)),"quote \" and \\ newline\n caf\xc3\xa9"));yyjson_doc_free(doc);
    char invalid[]={ (char)0xff, '\0' };input=text(invalid);vmError=0;CHECK(quotePrimitive(1,&input)==falseObj && vmError==argIndexOutOfRange);
    input=newStringFromBytes("a\0hidden",8);vmError=0;CHECK(quotePrimitive(1,&input)==falseObj && vmError==argIndexOutOfRange);
    char *huge=malloc(8193);CHECK(huge!=NULL);memset(huge,'x',8192);huge[8192]='\0';input=text(huge);free(huge);vmError=0;CHECK(quotePrimitive(1,&input)==falseObj && vmError==argIndexOutOfRange);
    Fixture f=fixture();nextJobID=LINUX_MICRODUCK_MAX_ID;uint32_t id=begin("robot.health","{}",0);CHECK(id==1073741823u);release(id);
    CHECK(begin("robot.health","{}",0)==0 && vmError==argIndexOutOfRange);cleanup(&f);
}
static OBJ sample(const char *reply,const char *field) {
    vmError=0;vars[0]=text(reply);vars[1]=text(field);OBJ args[]={vars[0],vars[1]};
    OBJ reading=healthSamplePrimitive(2,args);CHECK(reading && !vmError);vars[2]=reading;
    CHECK(IS_TYPE(reading,ListType) && obj2int(FIELD(reading,0))==4);return reading;
}
static void typedReadingsAndMovingRoots(void) {
    const char *reply="{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"healthy\":false,\"degraded\":true,\"simulation\":true,\"battery\":{\"percent\":73.25,\"volts\":7.8},\"cpu_temp_c\":-0.0005,\"imu\":{\"ready\":true,\"consecutive_stale_blocks\":25}}}";
    unsigned before=sentBytes;
    OBJ reading=sample(reply,"battery.percent");
    CHECK(!strcmp(obj2str(FIELD(reading,1)),"ok"));CHECK(obj2int(FIELD(reading,2))==7325);
    CHECK(!strcmp(obj2str(FIELD(reading,3)),"0.01%"));CHECK(!strcmp(obj2str(FIELD(reading,4)),"simulation"));
    OBJ arg=reading;CHECK(obj2int(readingValuePrimitive(1,&arg))==7325);
    reading=sample(reply,"health.state");CHECK(!strcmp(obj2str(FIELD(reading,2)),"degraded"));
    reading=sample(reply,"imu.state");CHECK(!strcmp(obj2str(FIELD(reading,2)),"frozen"));
    reading=sample(reply,"cpu_temp_c");CHECK(obj2int(FIELD(reading,2))==-1);
    reading=sample("{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"healthy\":false}}","battery.volts");
    CHECK(!strcmp(obj2str(FIELD(reading,1)),"unknown"));arg=reading;vmError=0;
    CHECK(readingValuePrimitive(1,&arg)==falseObj && vmError==argIndexOutOfRange);
    reading=sample("{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"healthy\":false}}","bus.consecutive_errors");CHECK(FIELD(reading,2)==zeroObj);
    reading=sample("{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"healthy\":false,\"battery\":{}}}","battery.volts");CHECK(!strcmp(obj2str(FIELD(reading,1)),"invalid"));
    reading=sample("{\"jsonrpc\":\"2.0\",\"id\":null,\"error\":{\"code\":-32004,\"message\":\"unavailable\"}}","healthy");CHECK(!strcmp(obj2str(FIELD(reading,1)),"error"));
    reading=sample("{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"healthy\":false,\"cpu_temp_c\":1073741.824}}","cpu_temp_c");CHECK(!strcmp(obj2str(FIELD(reading,1)),"out_of_range"));
    /* Force String allocation GC within record construction, retaining the
     * prior temporary root and both original VM argument globals correctly. */
    vars[0]=text(reply);vars[1]=text("battery.percent");vars[2]=zeroObj;
    tempGCRoot=text("previous temporary root");
    int free=wordsFree();CHECK(free>30);CHECK(newObj(ByteArrayType,free-14,zeroObj)!=falseObj);
    OBJ args[]={vars[0],vars[1]};vmError=0;reading=healthSamplePrimitive(2,args);CHECK(reading && !vmError);vars[2]=reading;
    CHECK(!strcmp(obj2str(tempGCRoot),"previous temporary root"));
    CHECK(obj2int(FIELD(reading,0))==4 && obj2int(FIELD(reading,2))==7325);
    CHECK(!strcmp(obj2str(FIELD(reading,1)),"ok") && !strcmp(obj2str(FIELD(reading,4)),"simulation"));
    CHECK(FIELD(reading,5)==zeroObj);CHECK(wordsFree()>30);CHECK(sentBytes==before);
    tempGCRoot=falseObj;
}
int main(void) {
    memInit();addMicroduckPrims();primitiveValidation();repliesAndFraming();securityBeforeFirstByte();cancellationSlotsAndRecovery();quoteAndIdentifierBoundary();typedReadingsAndMovingRoots();
    linuxMicroduckClose();smallvmArenaDestroy();
    printf("{\"result\":\"PASS\",\"checks\":%u,\"scope\":\"native Unix fixture sockets and real VM memory; peer/write fault providers; no robot hardware\"}\n",checks);return 0;
}
