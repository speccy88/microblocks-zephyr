/* SPDX-License-Identifier: MPL-2.0 */
/* Real physical cog workers. The first worker ABI is deliberately scalar-only. */
#include <stdint.h>
#include <string.h>
#include <propeller2.h>
#include "interp.h"

#define COGS 8
#define C_STACK_WORDS 2048
#define GUARD_WORDS 4
#define STACK_PATTERN 0xc09a5afeU
#define RECENT_US 10000000U

typedef struct {
    volatile int initialized;
    volatile int active;
    volatile int stop;
    volatile int paused;
    volatile int event;
    int eventChunk;
    int eventWhere;
    OBJ eventValue;
    int lastError;
    Task task;
} Worker;

P2InterpreterContext p2InterpreterContexts[COGS];
static Worker workers[COGS];
/* Give the builtin an explicit aligned, independently guarded stack. Its size
   parameter is discarded by the pinned FlexC macro and is not a bounds check. */
static uint32_t workerStorage[COGS][C_STACK_WORDS + 2 * GUARD_WORDS + 4];
static uint32_t *workerStacks[COGS];
static volatile int pauseRequested;
static int pauseDepth;
static int mainCogID;
static int receiverCogID = -1;
static int sharedLock = -1;
static int ready;

int p2CurrentCog(void) { return _cogid(); }
int p2IsWorker(void) { return ready && (_cogid() != mainCogID); }
int p2Scalar(OBJ value) { return isInt(value) || value == falseObj || value == trueObj; }

int p2WorkerLiteralAllowed(OBJ value) {
    /* Worker literals are in immutable persistent code, never allocated heap
       objects. Shared-variable reads below refuse non-scalars before pushing. */
    return p2Scalar(value) || IS_TYPE(value, StringType);
}

void p2CogsInit(int mainCog, int receiverCog) {
    mainCogID = mainCog;
    receiverCogID = receiverCog;
    sharedLock = _locknew();
    if (sharedLock < 0) vmPanic("No P2 lock for shared variables");
    memset(workers, 0, sizeof(workers));
    memset(p2InterpreterContexts, 0, sizeof(p2InterpreterContexts));
    ready = 1;
}

int p2WorkerPoll(void) {
    if (!p2IsWorker()) return 0;
    Worker *worker = &workers[_cogid()];
    while (pauseRequested && !worker->stop) {
        worker->paused = 1;
        _waitx(64);
    }
    worker->paused = 0;
    return worker->stop;
}

void p2PauseWorkers(void) {
    if (!ready || p2IsWorker()) return;
    if (pauseDepth++) return;
    pauseRequested = 1;
    for (int cog = 0; cog < COGS; cog++) {
        while (workers[cog].active && !workers[cog].paused) _waitx(64);
    }
}

void p2ResumeWorkers(void) {
    if (!ready || p2IsWorker() || pauseDepth <= 0) return;
    if (--pauseDepth == 0) pauseRequested = 0;
}

void p2StopWorkers(void) {
    if (!ready || p2IsWorker()) return;
    for (int cog = 0; cog < COGS; cog++) workers[cog].stop = 1;
    for (int cog = 0; cog < COGS; cog++) {
        while (workers[cog].active) _waitx(64);
    }
}

static void sharedEnter(void) {
    while (!_locktry(sharedLock)) {
        if (p2IsWorker()) p2WorkerPoll();
        _waitx(32);
    }
}

OBJ p2ReadShared(int index) {
    if (index < 0 || index >= MAX_VARS) return fail(indexOutOfRangeError);
    sharedEnter();
    OBJ value = vars[index];
    _lockrel(sharedLock);
    if (p2IsWorker() && !p2Scalar(value)) return fail(needsIntegerError);
    return value;
}

void p2WriteShared(int index, OBJ value) {
    if (index < 0 || index >= MAX_VARS) { fail(indexOutOfRangeError); return; }
    if (p2IsWorker() && !p2Scalar(value)) { fail(needsIntegerError); return; }
    sharedEnter();
    vars[index] = value;
    _lockrel(sharedLock);
}

OBJ p2AddShared(int index, OBJ delta) {
    if (index < 0 || index >= MAX_VARS) return fail(indexOutOfRangeError);
    sharedEnter();
    OBJ old = vars[index];
    if (p2IsWorker() && (!isInt(old) || !isInt(delta))) {
        _lockrel(sharedLock); return fail(needsIntegerError);
    }
    int previous = evalInt(old), increment = evalInt(delta);
    if (failure()) { _lockrel(sharedLock); return falseObj; }
    OBJ value = int2obj(previous + increment);
    vars[index] = value;
    _lockrel(sharedLock);
    return value;
}

int p2WorkerOpcodeAllowed(int opcode) {
    if (!p2IsWorker()) return 1;
    /* No allocation, shared task-list mutation, serial output or GPIO access.
       forLoop (27) is excluded because its string path allocates characters. */
    if (opcode == 0 || (opcode >= 2 && opcode <= 37 && opcode != 27)) return 1;
    if (opcode >= 43 && opcode <= 73 && opcode != 70) return 1;
    return opcode == 41 || opcode == 75 || opcode == 76 || opcode == 126 || opcode == 127;
}

int p2WorkerPrimitiveAllowed(int set, const char *name) {
    if (!p2IsWorker()) return 1;
    if (set != 3) return 0;
    return !strcmp(name, "p2Cog") || !strcmp(name, "p2SharedRead") ||
        !strcmp(name, "p2SharedWrite") || !strcmp(name, "p2SharedAdd") ||
        !strcmp(name, "p2RuntimeRevision");
}

int p2WorkerEvent(int kind, int chunk, OBJ value, int where) {
    if (!p2IsWorker()) return 0;
    Worker *worker = &workers[_cogid()];
    worker->eventChunk = chunk;
    worker->eventWhere = where;
    worker->eventValue = value;
    if (kind == 2) worker->lastError = obj2int(value);
    worker->event = kind; /* publish fields before the ready marker */
    return 1;
}

void p2CollectWorkerEvents(void) {
    if (!ready || p2IsWorker()) return;
    for (int cog = 0; cog < COGS; cog++) {
        Worker *worker = &workers[cog];
        int event = worker->event;
        if (!event || worker->active) continue;
        worker->event = 0;
        if (event == 1) sendTaskDone(worker->eventChunk);
        else if (event == 2) sendTaskError(worker->eventChunk, worker->lastError, worker->eventWhere);
        else if (event == 3) sendTaskReturnValue(worker->eventChunk, worker->eventValue);
    }
}

static int stackOK(int cog) {
    for (int i = 0; i < GUARD_WORDS; i++) {
        if (workerStacks[cog][i] != STACK_PATTERN ||
                workerStacks[cog][GUARD_WORDS + C_STACK_WORDS + i] != STACK_PATTERN) return 0;
    }
    return 1;
}

static void workerLoop(void *argument) {
    Worker *worker = (Worker *) argument;
    int cog = _cogid();
    worker->initialized = 1;
    for (;;) {
        if (!worker->active) { _waitx(256); continue; }
        if (p2WorkerPoll()) worker->task.status = unusedTask;
        if (worker->task.status == waiting_micros &&
                (microsecs() - worker->task.wakeTime) < RECENT_US) worker->task.status = running;
        if (worker->task.status == running) p2RunTask(&worker->task);
        if (worker->stop) worker->task.status = unusedTask;
        if (worker->task.status == unusedTask) {
            if (p2InterpreterContexts[cog].error) worker->lastError = p2InterpreterContexts[cog].error;
            p2InterpreterContexts[cog].error = 0;
            worker->paused = 0;
            worker->active = 0;
        }
    }
}

static int requestedCog(int count, OBJ *args, int position) {
    if (count <= position || !isInt(args[position])) return -1;
    int cog = obj2int(args[position]);
    return cog >= 0 && cog < COGS && cog != mainCogID && cog != receiverCogID ? cog : -1;
}

OBJ primP2CogStart(int count, OBJ *args) {
    if (p2IsWorker()) return fail(primitiveNotImplemented);
    int cog = requestedCog(count, args, 1);
    if (cog < 0 || !IS_TYPE(args[0], StringType)) return falseObj;
    int chunk = chunkIndexForFunction(obj2str(args[0]));
    if (chunk < 0 || workers[cog].active) return falseObj;
    Worker *worker = &workers[cog];
    p2CollectWorkerEvents();
    if (!worker->initialized) {
        if (_cogchk(cog)) return falseObj; /* never replace another cog */
        workerStacks[cog] = (uint32_t *) (((uint32_t) workerStorage[cog] + 15U) & ~15U);
        for (int i = 0; i < C_STACK_WORDS + 2 * GUARD_WORDS; i++) workerStacks[cog][i] = STACK_PATTERN;
        int started = _cogstart_C_cog(workerLoop, worker, &workerStacks[cog][GUARD_WORDS],
                                    C_STACK_WORDS * sizeof(uint32_t), cog);
        if (started < 0) return falseObj;
        while (!worker->initialized) _waitx(64);
    }
    if (!stackOK(cog)) return fail(stackOverflow);
    memset(&worker->task, 0, sizeof(Task));
    worker->task.taskChunkIndex = chunk;
    worker->task.currentChunkIndex = chunk;
    worker->task.code = chunks[chunk].code;
    worker->task.ip = 4;
    worker->task.status = running;
    worker->stop = 0;
    worker->lastError = 0;
    worker->event = 0;
    memset(&p2InterpreterContexts[cog], 0, sizeof(P2InterpreterContext));
    worker->active = 1;
    return trueObj;
}

OBJ primP2CogStop(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0);
    if (p2IsWorker() || cog < 0) return falseObj;
    workers[cog].stop = 1;
    while (workers[cog].active) _waitx(64);
    return trueObj;
}
OBJ primP2CogRunning(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0);
    return cog >= 0 && workers[cog].active ? trueObj : falseObj;
}
OBJ primP2CogError(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0);
    return int2obj(cog >= 0 ? workers[cog].lastError : -1);
}
OBJ primP2CogStackOK(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0);
    return cog >= 0 && workers[cog].initialized && stackOK(cog) ? trueObj : falseObj;
}
OBJ primP2CogStackUsed(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0), words = 0;
    if (cog < 0 || !workers[cog].initialized) return zeroObj;
    for (int i = 0; i < C_STACK_WORDS; i++) if (workerStacks[cog][GUARD_WORDS + i] != STACK_PATTERN) words = i + 1;
    return int2obj(words * sizeof(uint32_t));
}

static int sharedIndex(int count, OBJ *args) {
    if (!count || !IS_TYPE(args[0], StringType)) return -1;
    return indexOfVarNamed(obj2str(args[0]));
}
OBJ primP2SharedRead(int count, OBJ *args) {
    int index = sharedIndex(count, args);
    if (index < 0) return fail(indexOutOfRangeError);
    OBJ value = p2ReadShared(index);
    return p2Scalar(value) ? value : fail(needsIntegerError);
}
OBJ primP2SharedWrite(int count, OBJ *args) {
    int index = sharedIndex(count, args);
    if (index < 0 || count < 2 || !p2Scalar(args[1])) return fail(needsIntegerError);
    p2WriteShared(index, args[1]);
    return args[1];
}
OBJ primP2SharedAdd(int count, OBJ *args) {
    int index = sharedIndex(count, args);
    if (index < 0 || count < 2) return fail(notEnoughArguments);
    return p2AddShared(index, args[1]);
}
OBJ primP2RuntimeRevision(int count, OBJ *args) { (void) count; (void) args; return int2obj(1); }
