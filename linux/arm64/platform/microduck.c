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
#include <math.h>
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

typedef enum { PARAM_EMPTY, PARAM_HELLO, PARAM_COMPONENT, PARAM_LOG, PARAM_SHOW, PARAM_SYSTEM_LOGS, PARAM_SOUND, PARAM_SKILL, PARAM_ENABLE, PARAM_POLICY, PARAM_MOTION_SIM, PARAM_SENSOR_ZONE, PARAM_SENSOR_CODE, PARAM_SNAPSHOT_HANDLE, PARAM_SNAPSHOT_ROW, PARAM_SNAPSHOT_CODE, PARAM_ROBOT_PREVIEW, PARAM_TELEMETRY_CAPTURE, PARAM_TELEMETRY_READ, PARAM_MEDIA_READING, PARAM_RELAY_PREVIEW, PARAM_PAD_IMU_READ } ParamsKind;
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
    {"robot.enable",PARAM_ENABLE,1},{"robot.loadPolicy",PARAM_POLICY,1},
    /* Local simulation wrappers only. robot.move itself remains unavailable. */
    {"microduck.motionSim.status",PARAM_EMPTY,0},
    {"microduck.motionSim.run",PARAM_MOTION_SIM,1},
    {"microduck.motionSim.cancel",PARAM_EMPTY,0},
    /* Read-only local sensor simulation wrappers, not real daemon streams. */
    {"microduck.sensorSim.tof",PARAM_SENSOR_ZONE,0},
    {"microduck.sensorSim.axis",PARAM_SENSOR_CODE,0},
    {"microduck.sensorSim.button",PARAM_SENSOR_CODE,0},
    {"microduck.sensorSim.captureTof",PARAM_EMPTY,0},
    {"microduck.sensorSim.capturePad",PARAM_EMPTY,0},
    {"microduck.sensorSim.depthRow",PARAM_SNAPSHOT_ROW,0},
    {"microduck.sensorSim.padAxis",PARAM_SNAPSHOT_CODE,0},
    {"microduck.sensorSim.padButton",PARAM_SNAPSHOT_CODE,0},
    {"microduck.sensorSim.release",PARAM_SNAPSHOT_HANDLE,0},
    {"microduck.robotSim.preview",PARAM_ROBOT_PREVIEW,1},
    {"microduck.robotSim.capture",PARAM_TELEMETRY_CAPTURE,0},
    {"microduck.robotSim.reading",PARAM_TELEMETRY_READ,0},
    {"microduck.robotSim.release",PARAM_SNAPSHOT_HANDLE,0},
    {"microduck.robotSim.model",PARAM_EMPTY,0},
    {"microduck.mediaSim.reading",PARAM_MEDIA_READING,0},
    {"microduck.mediaSim.preview",PARAM_RELAY_PREVIEW,1},
    {"microduck.imuSim.capturePad",PARAM_EMPTY,0},
    {"microduck.imuSim.read",PARAM_PAD_IMU_READ,0},
    {"microduck.imuSim.release",PARAM_SNAPSHOT_HANDLE,0}
};
static int snapshotHandle(yyjson_val *value) {
    if (!boundedText(value,32) || yyjson_get_len(value)!=32) return 0;
    const char *text=yyjson_get_str(value);
    for (int i=0;i<32;++i) if (!((text[i]>='0' && text[i]<='9') || (text[i]>='a' && text[i]<='f'))) return 0;
    return 1;
}
typedef struct { const char *name; int indices,components; const char *unit; } TelemetryField;
static const TelemetryField telemetryFields[]={
    {"move.requested",1,3,"mm/s"},{"move.applied",1,3,"mm/s"},{"move.limit_count",1,1,"count"},{"move.limited_by",64,1,"text"},
    {"loop.hz",1,1,"mHz"},{"loop.missed",1,1,"count64"},
    {"safety.fallen",1,1,"boolean"},{"safety.limp",1,1,"boolean"},{"safety.picked_up",1,1,"boolean"},{"safety.gain",1,1,"gain"},{"safety.gravity",1,3,"ppm"},
    {"joints",128,1,"mrad"},{"targets",128,1,"mrad"},{"velocities",128,1,"mrad/s"},{"currents_ma",128,1,"uA"},
    {"odom.position",1,3,"mm"},{"odom.yaw",1,1,"mrad"},{"imu.gyro",1,3,"mrad/s"},{"imu.quat",1,4,"ppm"},
    {"frames.camera.pos",1,3,"mm"},{"frames.camera.quat",1,4,"ppm"},{"frames.tof.pos",1,3,"mm"},{"frames.tof.quat",1,4,"ppm"},
    {"frames.head_imu.pos",1,3,"mm"},{"frames.head_imu.quat",1,4,"ppm"},{"skeleton.pos",128,3,"mm"},{"skeleton.quat",128,4,"ppm"},
    {"t_ns",1,1,"ns"},{"policy",1,1,"text"}
};
static const TelemetryField *findTelemetryField(yyjson_val *value) {
    for (size_t i=0;i<sizeof(telemetryFields)/sizeof(telemetryFields[0]);++i) if (equalText(value,telemetryFields[i].name)) return &telemetryFields[i];
    return NULL;
}
static int validRobotPreview(yyjson_val *params) {
    yyjson_val *method=yyjson_obj_get(params,"method"),*args=yyjson_obj_get(params,"args");
    const char *keys[4];size_t count=0;
    if (equalText(method,"robot.move")) { keys[count++]="vx_mm_s";keys[count++]="vy_mm_s";keys[count++]="vyaw_mrad_s"; }
    else if (equalText(method,"robot.head")) { keys[count++]="neck_pitch_mrad";keys[count++]="head_pitch_mrad";keys[count++]="head_yaw_mrad";keys[count++]="head_roll_mrad"; }
    else if (equalText(method,"robot.look")) { keys[count++]="x_mm";keys[count++]="y_mm";keys[count++]="z_mm";keys[count++]="neck_pitch_mrad"; }
    else if (equalText(method,"robot.pose")) { keys[count++]="z_mm";keys[count++]="roll_mrad";keys[count++]="pitch_mrad";keys[count++]="active"; }
    else if (equalText(method,"robot.mouth")) keys[count++]="open_permille";
    else if (equalText(method,"robot.enable")) { keys[count++]="on";keys[count++]="toggle"; }
    else if (equalText(method,"robot.do")) keys[count++]="skill";
    else if (equalText(method,"robot.sound")) { keys[count++]="tag";keys[count++]="hold"; }
    else if (equalText(method,"robot.loadPolicy")) { keys[count++]="slot";keys[count++]="path"; }
    else if (equalText(method,"robot.setMode")) keys[count++]="mode";
    else if (!(equalText(method,"robot.stop") || equalText(method,"robot.init") || equalText(method,"robot.relax"))) return 0;
    if (!objectKeys(args,keys,count) || yyjson_obj_size(args)!=count) return 0;
    if (equalText(method,"robot.move")) return integerBetween(yyjson_obj_get(args,keys[0]),-300,300) && integerBetween(yyjson_obj_get(args,keys[1]),-300,300) && integerBetween(yyjson_obj_get(args,keys[2]),-1500,1500);
    if (equalText(method,"robot.head")) {
        for (size_t i=0;i<4;++i) if (!integerBetween(yyjson_obj_get(args,keys[i]),-3142,3142)) return 0;
        return 1;
    }
    if (equalText(method,"robot.look")) return integerBetween(yyjson_obj_get(args,"x_mm"),-1000,1000) && integerBetween(yyjson_obj_get(args,"y_mm"),-1000,1000) && integerBetween(yyjson_obj_get(args,"z_mm"),-1000,1000) && integerBetween(yyjson_obj_get(args,"neck_pitch_mrad"),-3142,3142);
    if (equalText(method,"robot.pose")) return integerBetween(yyjson_obj_get(args,"z_mm"),-25,10) && integerBetween(yyjson_obj_get(args,"roll_mrad"),-260,260) && integerBetween(yyjson_obj_get(args,"pitch_mrad"),-260,260) && yyjson_is_bool(yyjson_obj_get(args,"active"));
    if (equalText(method,"robot.mouth")) return integerBetween(yyjson_obj_get(args,"open_permille"),0,1000);
    if (equalText(method,"robot.enable")) return yyjson_is_bool(yyjson_obj_get(args,"on")) && yyjson_is_bool(yyjson_obj_get(args,"toggle"));
    if (equalText(method,"robot.do")) return equalText(yyjson_obj_get(args,"skill"),"simulation_bow") || equalText(yyjson_obj_get(args,"skill"),"simulation_nod");
    if (equalText(method,"robot.setMode")) return equalText(yyjson_obj_get(args,"mode"),"walk") || equalText(yyjson_obj_get(args,"mode"),"roller");
    if (equalText(method,"robot.sound")) {
        yyjson_val *tag=yyjson_obj_get(args,"tag"),*hold=yyjson_obj_get(args,"hold");
        if (equalText(tag,"wheee")) return yyjson_is_bool(hold);
        return yyjson_is_null(hold) && (equalText(tag,"alarm") || equalText(tag,"greet") || equalText(tag,"inquire") || equalText(tag,"peck") || equalText(tag,"chirp") || equalText(tag,"coo"));
    }
    if (equalText(method,"robot.loadPolicy")) {
        yyjson_val *slot=yyjson_obj_get(args,"slot"),*path=yyjson_obj_get(args,"path");
        if (yyjson_is_null(slot)) return yyjson_is_null(path);
        if (equalText(slot,"walk")) return yyjson_is_null(path) || equalText(path,"/SIMULATION/walk.onnx");
        if (equalText(slot,"stand")) return yyjson_is_null(path) || equalText(path,"/SIMULATION/stand.onnx");
        return 0;
    }
    return 1;
}
static const Method *findMethod(const char *name) {
    for (size_t i = 0; i < sizeof(methods) / sizeof(methods[0]); ++i) if (!strcmp(name, methods[i].name)) return &methods[i];
    return NULL;
}
typedef struct { const char *name,*unit; int type; } MediaField;
enum { MEDIA_BOOLEAN,MEDIA_PIXELS,MEDIA_COUNTER,MEDIA_EPOCH,MEDIA_STATE,MEDIA_ROTATION,MEDIA_AUDIO };
static const MediaField mediaFields[]={
    {"audio.receive","boolean",MEDIA_AUDIO},{"audio.send","boolean",MEDIA_AUDIO},
    {"relay.state","state",MEDIA_STATE},{"relay.since","epoch_s",MEDIA_EPOCH},
    {"relay.heartbeat","epoch_s",MEDIA_EPOCH},{"relay.account_known","boolean",MEDIA_BOOLEAN},
    {"video.width","px",MEDIA_PIXELS},{"video.height","px",MEDIA_PIXELS},{"video.rotate","degrees",MEDIA_ROTATION},
    {"stream.streaming","boolean",MEDIA_BOOLEAN},{"stream.connected","boolean",MEDIA_BOOLEAN},
    {"stream.sent","count64",MEDIA_COUNTER},{"stream.dropped","count64",MEDIA_COUNTER},
    {"stream.replies","count64",MEDIA_COUNTER},{"stream.reconnects","count64",MEDIA_COUNTER},
    {"robot.healthy","boolean",MEDIA_BOOLEAN},{"robot.enabled","boolean",MEDIA_BOOLEAN}
};
static const MediaField *findMediaField(yyjson_val *value) {
    for (size_t i=0;i<sizeof(mediaFields)/sizeof(mediaFields[0]);++i) if (equalText(value,mediaFields[i].name)) return &mediaFields[i];
    return NULL;
}
static int validRelayPreview(yyjson_val *params) {
    if (!validRobotPreview(params)) return 0;
    yyjson_val *method=yyjson_obj_get(params,"method"),*args=yyjson_obj_get(params,"args");
    return !(equalText(method,"robot.move") || equalText(method,"robot.head") || equalText(method,"robot.pose") || equalText(method,"robot.mouth")
        || (equalText(method,"robot.sound") && equalText(yyjson_obj_get(args,"tag"),"wheee")));
}
typedef struct { const char *name,*unit; int samples,components,type; } ImuField;
enum { IMU_NUMBER,IMU_COUNTER,IMU_BOOLEAN,IMU_COUNT,IMU_METADATA };
static const ImuField imuFields[]={
    {"accel_raw","raw",32,3,IMU_NUMBER},{"gyro_raw","raw",32,3,IMU_NUMBER},
    {"accel_mg","mg",32,3,IMU_NUMBER},{"gyro_mdps","mdps",32,3,IMU_NUMBER},
    {"seq","count64",32,1,IMU_COUNTER},{"at_us","us_unix",32,1,IMU_COUNTER},
    {"sample_count","count",1,1,IMU_COUNT},
    {"accel_per_g","raw/g",1,1,IMU_METADATA},{"gyro_per_dps","raw/dps",1,1,IMU_METADATA},
    {"accel_max","raw",1,1,IMU_METADATA},{"gyro_max","raw",1,1,IMU_METADATA},
    {"accel_at_limit","boolean",32,3,IMU_BOOLEAN},{"gyro_at_limit","boolean",32,3,IMU_BOOLEAN}
};
static const ImuField *findImuField(yyjson_val *value) {
    for (size_t i=0;i<sizeof(imuFields)/sizeof(imuFields[0]);++i) if (equalText(value,imuFields[i].name)) return &imuFields[i];
    return NULL;
}
static int validParams(const Method *method, yyjson_val *params) {
    const char *keys[4]; size_t count = 0;
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
        case PARAM_MOTION_SIM: keys[count++]="vx_mm_s"; keys[count++]="vy_mm_s"; keys[count++]="vyaw_mrad_s"; keys[count++]="duration_ms"; break;
        case PARAM_SENSOR_ZONE: keys[count++]="row"; keys[count++]="col"; break;
        case PARAM_SENSOR_CODE: keys[count++]="code"; break;
        case PARAM_SNAPSHOT_HANDLE: keys[count++]="handle"; break;
        case PARAM_SNAPSHOT_ROW: keys[count++]="handle"; keys[count++]="row"; break;
        case PARAM_SNAPSHOT_CODE: keys[count++]="handle"; keys[count++]="code"; break;
        case PARAM_ROBOT_PREVIEW: keys[count++]="method"; keys[count++]="args"; break;
        case PARAM_TELEMETRY_CAPTURE: keys[count++]="hz"; break;
        case PARAM_TELEMETRY_READ: keys[count++]="handle"; keys[count++]="field"; keys[count++]="index"; keys[count++]="component"; break;
        case PARAM_MEDIA_READING: keys[count++]="field"; break;
        case PARAM_RELAY_PREVIEW: keys[count++]="method"; keys[count++]="args"; break;
        case PARAM_PAD_IMU_READ: keys[count++]="handle"; keys[count++]="field"; keys[count++]="sample"; keys[count++]="component"; break;
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
        case PARAM_MOTION_SIM:
            return integerBetween(yyjson_obj_get(params,"vx_mm_s"),-300,300)
                && integerBetween(yyjson_obj_get(params,"vy_mm_s"),-300,300)
                && integerBetween(yyjson_obj_get(params,"vyaw_mrad_s"),-1500,1500)
                && integerBetween(yyjson_obj_get(params,"duration_ms"),100,2000);
        case PARAM_SENSOR_ZONE:
            return integerBetween(yyjson_obj_get(params,"row"),1,8) && integerBetween(yyjson_obj_get(params,"col"),1,8);
        case PARAM_SENSOR_CODE: return integerBetween(yyjson_obj_get(params,"code"),0,65535);
        case PARAM_SNAPSHOT_HANDLE: return snapshotHandle(yyjson_obj_get(params,"handle"));
        case PARAM_SNAPSHOT_ROW: return snapshotHandle(yyjson_obj_get(params,"handle")) && integerBetween(yyjson_obj_get(params,"row"),1,8);
        case PARAM_SNAPSHOT_CODE: return snapshotHandle(yyjson_obj_get(params,"handle")) && integerBetween(yyjson_obj_get(params,"code"),0,65535);
        case PARAM_ROBOT_PREVIEW: return yyjson_obj_size(params)==2 && validRobotPreview(params);
        case PARAM_TELEMETRY_CAPTURE: return integerBetween(yyjson_obj_get(params,"hz"),1,50);
        case PARAM_TELEMETRY_READ: {
            const TelemetryField *field=findTelemetryField(yyjson_obj_get(params,"field"));
            return snapshotHandle(yyjson_obj_get(params,"handle")) && field && integerBetween(yyjson_obj_get(params,"index"),1,field->indices) && integerBetween(yyjson_obj_get(params,"component"),1,field->components);
        }
        case PARAM_MEDIA_READING: return yyjson_obj_size(params)==1 && findMediaField(yyjson_obj_get(params,"field"));
        case PARAM_RELAY_PREVIEW: return yyjson_obj_size(params)==2 && validRelayPreview(params);
        case PARAM_PAD_IMU_READ: {
            const ImuField *field=findImuField(yyjson_obj_get(params,"field"));
            return snapshotHandle(yyjson_obj_get(params,"handle")) && field && integerBetween(yyjson_obj_get(params,"sample"),1,field->samples) && integerBetween(yyjson_obj_get(params,"component"),1,field->components);
        }
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

/* Pure conversion of one health snapshot. No I/O, readiness authorization or
 * invented measurement. Unknown/invalid/error values remain explicit records. */
typedef struct { const char *name,*section,*key,*unit; int kind,scale,defaults; } HealthField;
enum { HEALTH_NUMBER, HEALTH_COUNTER, HEALTH_BOOLEAN, HEALTH_VERDICT, HEALTH_IMU_STATE };
static const HealthField healthFields[]={
    {"healthy",NULL,"healthy","boolean",HEALTH_BOOLEAN,1,0},
    {"degraded",NULL,"degraded","boolean",HEALTH_BOOLEAN,1,1},
    {"health.state",NULL,NULL,"state",HEALTH_VERDICT,1,0},
    {"battery.percent","battery","percent","0.01%",HEALTH_NUMBER,100,0},
    {"battery.volts","battery","volts","mV",HEALTH_NUMBER,1000,0},
    {"cpu_temp_c",NULL,"cpu_temp_c","mC",HEALTH_NUMBER,1000,0},
    {"motors.max_c","motors","max_c","mC",HEALTH_NUMBER,1000,0},
    {"motors.mean_c","motors","mean_c","mC",HEALTH_NUMBER,1000,0},
    {"control_loop.target_hz","control_loop","target_hz","mHz",HEALTH_NUMBER,1000,0},
    {"control_loop.achieved_hz","control_loop","achieved_hz","mHz",HEALTH_NUMBER,1000,0},
    {"control_loop.last_tick_age_ms","control_loop","last_tick_age_ms","ms",HEALTH_COUNTER,1,0},
    {"bus.consecutive_errors","bus","consecutive_errors","count",HEALTH_COUNTER,1,1},
    {"bus.startup_failures","bus","startup_failures","count",HEALTH_COUNTER,1,1},
    {"imu.ready","imu","ready","boolean",HEALTH_BOOLEAN,1,1},
    {"imu.missing","imu","missing","boolean",HEALTH_BOOLEAN,1,1},
    {"imu.stale_blocks","imu","stale_blocks","count",HEALTH_COUNTER,1,1},
    {"imu.consecutive_stale_blocks","imu","consecutive_stale_blocks","count",HEALTH_COUNTER,1,1},
    {"imu.state","imu",NULL,"state",HEALTH_IMU_STATE,1,1}
};
typedef struct { const char *status,*text,*unit,*origin; int number,boolean,isText,isBoolean; } HealthReading;

static int optionalBoolean(yyjson_val *object,const char *key,int *number) {
    yyjson_val *v=yyjson_obj_get(object,key);
    if (!v) { *number=0; return 1; }
    if (!yyjson_is_bool(v)) return 0;
    *number=yyjson_get_bool(v); return 1;
}
static void decodeHealth(yyjson_val *root,const HealthField *field,HealthReading *reading) {
    yyjson_val *result=yyjson_obj_get(root,"result"),*error=yyjson_obj_get(root,"error"),*id=yyjson_obj_get(root,"id");
    if (!yyjson_is_obj(root) || !equalText(yyjson_obj_get(root,"jsonrpc"),"2.0") || (!result==!error)
        || !(integerBetween(id,1,INT32_MAX) || (error && yyjson_is_null(id)))) return;
    if (error) {
        if (yyjson_is_obj(error) && integerBetween(yyjson_obj_get(error,"code"),INT32_MIN,INT32_MAX)
            && yyjson_is_str(yyjson_obj_get(error,"message"))) reading->status="error";
        return;
    }
    if (!yyjson_is_obj(result)) return;
    if (yyjson_is_true(yyjson_obj_get(result,"simulation")) || yyjson_is_true(yyjson_obj_get(result,"simulated"))) reading->origin="simulation";
    yyjson_val *healthy=yyjson_obj_get(result,"healthy");
    if (!yyjson_is_bool(healthy)) return;
    if (field->kind==HEALTH_VERDICT) {
        int degraded;
        if (!optionalBoolean(result,"degraded",&degraded)) return;
        reading->text=yyjson_get_bool(healthy)?"healthy":degraded?"degraded":"unhealthy";
        reading->isText=1; reading->status="ok"; return;
    }
    yyjson_val *section=field->section?yyjson_obj_get(result,field->section):result;
    if (field->section && !section && !strcmp(field->section,"bus")) {
        reading->number=0; reading->status="ok"; return; /* documented serde(default) */
    }
    if (!section || yyjson_is_null(section)) {
        if (!field->section || strcmp(field->section,"bus")) reading->status="unknown";
        return;
    }
    if (!yyjson_is_obj(section)) return;
    if (field->kind==HEALTH_IMU_STATE) {
        int ready,missing;
        yyjson_val *stale=yyjson_obj_get(section,"consecutive_stale_blocks");
        if (!optionalBoolean(section,"ready",&ready) || !optionalBoolean(section,"missing",&missing)
            || (stale && !yyjson_is_uint(stale))) return;
        /* API44 ImuHealth::FROZEN_RUN=25; convergence alone is not fresh data. */
        reading->text=missing?"missing":stale && yyjson_get_uint(stale)>=25?"frozen":ready?"converged":"not_converged";
        reading->isText=1; reading->status="ok"; return;
    }
    yyjson_val *value=yyjson_obj_get(section,field->key);
    if (!value && field->defaults) {
        reading->isBoolean=field->kind==HEALTH_BOOLEAN;
        reading->status="ok"; return;
    }
    if (!value || yyjson_is_null(value)) {
        /* Only these scalar members are Option<T> in a present section.
         * Missing required nested members are a malformed measurement. */
        if (!strcmp(field->name,"cpu_temp_c") || !strcmp(field->name,"control_loop.achieved_hz")) reading->status="unknown";
        return;
    }
    if (field->kind==HEALTH_BOOLEAN) {
        if (!yyjson_is_bool(value)) return;
        reading->isBoolean=1; reading->boolean=yyjson_get_bool(value); reading->status="ok"; return;
    }
    if (field->kind==HEALTH_COUNTER) {
        if (!yyjson_is_uint(value)) return;
        if (yyjson_get_uint(value)>1073741823u) { reading->status="out_of_range"; return; }
        reading->number=(int)yyjson_get_uint(value); reading->status="ok"; return;
    }
    if (!yyjson_is_num(value)) return;
    double scaled=yyjson_get_num(value)*field->scale;
    if (!isfinite(scaled) || scaled<=-1073741824.5 || scaled>=1073741823.5) { reading->status="out_of_range"; return; }
    reading->number=(int)(scaled>=0?scaled+0.5:scaled-0.5); reading->status="ok";
}
static OBJ readingRecord(const HealthReading *reading) {
    /* Keep the caller's temporary root in the spare capacity slot while each
     * String allocation may compact the heap. Never retain a stale field ptr. */
    OBJ list=newObj(ListType,6,tempGCRoot);
    if (list==falseObj) return falseObj;
    tempGCRoot=list; FIELD(list,0)=int2obj(4);
    const char *text[4]={reading->status,reading->text,reading->unit,reading->origin};
    for (int part=0;part<4;++part) {
        OBJ value;
        if (part==1 && !strcmp(reading->status,"ok") && !reading->isText) value=reading->isBoolean?(reading->boolean?trueObj:falseObj):int2obj(reading->number);
        else {
            const char *s=part==1 && strcmp(reading->status,"ok")?"":text[part];
            value=newStringFromBytes(s,(int)strlen(s));
            if (value==falseObj) { tempGCRoot=FIELD(tempGCRoot,5); return falseObj; }
        }
        FIELD(tempGCRoot,part+1)=value;
    }
    list=tempGCRoot; OBJ previous=FIELD(list,5); FIELD(list,5)=zeroObj; tempGCRoot=previous;
    return list;
}
static OBJ healthSamplePrimitive(int argc,OBJ *args) {
    if (argc!=2) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType) || !IS_TYPE(args[1],StringType)) return fail(needsStringError);
    char reply[LINUX_MICRODUCK_MAX_REPLY+1u],name[65]; size_t replyLength,nameLength;
    if (!copyVMString(args[0],reply,LINUX_MICRODUCK_MAX_REPLY,&replyLength)
        || !copyVMString(args[1],name,64,&nameLength)) return fail(argIndexOutOfRange);
    (void)nameLength;
    const HealthField *field=NULL;
    for (size_t i=0;i<sizeof(healthFields)/sizeof(healthFields[0]);++i) if (!strcmp(name,healthFields[i].name)) { field=&healthFields[i]; break; }
    if (!field) return fail(argIndexOutOfRange);
    yyjson_doc *document=parseJSON(reply,replyLength);
    if (!document) return fail(argIndexOutOfRange);
    HealthReading reading={.status="invalid",.text="",.unit=field->unit,.origin="unmarked"};
    decodeHealth(yyjson_doc_get_root(document),field,&reading);
    yyjson_doc_free(document);
    return readingRecord(&reading);
}
static OBJ readingValuePrimitive(int argc,OBJ *args) {
    if (argc!=1) return fail(notEnoughArguments);
    OBJ list=args[0];
    if (!IS_TYPE(list,ListType)) return fail(needsListError);
    if (WORDS(list)<5 || !isInt(FIELD(list,0)) || obj2int(FIELD(list,0))!=4) return fail(argIndexOutOfRange);
    char status[17],unit[17],origin[17]; size_t length;
    if (!copyVMString(FIELD(list,1),status,16,&length) || strcmp(status,"ok")
        || !copyVMString(FIELD(list,3),unit,16,&length) || !copyVMString(FIELD(list,4),origin,16,&length)) return fail(argIndexOutOfRange);
    OBJ value=FIELD(list,2);
    if (!isInt(value) && !isBoolean(value) && !IS_TYPE(value,StringType)) return fail(argIndexOutOfRange);
    return value;
}
/* Local simulated sensor records use the same GC-safe four-field representation
 * as health readings. No JSON scalar is coerced from null/missing/Boolean. */
static yyjson_val *sensorResult(yyjson_val *root,HealthReading *reading) {
    yyjson_val *value=yyjson_obj_get(root,"result"),*error=yyjson_obj_get(root,"error"),*id=yyjson_obj_get(root,"id");
    if (!yyjson_is_obj(root) || !equalText(yyjson_obj_get(root,"jsonrpc"),"2.0") || (!value==!error)
        || !(integerBetween(id,1,INT32_MAX) || (error && yyjson_is_null(id)))) return NULL;
    if (error) {
        if (yyjson_is_obj(error) && integerBetween(yyjson_obj_get(error,"code"),INT32_MIN,INT32_MAX) && yyjson_is_str(yyjson_obj_get(error,"message"))) reading->status="error";
        return NULL;
    }
    if (!yyjson_is_obj(value) || !yyjson_is_true(yyjson_obj_get(value,"simulation")) || !yyjson_is_false(yyjson_obj_get(value,"physical_movement_enabled"))) return NULL;
    reading->origin="simulation";
    yyjson_val *status=yyjson_obj_get(value,"status");
    if (equalText(status,"ok")) return value;
    const char *states[]={"waiting","timeout","absent","refused","detached","dropped","unobserved","unsupported","no_event","event_limit","no_target","unusable","busy","expired_or_unknown","wrong_kind","not_reported","out_of_range","rate_limited","error"};
    for (size_t i=0;i<sizeof(states)/sizeof(states[0]);++i) if (equalText(status,states[i])) { reading->status=states[i]; return value; }
    return NULL;
}
static OBJ sensorSamplePrimitive(int argc,OBJ *args) {
    if (argc!=2) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType) || !IS_TYPE(args[1],StringType)) return fail(needsStringError);
    char reply[LINUX_MICRODUCK_MAX_REPLY+1u],selector[17],handle[33];size_t length,selectorLength;
    if (!copyVMString(args[0],reply,LINUX_MICRODUCK_MAX_REPLY,&length) || !copyVMString(args[1],selector,16,&selectorLength)) return fail(argIndexOutOfRange);
    (void)selectorLength;
    int capture=!strcmp(selector,"capture"),position=!strcmp(selector,"position");
    if (!capture && !position && strcmp(selector,"raw")) return fail(argIndexOutOfRange);
    yyjson_doc *doc=parseJSON(reply,length);if (!doc) return fail(argIndexOutOfRange);
    HealthReading reading={.status="invalid",.text="",.unit=capture?"snapshot":position?"permille":"raw",.origin="unmarked"};
    yyjson_val *result=sensorResult(yyjson_doc_get_root(doc),&reading);
    yyjson_val *unit=yyjson_obj_get(result,"unit"),*value=yyjson_obj_get(result,"value"),*kind=yyjson_obj_get(result,"kind");
    if (!capture && !position) {
        if (equalText(unit,"mm")) reading.unit="mm";
        else if (equalText(unit,"pressed")) reading.unit="boolean";
    }
    if (result && equalText(yyjson_obj_get(result,"status"),"ok")) {
        if (capture) {
            yyjson_val *token=yyjson_obj_get(result,"handle");
            if ((equalText(kind,"tof_capture") || equalText(kind,"pad_capture") || equalText(kind,"telemetry_capture")) && snapshotHandle(token)) {
                memcpy(handle,yyjson_get_str(token),32);handle[32]='\0';reading.text=handle;reading.isText=1;reading.status="ok";
            }
        } else if (position) {
            yyjson_val *min=yyjson_obj_get(result,"min"),*max=yyjson_obj_get(result,"max");
            if (equalText(unit,"raw") && (equalText(kind,"axis_state") || equalText(yyjson_obj_get(result,"source"),"padd"))
                && integerBetween(value,INT32_MIN,INT32_MAX) && integerBetween(min,INT32_MIN,INT32_MAX) && integerBetween(max,INT32_MIN,INT32_MAX)) {
                int64_t low=yyjson_get_sint(min),high=yyjson_get_sint(max),raw=yyjson_get_sint(value);
                if (high>low && raw>=low && raw<=high) { reading.number=(int)(((raw-low)*1000+(high-low)/2)/(high-low));reading.status="ok"; }
            }
        } else if (equalText(unit,"pressed") && (equalText(kind,"button_state") || equalText(yyjson_obj_get(result,"source"),"padd")) && yyjson_is_bool(value)) {
            reading.isBoolean=1;reading.boolean=yyjson_get_bool(value);reading.status="ok";
        } else if (equalText(unit,"mm") && equalText(yyjson_obj_get(result,"source"),"tofd")) {
            yyjson_val *raw=yyjson_obj_get(result,"raw_distance_mm"),*status=yyjson_obj_get(result,"raw_status");
            if (integerBetween(value,1,32767) && integerBetween(raw,1,32767) && yyjson_get_sint(value)==yyjson_get_sint(raw)
                && (integerBetween(status,5,5) || integerBetween(status,9,9))) { reading.number=(int)yyjson_get_sint(value);reading.status="ok"; }
        } else if (equalText(unit,"raw") && (equalText(kind,"axis_state") || equalText(yyjson_obj_get(result,"source"),"padd"))) {
            yyjson_val *min=yyjson_obj_get(result,"min"),*max=yyjson_obj_get(result,"max");
            if (integerBetween(value,INT32_MIN,INT32_MAX) && integerBetween(min,INT32_MIN,INT32_MAX) && integerBetween(max,INT32_MIN,INT32_MAX)
                && yyjson_get_sint(max)>yyjson_get_sint(min) && yyjson_get_sint(value)>=yyjson_get_sint(min) && yyjson_get_sint(value)<=yyjson_get_sint(max)) {
                if (integerBetween(value,-1073741824,1073741823)) { reading.number=(int)yyjson_get_sint(value);reading.status="ok"; }
                else reading.status="out_of_range";
            }
        }
    }
    yyjson_doc_free(doc);return readingRecord(&reading);
}
static OBJ sensorRowPrimitive(int argc,OBJ *args) {
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType)) return fail(needsStringError);
    char reply[LINUX_MICRODUCK_MAX_REPLY+1u];size_t length;
    if (!copyVMString(args[0],reply,LINUX_MICRODUCK_MAX_REPLY,&length)) return fail(argIndexOutOfRange);
    yyjson_doc *doc=parseJSON(reply,length);if (!doc) return fail(argIndexOutOfRange);
    HealthReading base={.status="invalid",.text="",.unit="mm",.origin="unmarked"};
    yyjson_val *result=sensorResult(yyjson_doc_get_root(doc),&base),*distances=yyjson_obj_get(result,"distance_mm"),*statuses=yyjson_obj_get(result,"raw_status");
    int valid=result && equalText(yyjson_obj_get(result,"status"),"ok") && equalText(yyjson_obj_get(result,"kind"),"depth_row")
        && snapshotHandle(yyjson_obj_get(result,"handle")) && integerBetween(yyjson_obj_get(result,"row"),1,8)
        && yyjson_is_arr(distances) && yyjson_arr_size(distances)==8 && yyjson_is_arr(statuses) && yyjson_arr_size(statuses)==8;
    if (valid) for (size_t i=0;i<8;++i) if (!integerBetween(yyjson_arr_get(distances,i),-32768,32767) || !integerBetween(yyjson_arr_get(statuses,i),0,255)) valid=0;
    OBJ list=newObj(ListType,10,tempGCRoot);
    if (list==falseObj) { yyjson_doc_free(doc);return falseObj; }
    tempGCRoot=list;FIELD(list,0)=int2obj(8);
    for (int i=0;i<8;++i) {
        HealthReading reading=base;
        if (valid) {
            int raw=(int)yyjson_get_sint(yyjson_arr_get(distances,(size_t)i)),status=(int)yyjson_get_sint(yyjson_arr_get(statuses,(size_t)i));
            reading.status=(status==5 || status==9) && raw>0?"ok":status==255?"no_target":"unusable";reading.number=raw;
        }
        OBJ record=readingRecord(&reading);
        if (record==falseObj) { tempGCRoot=FIELD(tempGCRoot,9);yyjson_doc_free(doc);return falseObj; }
        FIELD(tempGCRoot,i+1)=record;
    }
    yyjson_doc_free(doc);list=tempGCRoot;OBJ previous=FIELD(list,9);FIELD(list,9)=zeroObj;tempGCRoot=previous;return list;
}
static int decimalCounter(yyjson_val *value,uint64_t *number) {
    if (!yyjson_is_str(value)) return 0;
    size_t length=yyjson_get_len(value);const char *text=yyjson_get_str(value);
    if (!length || length>20 || (length>1 && text[0]=='0')) return 0;
    uint64_t result=0;
    for (size_t i=0;i<length;++i) {
        if (text[i]<'0' || text[i]>'9') return 0;
        unsigned digit=(unsigned)(text[i]-'0');
        if (result>(UINT64_MAX-digit)/10u) return 0;
        result=result*10u+digit;
    }
    *number=result;return 1;
}
static OBJ telemetrySamplePrimitive(int argc,OBJ *args) {
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType)) return fail(needsStringError);
    char reply[LINUX_MICRODUCK_MAX_REPLY+1u],text[129];size_t length;
    if (!copyVMString(args[0],reply,LINUX_MICRODUCK_MAX_REPLY,&length)) return fail(argIndexOutOfRange);
    yyjson_doc *doc=parseJSON(reply,length);if (!doc) return fail(argIndexOutOfRange);
    HealthReading reading={.status="invalid",.text="",.unit="",.origin="unmarked"};
    yyjson_val *result=sensorResult(yyjson_doc_get_root(doc),&reading),*value=yyjson_obj_get(result,"value");
    const TelemetryField *field=findTelemetryField(yyjson_obj_get(result,"field"));
    yyjson_val *index=yyjson_obj_get(result,"index"),*component=yyjson_obj_get(result,"component");
    if (result && field && equalText(yyjson_obj_get(result,"kind"),"telemetry_reading") && integerBetween(index,1,field->indices) && integerBetween(component,1,field->components)) {
        reading.unit=field->unit;
        if ((!strcmp(field->name,"move.requested") || !strcmp(field->name,"move.applied")) && integerBetween(component,3,3)) reading.unit="mrad/s";
        if (equalText(yyjson_obj_get(result,"status"),"ok") && equalText(yyjson_obj_get(result,"unit"),reading.unit)) {
            if (!strcmp(reading.unit,"boolean")) {
                if (yyjson_is_bool(value)) { reading.isBoolean=1;reading.boolean=yyjson_get_bool(value);reading.status="ok"; }
            } else if (!strcmp(reading.unit,"ns") || !strcmp(reading.unit,"count64")) {
                uint64_t number;
                if (decimalCounter(value,&number)) {
                    if (!strcmp(reading.unit,"ns") && !number) reading.status="not_reported";
                    else { size_t n=yyjson_get_len(value);memcpy(text,yyjson_get_str(value),n);text[n]='\0';reading.text=text;reading.isText=1;reading.status="ok"; }
                }
            } else if (!strcmp(reading.unit,"text")) {
                if (yyjson_is_str(value) && yyjson_get_len(value)<=128) {
                    size_t n=yyjson_get_len(value);const unsigned char *p=(const unsigned char *)yyjson_get_str(value);int valid=1;
                    for (size_t i=0;i<n;++i) if (p[i]<32u || p[i]==127u) valid=0;
                    if (valid) { memcpy(text,p,n);text[n]='\0';reading.text=text;reading.isText=1;reading.status="ok"; }
                }
            } else if (yyjson_is_int(value)) {
                int nonnegative=!strcmp(reading.unit,"uA") || !strcmp(reading.unit,"mHz") || !strcmp(reading.unit,"count") || !strcmp(reading.unit,"gain");
                int maximum=!strcmp(reading.unit,"gain")?65535:!strcmp(reading.unit,"count")?64:1073741823;
                if (integerBetween(value,nonnegative?0:-1073741824,maximum)) { reading.number=(int)yyjson_get_sint(value);reading.status="ok"; }
                else reading.status="out_of_range";
            }
        }
    }
    yyjson_val *defaulted=yyjson_obj_get(result,"source_default");
    if (defaulted && !yyjson_is_bool(defaulted)) reading.status="invalid";
    else if (yyjson_is_true(defaulted)) {
        if (field && !strcmp(field->name,"move.limit_count") && !strcmp(reading.status,"ok") && !reading.number) reading.origin="sim_default";
        else reading.status="invalid";
    }
    yyjson_doc_free(doc);return readingRecord(&reading);
}
static int epochDecimal(yyjson_val *value) {
    if (!yyjson_is_str(value)) return 0;
    const char *s=yyjson_get_str(value);size_t n=yyjson_get_len(value),start=n && s[0]=='-'?1u:0u;
    if (n<=start || n>20 || (n-start>1 && s[start]=='0') || (start && s[start]=='0')) return 0;
    uint64_t limit=start?UINT64_C(9223372036854775808):UINT64_C(9223372036854775807),number=0;
    for (size_t i=start;i<n;++i) {
        if (s[i]<'0' || s[i]>'9') return 0;
        unsigned digit=(unsigned)(s[i]-'0');if (number>(limit-digit)/10u) return 0;
        number=number*10u+digit;
    }
    return 1;
}
static OBJ mediaSamplePrimitive(int argc,OBJ *args) {
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType)) return fail(needsStringError);
    char reply[LINUX_MICRODUCK_MAX_REPLY+1u],text[21];size_t length;
    if (!copyVMString(args[0],reply,LINUX_MICRODUCK_MAX_REPLY,&length)) return fail(argIndexOutOfRange);
    yyjson_doc *doc=parseJSON(reply,length);if (!doc) return fail(argIndexOutOfRange);
    HealthReading reading={.status="invalid",.text="",.unit="",.origin="unmarked"};
    yyjson_val *result=sensorResult(yyjson_doc_get_root(doc),&reading),*value=yyjson_obj_get(result,"value");
    const MediaField *field=findMediaField(yyjson_obj_get(result,"field"));
    if (result && field && equalText(yyjson_obj_get(result,"kind"),"media_reading") && equalText(yyjson_obj_get(result,"unit"),field->unit)) {
        reading.unit=field->unit;
        if (equalText(yyjson_obj_get(result,"status"),"ok")) {
            if (field->type==MEDIA_BOOLEAN && yyjson_is_bool(value)) { reading.isBoolean=1;reading.boolean=yyjson_get_bool(value);reading.status="ok"; }
            else if (field->type==MEDIA_PIXELS || field->type==MEDIA_ROTATION) {
                if (integerBetween(value,field->type==MEDIA_PIXELS?1:0,1073741823)
                    && (field->type!=MEDIA_ROTATION || integerBetween(value,0,0) || integerBetween(value,90,90) || integerBetween(value,180,180) || integerBetween(value,270,270))) {
                    reading.number=(int)yyjson_get_sint(value);reading.status="ok";
                }
            } else if (field->type==MEDIA_COUNTER || field->type==MEDIA_EPOCH) {
                uint64_t number;
                if ((field->type==MEDIA_COUNTER && decimalCounter(value,&number)) || (field->type==MEDIA_EPOCH && epochDecimal(value))) {
                    size_t n=yyjson_get_len(value);memcpy(text,yyjson_get_str(value),n);text[n]='\0';reading.text=text;reading.isText=1;reading.status="ok";
                }
            } else if (field->type==MEDIA_STATE) {
                const char *states[]={"signed_out","connecting","registered","refused","retrying"};
                for (size_t i=0;i<5;++i) if (equalText(value,states[i])) { reading.text=states[i];reading.isText=1;reading.status="ok"; }
            }
        }
    } else if (result) reading.status="invalid";
    yyjson_doc_free(doc);return readingRecord(&reading);
}
static OBJ imuSamplePrimitive(int argc,OBJ *args) {
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],StringType)) return fail(needsStringError);
    char reply[LINUX_MICRODUCK_MAX_REPLY+1u],text[33];size_t length;
    if (!copyVMString(args[0],reply,LINUX_MICRODUCK_MAX_REPLY,&length)) return fail(argIndexOutOfRange);
    yyjson_doc *doc=parseJSON(reply,length);if (!doc) return fail(argIndexOutOfRange);
    HealthReading reading={.status="invalid",.text="",.unit="",.origin="unmarked"};
    yyjson_val *result=sensorResult(yyjson_doc_get_root(doc),&reading),*value=yyjson_obj_get(result,"value");
    if (result && equalText(yyjson_obj_get(result,"kind"),"pad_imu_capture")) {
        reading.unit="snapshot";
        if (equalText(yyjson_obj_get(result,"status"),"ok")) {
            yyjson_val *handle=yyjson_obj_get(result,"handle");
            if (snapshotHandle(handle) && integerBetween(yyjson_obj_get(result,"sample_count"),1,32)) {
                memcpy(text,yyjson_get_str(handle),32);text[32]='\0';reading.text=text;reading.isText=1;reading.status="ok";
            }
        }
    } else if (result && equalText(yyjson_obj_get(result,"kind"),"pad_imu_reading")) {
        const ImuField *field=findImuField(yyjson_obj_get(result,"field"));
        if (field && equalText(yyjson_obj_get(result,"unit"),field->unit) && integerBetween(yyjson_obj_get(result,"sample"),1,field->samples) && integerBetween(yyjson_obj_get(result,"component"),1,field->components)) {
            reading.unit=field->unit;
            if (equalText(yyjson_obj_get(result,"status"),"ok")) {
                if (field->type==IMU_BOOLEAN && yyjson_is_bool(value)) { reading.isBoolean=1;reading.boolean=yyjson_get_bool(value);reading.status="ok"; }
                else if (field->type==IMU_COUNTER) {
                    uint64_t number;
                    if (decimalCounter(value,&number)) { size_t n=yyjson_get_len(value);memcpy(text,yyjson_get_str(value),n);text[n]='\0';reading.text=text;reading.isText=1;reading.status="ok"; }
                } else if (field->type!=IMU_BOOLEAN && integerBetween(value,field->type==IMU_METADATA?0:field->type==IMU_COUNT?1:-1073741824,field->type==IMU_COUNT?32:1073741823)) {
                    reading.number=(int)yyjson_get_sint(value);reading.status="ok";
                }
            }
        } else reading.status="invalid";
    } else if (result) reading.status="invalid";
    yyjson_doc_free(doc);return readingRecord(&reading);
}
static PrimEntry entries[]={
    {"configured",configuredPrimitive},{"quote",quotePrimitive},{"jobs",jobsPrimitive},{"begin",beginPrimitive},
    {"status",statusPrimitive},{"result",resultPrimitive},{"release",releasePrimitive},
    {"healthSample",healthSamplePrimitive},{"readingValue",readingValuePrimitive},
    {"sensorSample",sensorSamplePrimitive},{"sensorRow",sensorRowPrimitive},{"telemetrySample",telemetrySamplePrimitive},
    {"mediaSample",mediaSamplePrimitive},{"imuSample",imuSamplePrimitive}
};
void addMicroduckPrims(void) { initialize(); addPrimitiveSet(MicroDuckPrims,"microduck",(int)(sizeof(entries)/sizeof(entries[0])),entries); }
