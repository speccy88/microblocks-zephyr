/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */
/* Private same-UID MicroDuck gateway jobs. No threads, shell, TCP or retries.
 * JSON parser/writer: pinned MIT-licensed yyjson, see dependencies/json.json. */
#define _GNU_SOURCE
#include "microduck.h"
#include "vm/interp.h"
#include "third_party/yyjson/yyjson.h"
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <poll.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#ifndef MICRODUCK_TIMEOUT_MS
#define MICRODUCK_TIMEOUT_MS 10000u
#endif
#define IO_SLICE 2048u
#define JSON_DEPTH 16u
#define JSON_NODES 8192u
#define JSON_MEMBERS 256u
#define JSON_POOL_BYTES (2u * 1024u * 1024u)

typedef enum { JOB_UNUSED, JOB_PENDING, JOB_READY, JOB_ERROR, JOB_UNKNOWN } JobState;
typedef enum { ST_NEW, ST_CONNECTING, ST_SENDING, ST_READING } JobStage;
typedef struct { dev_t device, parentDevice; ino_t inode, parentInode; } SocketIdentity;
typedef struct {
    uint32_t id;
    int fd;
    JobState state;
    JobStage stage;
    uint64_t deadline;
    SocketIdentity identity;
    size_t requestLength, sent, replyLength;
    char request[LINUX_MICRODUCK_MAX_REQUEST + 1u];
    char reply[LINUX_MICRODUCK_MAX_REPLY + 1u];
} Job;
static Job jobs[LINUX_MICRODUCK_MAX_JOBS];
static char gatewayPath[sizeof(((struct sockaddr_un *)0)->sun_path)];
static uint32_t nextJobID = 1u;
static int initialized;
static union { max_align_t align; unsigned char bytes[JSON_POOL_BYTES]; } jsonPool;

static void initialize(void) {
    if (initialized) return;
    for (unsigned i = 0; i < LINUX_MICRODUCK_MAX_JOBS; ++i) jobs[i].fd = -1;
    initialized = 1;
}
static uint64_t nowMilliseconds(void) {
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) return 0;
    return (uint64_t)value.tv_sec * 1000u + (uint64_t)value.tv_nsec / 1000000u;
}
static void closeFD(Job *job) { if (job->fd >= 0) close(job->fd); job->fd = -1; }
static void clearJob(Job *job) { closeFD(job); memset(job, 0, sizeof(*job)); job->fd = -1; }

void linuxMicroduckClose(void) {
    initialize();
    for (unsigned i = 0; i < LINUX_MICRODUCK_MAX_JOBS; ++i) clearJob(&jobs[i]);
    memset(gatewayPath, 0, sizeof(gatewayPath));
}
static int canonicalSyntax(const char *path) {
    if (!path || path[0] != '/') return 0;
    size_t length = strnlen(path, sizeof(gatewayPath));
    if (length < 2 || length >= sizeof(gatewayPath) || path[length - 1] == '/') return 0;
    const char *start = path + 1;
    for (const char *p = start;; ++p) {
        if (((unsigned char)*p < 32u && *p) || (unsigned char)*p == 127u) return 0;
        if (*p == '/' || !*p) {
            size_t part = (size_t)(p - start);
            if (!part || (part == 1 && start[0] == '.') || (part == 2 && start[0] == '.' && start[1] == '.')) return 0;
            if (!*p) break;
            start = p + 1;
        }
    }
    return 1;
}
int linuxMicroduckConfigure(const char *path) {
    linuxMicroduckClose();
    if (!path) return 0;
    if (!canonicalSyntax(path)) { errno = EINVAL; return -1; }
    memcpy(gatewayPath, path, strlen(path) + 1u);
    return 0;
}

static int socketIdentity(SocketIdentity *identity) {
    char parent[sizeof(gatewayPath)], resolved[PATH_MAX];
    memcpy(parent, gatewayPath, strlen(gatewayPath) + 1u);
    char *slash = strrchr(parent, '/');
    if (!slash || slash == parent) return 0; /* '/' cannot be a private 0700 parent. */
    *slash = '\0';
    if (!realpath(parent, resolved) || strcmp(parent, resolved)) return 0;
    struct stat directory, socketInfo;
    if (lstat(parent, &directory) || !S_ISDIR(directory.st_mode) || directory.st_uid != geteuid() || (directory.st_mode & 07777) != 0700) return 0;
    if (lstat(gatewayPath, &socketInfo) || !S_ISSOCK(socketInfo.st_mode) || socketInfo.st_uid != geteuid() || (socketInfo.st_mode & 07777) != 0600) return 0;
    *identity = (SocketIdentity){socketInfo.st_dev, directory.st_dev, socketInfo.st_ino, directory.st_ino};
    return 1;
}
static int sameIdentity(const SocketIdentity *a, const SocketIdentity *b) {
    return a->device == b->device && a->inode == b->inode && a->parentDevice == b->parentDevice && a->parentInode == b->parentInode;
}
static int trustedPeer(Job *job) {
    struct ucred peer; socklen_t size = sizeof(peer);
    SocketIdentity current;
    return !getsockopt(job->fd, SOL_SOCKET, SO_PEERCRED, &peer, &size) && size == sizeof(peer) && peer.pid > 0 && peer.uid == geteuid() && socketIdentity(&current) && sameIdentity(&current, &job->identity);
}

static void terminalError(Job *job, int code, const char *outcome, int remote) {
    closeFD(job);
    memset(job->request, 0, sizeof(job->request));
    job->requestLength = 0;
    int length = snprintf(job->reply, sizeof(job->reply),
        "{\"jsonrpc\":\"2.0\",\"id\":%u,\"error\":{\"code\":%d,\"message\":\"%s\",\"data\":{\"outcome\":\"%s\"}}}",
        job->id, code, remote ? "MicroDuck gateway refused the request" : "Local MicroDuck gateway operation did not complete", outcome);
    job->replyLength = length > 0 ? (size_t)length : 0;
    job->state = !strcmp(outcome, "unknown") ? JOB_UNKNOWN : JOB_ERROR;
}
static void localFailure(Job *job, int code) { terminalError(job, code, job->sent ? "unknown" : "not_sent", 0); }
void linuxMicroduckCancelPending(void) {
    initialize();
    for (unsigned i = 0; i < LINUX_MICRODUCK_MAX_JOBS; ++i) if (jobs[i].state == JOB_PENDING) localFailure(&jobs[i], -32012);
}

static int equalText(const yyjson_val *value, const char *text) {
    return yyjson_is_str(value) && yyjson_get_len(value) == strlen(text) && !memcmp(yyjson_get_str(value), text, strlen(text));
}
static int boundedText(const yyjson_val *value, size_t maximum) {
    if (!yyjson_is_str(value)) return 0;
    size_t length = yyjson_get_len(value);
    if (!length || length > maximum) return 0;
    const unsigned char *text = (const unsigned char *)yyjson_get_str(value);
    for (size_t i = 0; i < length; ++i) if (text[i] < 32u || text[i] == 127u) return 0;
    return 1;
}
static int integerBetween(const yyjson_val *value, int64_t minimum, int64_t maximum) {
    if (!yyjson_is_int(value)) return 0;
    if (yyjson_is_uint(value)) return maximum >= 0 && yyjson_get_uint(value) <= (uint64_t)maximum && (minimum <= 0 || yyjson_get_uint(value) >= (uint64_t)minimum);
    int64_t number = yyjson_get_sint(value);
    return number >= minimum && number <= maximum;
}
static int strictTree(yyjson_val *value, unsigned depth, unsigned *nodes) {
    if (!value || depth > JSON_DEPTH || ++*nodes > JSON_NODES) return 0;
    if (yyjson_is_obj(value)) {
        if (yyjson_obj_size(value) > JSON_MEMBERS) return 0;
        yyjson_val *keys[JSON_MEMBERS]; size_t count = 0;
        yyjson_obj_iter iterator = yyjson_obj_iter_with(value); yyjson_val *key;
        while ((key = yyjson_obj_iter_next(&iterator))) {
            for (size_t i = 0; i < count; ++i) if (yyjson_get_len(keys[i]) == yyjson_get_len(key) && !memcmp(yyjson_get_str(keys[i]), yyjson_get_str(key), yyjson_get_len(key))) return 0;
            keys[count++] = key;
            if (!strictTree(yyjson_obj_iter_get_val(key), depth + 1u, nodes)) return 0;
        }
    } else if (yyjson_is_arr(value)) {
        yyjson_arr_iter iterator = yyjson_arr_iter_with(value); yyjson_val *item;
        while ((item = yyjson_arr_iter_next(&iterator))) if (!strictTree(item, depth + 1u, nodes)) return 0;
    }
    return 1;
}
static yyjson_doc *parseJSON(char *text, size_t length) {
    yyjson_alc allocator;
    if (!yyjson_alc_pool_init(&allocator, jsonPool.bytes, sizeof(jsonPool.bytes))) return NULL;
    yyjson_doc *document = yyjson_read_opts(text, length, YYJSON_READ_NOFLAG, &allocator, NULL);
    unsigned nodes = 0;
    if (document && !strictTree(yyjson_doc_get_root(document), 0, &nodes)) { yyjson_doc_free(document); return NULL; }
    return document;
}
static int objectKeys(yyjson_val *object, const char *const *allowed, size_t count) {
    if (!yyjson_is_obj(object)) return 0;
    yyjson_obj_iter iterator = yyjson_obj_iter_with(object); yyjson_val *key;
    while ((key = yyjson_obj_iter_next(&iterator))) {
        int found = 0;
        for (size_t i = 0; i < count; ++i) if (equalText(key, allowed[i])) { found = 1; break; }
        if (!found) return 0;
    }
    return 1;
}

typedef enum { PARAM_EMPTY, PARAM_HELLO, PARAM_COMPONENT, PARAM_LOG, PARAM_SHOW, PARAM_SYSTEM_LOGS, PARAM_SOUND, PARAM_SKILL, PARAM_ENABLE, PARAM_POLICY } ParamsKind;
typedef struct { const char *name; ParamsKind params; int mutation; } Method;
static const Method methods[] = {
    {"microduck.capabilities",PARAM_EMPTY,0},{"hello",PARAM_HELLO,0},
    {"robot.health",PARAM_EMPTY,0},{"robot.policies",PARAM_EMPTY,0},{"robot.skills",PARAM_EMPTY,0},
    {"robot.model",PARAM_EMPTY,0},{"robot.vetbook",PARAM_EMPTY,0},{"pad.bindings",PARAM_EMPTY,0},
    {"system.info",PARAM_EMPTY,0},{"system.services",PARAM_EMPTY,0},{"system.logs",PARAM_SYSTEM_LOGS,0},
    {"net.status",PARAM_EMPTY,0},{"net.scan",PARAM_EMPTY,0},{"pad.status",PARAM_EMPTY,0},
    {"update.status",PARAM_EMPTY,0},{"update.check",PARAM_COMPONENT,0},{"update.listInstalled",PARAM_COMPONENT,0},
    {"update.log",PARAM_LOG,0},{"update.show",PARAM_SHOW,0},
    {"robot.sound",PARAM_SOUND,1},{"robot.do",PARAM_SKILL,1},{"robot.init",PARAM_EMPTY,1},
    {"robot.enable",PARAM_ENABLE,1},{"robot.loadPolicy",PARAM_POLICY,1}
};
static const Method *findMethod(const char *name) {
    for (size_t i = 0; i < sizeof(methods) / sizeof(methods[0]); ++i) if (!strcmp(name, methods[i].name)) return &methods[i];
    return NULL;
}
static int validParams(const Method *method, yyjson_val *params) {
    const char *keys[3]; size_t count = 0;
    switch (method->params) {
        case PARAM_EMPTY: break;
        case PARAM_HELLO: keys[count++]="api_version"; break;
        case PARAM_COMPONENT: keys[count++]="component"; break;
        case PARAM_LOG: keys[count++]="limit"; break;
        case PARAM_SHOW: keys[count++]="run"; break;
        case PARAM_SYSTEM_LOGS: keys[count++]="unit"; keys[count++]="lines"; keys[count++]="boot"; break;
        case PARAM_SOUND: keys[count++]="tag"; break;
        case PARAM_SKILL: keys[count++]="skill"; break;
        case PARAM_ENABLE: keys[count++]="on"; keys[count++]="toggle"; break;
        case PARAM_POLICY: keys[count++]="slot"; keys[count++]="path"; break;
    }
    if (!objectKeys(params, keys, count)) return 0;
    yyjson_val *value;
    switch (method->params) {
        case PARAM_EMPTY: return 1;
        case PARAM_HELLO: value=yyjson_obj_get(params,"api_version"); return !value || integerBetween(value,44,44);
        case PARAM_COMPONENT: {
            value=yyjson_obj_get(params,"component"); if (!boundedText(value,64)) return 0;
            const unsigned char *text=(const unsigned char *)yyjson_get_str(value); int alphanumeric=0;
            for (size_t i=0;i<yyjson_get_len(value);++i) { if (text[i]>=128u || !(isalnum(text[i])||text[i]=='-'||text[i]=='_')) return 0; if (isalnum(text[i])) alphanumeric=1; }
            return alphanumeric;
        }
        case PARAM_LOG: value=yyjson_obj_get(params,"limit"); return !value || integerBetween(value,1,100);
        case PARAM_SHOW: value=yyjson_obj_get(params,"run"); return !value || yyjson_is_null(value) || integerBetween(value,0,INT32_MAX);
        case PARAM_SYSTEM_LOGS: {
            value=yyjson_obj_get(params,"unit"); if (!boundedText(value,64)) return 0;
            char unit[65]; size_t length=yyjson_get_len(value); memcpy(unit,yyjson_get_str(value),length); unit[length]='\0';
            if (length>=8 && !strcmp(unit+length-8,".service")) unit[length-8]='\0';
            for (char *p=unit;*p;++p) { if ((unsigned char)*p>=128u) return 0; *p=(char)tolower((unsigned char)*p); }
            const char *units[]={"updaterd","robotd","configd","btd","padd","netpadd","mediad","tofd","nfcd","bluetooth","networkmanager"}; int found=0;
            for (size_t i=0;i<sizeof(units)/sizeof(units[0]);++i) if (!strcmp(unit,units[i])) found=1;
            if (!found) return 0;
            value=yyjson_obj_get(params,"lines"); if (value && !integerBetween(value,1,500)) return 0;
            value=yyjson_obj_get(params,"boot"); return !value || integerBetween(value,-1000,0);
        }
        case PARAM_SOUND: {
            value=yyjson_obj_get(params,"tag"); const char *tags[]={"alarm","greet","inquire","peck","chirp","coo"};
            for (size_t i=0;i<sizeof(tags)/sizeof(tags[0]);++i) if (equalText(value,tags[i])) return 1;
            return 0;
        }
        case PARAM_SKILL: return boundedText(yyjson_obj_get(params,"skill"),128);
        case PARAM_ENABLE: value=yyjson_obj_get(params,"toggle"); return yyjson_is_bool(yyjson_obj_get(params,"on")) && (!value || yyjson_is_bool(value));
        case PARAM_POLICY: value=yyjson_obj_get(params,"path"); return boundedText(yyjson_obj_get(params,"slot"),64) && (!value || yyjson_is_null(value) || (boundedText(value,512) && yyjson_get_str(value)[0]=='/'));
    }
    return 0;
}

static int validateReply(Job *job) {
    /* One NDJSON envelope, exact numeric job ID, no duplicate members or extra
     * text. Remote error text/data are replaced by a local sanitized envelope. */
    size_t length=job->replyLength;
    if (!length || job->reply[length-1]!='\n') return 0;
    --length; if (length && job->reply[length-1]=='\r') --length;
    yyjson_doc *document=parseJSON(job->reply,length);
    if (!document) return 0;
    yyjson_val *reply=yyjson_doc_get_root(document),*result=yyjson_obj_get(reply,"result"),*error=yyjson_obj_get(reply,"error");
    const char *topKeys[]={"jsonrpc","id","result","error","gateway"};
    int valid=objectKeys(reply,topKeys,5) && equalText(yyjson_obj_get(reply,"jsonrpc"),"2.0") && integerBetween(yyjson_obj_get(reply,"id"),job->id,job->id) && (!!result != !!error);
    yyjson_val *metadata=yyjson_obj_get(reply,"gateway");
    if (metadata) {
        const char *keys[]={"service","upstream_api_version","expected_api_version"};
        yyjson_val *service=yyjson_obj_get(metadata,"service");
        valid=valid && !error && objectKeys(metadata,keys,3) && yyjson_obj_size(metadata)==3 && (equalText(service,"robot")||equalText(service,"config")||equalText(service,"updater")) && integerBetween(yyjson_obj_get(metadata,"upstream_api_version"),1,255) && integerBetween(yyjson_obj_get(metadata,"expected_api_version"),44,44);
    }
    int errorCode=0; const char *outcome="rejected";
    if (valid && error) {
        const char *keys[]={"code","message","data"};
        valid=objectKeys(error,keys,3) && integerBetween(yyjson_obj_get(error,"code"),INT32_MIN,INT32_MAX) && yyjson_is_str(yyjson_obj_get(error,"message"));
        yyjson_val *details=yyjson_obj_get(error,"data");
        if (details) {
            const char *detailKeys[]={"outcome"}; yyjson_val *value=yyjson_obj_get(details,"outcome");
            valid=valid && objectKeys(details,detailKeys,1) && yyjson_obj_size(details)==1;
            if (equalText(value,"not_sent")) outcome="not_sent";
            else if (equalText(value,"unknown")) outcome="unknown";
            else if (!equalText(value,"rejected")) valid=0;
        }
        if (valid) errorCode=(int)yyjson_get_sint(yyjson_obj_get(error,"code"));
    }
    yyjson_doc_free(document);
    if (!valid) return 0;
    if (error) terminalError(job,errorCode,outcome,1);
    else {
        closeFD(job); job->replyLength=length; job->reply[length]='\0'; job->state=JOB_READY;
        memset(job->request,0,sizeof(job->request)); job->requestLength=0;
    }
    return 1;
}

static void pollJob(Job *job, uint64_t now) {
    if (!now || now >= job->deadline) { localFailure(job,-32008); return; }
    if (job->stage==ST_NEW) {
        if (!socketIdentity(&job->identity)) { localFailure(job,-32001); return; }
        job->fd=socket(AF_UNIX,SOCK_STREAM|SOCK_NONBLOCK|SOCK_CLOEXEC,0);
        if (job->fd<0) { localFailure(job,-32009); return; }
        struct sockaddr_un address={.sun_family=AF_UNIX}; memcpy(address.sun_path,gatewayPath,strlen(gatewayPath)+1u);
        int result=connect(job->fd,(struct sockaddr *)&address,(socklen_t)(offsetof(struct sockaddr_un,sun_path)+strlen(gatewayPath)+1u));
        if (result==0) job->stage=ST_SENDING;
        else if (errno==EINPROGRESS) job->stage=ST_CONNECTING;
        else localFailure(job,-32009);
        return;
    }
    if (job->stage==ST_CONNECTING) {
        struct pollfd descriptor={.fd=job->fd,.events=POLLOUT};
        int polled=poll(&descriptor,1,0);
        if (polled<0) { if (errno!=EINTR) localFailure(job,-32009); return; }
        if (!polled) return;
        int error=0; socklen_t size=sizeof(error);
        if (getsockopt(job->fd,SOL_SOCKET,SO_ERROR,&error,&size) || error) { localFailure(job,-32009); return; }
        job->stage=ST_SENDING; return;
    }
    if (job->stage==ST_SENDING) {
        if (!job->sent && !trustedPeer(job)) { localFailure(job,-32001); return; }
        size_t count=job->requestLength-job->sent; if (count>IO_SLICE) count=IO_SLICE;
        ssize_t sent=send(job->fd,job->request+job->sent,count,MSG_DONTWAIT|MSG_NOSIGNAL);
        if (sent<0) { if (errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) localFailure(job,-32009); return; }
        if (!sent) { localFailure(job,-32009); return; }
        job->sent+=(size_t)sent;
        if (job->sent==job->requestLength) job->stage=ST_READING;
        return;
    }
    size_t available=sizeof(job->reply)-job->replyLength;
    if (available>IO_SLICE) available=IO_SLICE;
    ssize_t received=recv(job->fd,job->reply+job->replyLength,available,MSG_DONTWAIT);
    if (received<0) { if (errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) localFailure(job,-32009); return; }
    if (!received) { localFailure(job,-32009); return; }
    job->replyLength+=(size_t)received;
    char *newline=memchr(job->reply,'\n',job->replyLength);
    if (job->replyLength>LINUX_MICRODUCK_MAX_REPLY) { localFailure(job,-32010); return; }
    if (newline) {
        if ((size_t)(newline-job->reply)+1u!=job->replyLength || !validateReply(job)) localFailure(job,-32011);
    } else if (job->replyLength==LINUX_MICRODUCK_MAX_REPLY) localFailure(job,-32010);
}
void linuxMicroduckPoll(void) {
    initialize(); uint64_t now=nowMilliseconds();
    for (unsigned i=0;i<LINUX_MICRODUCK_MAX_JOBS;++i) if (jobs[i].state==JOB_PENDING) pollJob(&jobs[i],now);
}

static int copyVMString(OBJ object, char *destination, size_t maximum, size_t *length) {
    if (!IS_TYPE(object,StringType)) return 0;
    const char *text=obj2str(object); size_t capacity=(size_t)WORDS(object)*4u;
    uintptr_t start=(uintptr_t)text,heap=(uintptr_t)smallvmHeapStart(),code=(uintptr_t)smallvmCodeStart();
    int inHeap=start>=heap && start<=heap+smallvmHeapBytes() && capacity<=heap+smallvmHeapBytes()-start;
    int inCode=start>=code && start<=code+smallvmCodeBytes() && capacity<=code+smallvmCodeBytes()-start;
    if ((!inHeap&&!inCode) || !capacity) return 0;
    size_t bound=capacity<maximum+1u?capacity:maximum+1u;
    const char *end=memchr(text,'\0',bound);
    if (!end) return 0;
    *length=(size_t)(end-text);
    /* String headers carry word capacity, not byte length. Only zero padding
     * may follow the first terminator; reject a hidden embedded-NUL suffix. */
    for (size_t i=*length+1u;i<capacity;++i) if (text[i]) return 0;
    memcpy(destination,text,*length); destination[*length]='\0'; return 1;
}
static Job *findJob(uint32_t id) {
    for (unsigned i=0;i<LINUX_MICRODUCK_MAX_JOBS;++i) if (jobs[i].state!=JOB_UNUSED && jobs[i].id==id) return &jobs[i];
    return NULL;
}
static int jobArgument(int argc, OBJ *args, uint32_t *id) {
    if (argc!=1) { fail(notEnoughArguments); return 0; }
    if (!isInt(args[0])) { fail(needsIntegerError); return 0; }
    int value=obj2int(args[0]);
    if (value<1) { fail(argIndexOutOfRange); return 0; }
    *id=(uint32_t)value; return 1;
}
static OBJ configuredPrimitive(int argc, OBJ *args) {
    (void)args; if (argc!=0) return fail(notEnoughArguments);
    return gatewayPath[0]?trueObj:falseObj;
}
static OBJ beginPrimitive(int argc, OBJ *args) {
    initialize();
    if (argc!=3) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType)||!IS_TYPE(args[1],StringType)) return fail(needsStringError);
    if (!isBoolean(args[2])) return fail(needsBooleanError);
    if (!gatewayPath[0]) return fail(primitiveNotImplemented);
    char methodName[129],params[LINUX_MICRODUCK_MAX_REQUEST+1u]; size_t methodLength,paramsLength;
    if (!copyVMString(args[0],methodName,128,&methodLength)||!copyVMString(args[1],params,LINUX_MICRODUCK_MAX_REQUEST,&paramsLength)) return fail(argIndexOutOfRange);
    const Method *method=findMethod(methodName); (void)methodLength;
    if (!method || (method->mutation && args[2]!=trueObj)) return fail(argIndexOutOfRange);
    yyjson_doc *document=parseJSON(params,paramsLength);
    if (!document) return fail(argIndexOutOfRange);
    char compact[LINUX_MICRODUCK_MAX_REQUEST+1024u];
    int valid=validParams(method,yyjson_doc_get_root(document));
    size_t compactLength=valid?yyjson_val_write_buf(compact,sizeof(compact),yyjson_doc_get_root(document),YYJSON_WRITE_NOFLAG,NULL):0;
    yyjson_doc_free(document);
    valid=valid && compactLength>0 && compactLength<=LINUX_MICRODUCK_MAX_REQUEST;
    if (!valid) return fail(argIndexOutOfRange);
    Job *job=NULL;
    for (unsigned i=0;i<LINUX_MICRODUCK_MAX_JOBS;++i) if (jobs[i].state==JOB_UNUSED) { job=&jobs[i]; break; }
    if (!job) return fail(insufficientMemoryError);
    if (nextJobID>LINUX_MICRODUCK_MAX_ID) return fail(argIndexOutOfRange);
    uint64_t now=nowMilliseconds(); if (!now) return fail(unspecifiedError);
    int length=snprintf(job->request,sizeof(job->request),"{\"jsonrpc\":\"2.0\",\"id\":%u,\"method\":\"%s\",\"params\":%s,\"confirmed\":%s}\n",nextJobID,methodName,compact,args[2]==trueObj?"true":"false");
    if (length<0 || (size_t)length>LINUX_MICRODUCK_MAX_REQUEST) { memset(job->request,0,sizeof(job->request)); return fail(argIndexOutOfRange); }
    job->id=nextJobID++; job->requestLength=(size_t)length; job->replyLength=job->sent=0; job->fd=-1;
    job->state=JOB_PENDING; job->stage=ST_NEW; job->deadline=now+MICRODUCK_TIMEOUT_MS;
    return int2obj(job->id);
}
static OBJ statusPrimitive(int argc, OBJ *args) {
    uint32_t id; if (!jobArgument(argc,args,&id)) return falseObj;
    Job *job=findJob(id); if (!job) return fail(indexOutOfRangeError);
    const char *status="unknown";
    switch(job->state) { case JOB_PENDING:status="pending";break;case JOB_READY:status="ready";break;case JOB_ERROR:status="error";break;default:break; }
    return newStringFromBytes(status,(int)strlen(status));
}
static OBJ resultPrimitive(int argc, OBJ *args) {
    uint32_t id; if (!jobArgument(argc,args,&id)) return falseObj;
    Job *job=findJob(id); if (!job) return fail(indexOutOfRangeError);
    if (job->state==JOB_PENDING) return fail(argIndexOutOfRange);
    return newStringFromBytes(job->reply,(int)job->replyLength);
}
static OBJ releasePrimitive(int argc, OBJ *args) {
    uint32_t id; if (!jobArgument(argc,args,&id)) return falseObj;
    Job *job=findJob(id); if (!job) return fail(indexOutOfRangeError);
    clearJob(job); return falseObj;
}
static OBJ quotePrimitive(int argc, OBJ *args) {
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType)) return fail(needsStringError);
    char input[LINUX_MICRODUCK_MAX_REQUEST+1u],output[LINUX_MICRODUCK_MAX_REQUEST+1024u]; size_t length;
    if (!copyVMString(args[0],input,LINUX_MICRODUCK_MAX_REQUEST,&length)) return fail(argIndexOutOfRange);
    yyjson_alc allocator; if (!yyjson_alc_pool_init(&allocator,jsonPool.bytes,sizeof(jsonPool.bytes))) return fail(insufficientMemoryError);
    yyjson_mut_doc *document=yyjson_mut_doc_new(&allocator); if (!document) return fail(insufficientMemoryError);
    yyjson_mut_val *string=yyjson_mut_strncpy(document,input,length); yyjson_mut_doc_set_root(document,string);
    size_t written=yyjson_mut_write_buf(output,sizeof(output),document,YYJSON_WRITE_NOFLAG,NULL);
    yyjson_mut_doc_free(document);
    if (!written || written>LINUX_MICRODUCK_MAX_REQUEST) return fail(argIndexOutOfRange);
    return newStringFromBytes(output,(int)written);
}
static OBJ jobsPrimitive(int argc, OBJ *args) {
    (void)args; if (argc!=0) return fail(notEnoughArguments);
    unsigned count=0;
    for (unsigned i=0;i<LINUX_MICRODUCK_MAX_JOBS;++i) if (jobs[i].state!=JOB_UNUSED) ++count;
    OBJ list=newObj(ListType,(int)count+1,zeroObj); if (!list) return falseObj;
    FIELD(list,0)=int2obj(count); unsigned at=1;
    for (unsigned i=0;i<LINUX_MICRODUCK_MAX_JOBS;++i) if (jobs[i].state!=JOB_UNUSED) FIELD(list,at++)=int2obj(jobs[i].id);
    return list;
}
static PrimEntry entries[]={
    {"configured",configuredPrimitive},{"quote",quotePrimitive},{"jobs",jobsPrimitive},{"begin",beginPrimitive},
    {"status",statusPrimitive},{"result",resultPrimitive},{"release",releasePrimitive}
};
void addMicroduckPrims(void) { initialize(); addPrimitiveSet(MicroDuckPrims,"microduck",(int)(sizeof(entries)/sizeof(entries[0])),entries); }
