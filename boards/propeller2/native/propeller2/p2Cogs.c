/* SPDX-License-Identifier: MPL-2.0 */
/* Physical cog interpreters; main-cog services own heap and pin operations. */
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
    volatile int nativePending;
    volatile int nativeActive;
    P2NativeJob nativeFunction;
    void *nativeArgument;
    volatile int active;
    volatile int stop;
    volatile int paused;
    volatile int event;
    int eventChunk;
    int eventWhere;
    OBJ eventValue;
    int lastError;
    volatile int requestState; /* 0 idle, 1 published, 2 servicing, 3 complete */
    int requestOpcode;
    int requestSet;
    const char *requestName; /* immutable persistent bytecode */
    int requestCount;
    OBJ *requestArgs; /* points into this worker's rooted Task stack */
    OBJ requestResult;
    uint8 requestError;
    int requestSleep;
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
int p2WorkerValueAllowed(OBJ value) {
    return p2Scalar(value) || IS_TYPE(value, StringType) ||
        IS_TYPE(value, ListType) || IS_TYPE(value, ByteArrayType);
}

int p2WorkerLiteralAllowed(OBJ value) {
    /* Worker literals are in immutable persistent code, never allocated heap
       objects. Heap values arrive through rooted globals or main services. */
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
        while (workers[cog].active || workers[cog].nativePending || workers[cog].nativeActive) _waitx(64);
        /* Reset/edit can clear the heap immediately after stopping. Never
           retain an undelivered object return into that cleared heap. */
        workers[cog].event = 0;
        workers[cog].eventValue = falseObj;
        workers[cog].requestState = 0;
        workers[cog].requestResult = falseObj;
    }
}

static void sharedEnter(void) {
    while (!_locktry(sharedLock)) {
        /* Do not pause with a copied heap argument on a native C stack.
           The holder performs no allocation or GC and always releases. */
        _waitx(32);
    }
}

OBJ p2ReadShared(int index) {
    if (index < 0 || index >= MAX_VARS) return fail(indexOutOfRangeError);
    sharedEnter();
    OBJ value = vars[index];
    _lockrel(sharedLock);
    if (p2IsWorker() && !p2WorkerValueAllowed(value)) return fail(primitiveNotImplemented);
    return value;
}

void p2WriteShared(int index, OBJ value) {
    if (index < 0 || index >= MAX_VARS) { fail(indexOutOfRangeError); return; }
    if (p2IsWorker() && !p2WorkerValueAllowed(value)) { fail(primitiveNotImplemented); return; }
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
    /* Object and pin instructions are serviced by the main cog. */
    if (opcode == 0 || (opcode >= 2 && opcode <= 37)) return 1;
    if (opcode >= 43 && opcode <= 73 && opcode != 70) return 1;
    return opcode == 41 || opcode == 75 || opcode == 76 ||
        (opcode >= 80 && opcode <= 94) || opcode == 126 || opcode == 127;
}

int p2PrimitiveNeedsService(int set, const char *name) {
    if (set == DataPrims) return !strcmp(name, "makeList") || !strcmp(name, "range") ||
        !strcmp(name, "addLast") || !strcmp(name, "delete") || !strcmp(name, "newByteArray") ||
        !strcmp(name, "freeMemory");
    if (set != IOPrims) return 0;
    const char *names[] = {"p2BitDensity", "p2FilterConfigure", "p2FilterInfo", "p2FilterInput", "p2AsyncWords", "p2SyncTransmitWords", "p2SyncReceiveWords", "p2SerialSendHex", "p2SerialReadHex", "p2SerialBusy", "p2LogicInput", "p2LevelInput", "p2CaptureRead", "p2CaptureInfo", "p2StreamRead", "p2Duty", "p2FeedbackPWM", "p2DACNoise", "p2DAC16",
        "p2ADCSetup", "p2Scope", "p2ConfigureInputs", "p2ListAtomicAdd", "p2PadRaw", "p2PadNamed", "p2Configure",
        "p2PinSample", "p2PinPeekHex", "p2PinAck", "p2Pulse", "p2Transition", "p2PWM",
        "p2UART", "p2UARTWrite", "p2UARTRead", "p2DAC8", "p2SmartPin", "p2SmartPinRaw",
        "p2Frequency", "p2PinRelease", "p2PinReady", "p2PinRead", "p2PinReadHex",
        "p2PinModeHex", "p2PinWriteX", "p2PinWriteY", "p2PinCount", "p2PinUsable"};
    for (int i = 0; i < sizeof(names)/sizeof(names[0]); i++) if (!strcmp(name, names[i])) return 1;
    return 0;
}

int p2WorkerPrimitiveAllowed(int set, const char *name) {
    if (!p2IsWorker()) return 1;
    if (p2PrimitiveNeedsService(set, name)) return 1;
    if (set != 3) return 0;
    return !strcmp(name, "p2Cog") || !strcmp(name, "p2SharedRead") ||
        !strcmp(name, "p2SharedWrite") || !strcmp(name, "p2SharedAdd") ||
        !strcmp(name, "p2LocalPinDIR") ||
        !strcmp(name, "p2RuntimeRevision") || !strcmp(name, "p2ScaleSample");
}

OBJ p2RequestService(int opcode, int set, const char *name, int count, OBJ *args) {
    Worker *worker = &workers[_cogid()];
    worker->requestOpcode = opcode; worker->requestSet = set;
    worker->requestName = name; worker->requestCount = count; worker->requestArgs = args;
    worker->requestResult = falseObj; worker->requestError = 0;
    worker->requestState = 1;
    while (worker->requestState != 3) {
        /* Only a fixed stack pointer and immutable code pointer are held here.
           GC forwards the stack arguments and the published result. */
        if (p2WorkerPoll()) { worker->requestState = 0; return falseObj; }
        _waitx(64);
    }
    OBJ result = worker->requestResult;
    uint8 error = worker->requestError;
    p2InterpreterContexts[_cogid()].sleepUsecs = worker->requestSleep;
    worker->requestState = 0;
    if (error) return fail(error);
    return result;
}

void p2ServiceWorkerRequests(void) {
    if (!ready || p2IsWorker()) return;
    for (int cog = 0; cog < COGS; cog++) {
        Worker *worker = &workers[cog];
        if (!worker->active || worker->stop || worker->requestState != 1) continue;
        worker->requestState = 2;
        P2InterpreterContext saved = p2InterpreterContexts[mainCogID];
        p2InterpreterContexts[mainCogID].error = 0;
        p2InterpreterContexts[mainCogID].sleepUsecs = 0;
        worker->requestResult = worker->requestOpcode < 0 ?
            doPrimitiveCall(worker->requestSet, worker->requestName, worker->requestCount, worker->requestArgs) :
            p2ExecuteServiceOpcode(worker->requestOpcode, worker->requestCount, worker->requestArgs);
        worker->requestError = p2InterpreterContexts[mainCogID].error;
        worker->requestSleep = p2InterpreterContexts[mainCogID].sleepUsecs;
        p2InterpreterContexts[mainCogID] = saved;
        worker->requestState = 3;
    }
}

void p2MarkWorkerRoots(void (*visit)(OBJ)) {
    for (int cog = 0; cog < COGS; cog++) {
        Worker *w = &workers[cog];
        if (w->active && w->task.status != unusedTask)
            for (int j = 0; j < w->task.sp; j++) visit(w->task.stack[j]);
        if (w->requestState == 3) visit(w->requestResult);
        if (w->event == 3) visit(w->eventValue);
    }
}
void p2ForwardWorkerRoots(OBJ (*visit)(OBJ)) {
    for (int cog = 0; cog < COGS; cog++) {
        Worker *w = &workers[cog];
        if (w->active && w->task.status != unusedTask)
            for (int j = 0; j < w->task.sp; j++) w->task.stack[j] = visit(w->task.stack[j]);
        if (w->requestState == 3) w->requestResult = visit(w->requestResult);
        if (w->event == 3) w->eventValue = visit(w->eventValue);
    }
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
        if (event == 3 && !p2ReturnHasSpace(worker->eventValue)) continue;
        if (event == 1) sendTaskDone(worker->eventChunk);
        else if (event == 2) sendTaskError(worker->eventChunk, worker->lastError, worker->eventWhere);
        else if (event == 3) sendTaskReturnValue(worker->eventChunk, worker->eventValue);
        worker->event = 0;
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
        if (worker->nativePending) {
            worker->nativeActive = 1;
            worker->nativePending = 0;
            worker->nativeFunction(worker->nativeArgument, &worker->stop);
            worker->nativeActive = 0;
            continue;
        }
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
            worker->requestState = 0;
            worker->active = 0;
        }
    }
}

static int requestedCog(int count, OBJ *args, int position) {
    if (count <= position || !isInt(args[position])) return -1;
    int cog = obj2int(args[position]);
    return cog >= 0 && cog < COGS && cog != mainCogID && cog != receiverCogID ? cog : -1;
}

static int ensureWorker(int cog) {
    Worker *worker = &workers[cog];
    if (!worker->initialized) {
        if (_cogchk(cog)) return 0; /* never replace another cog */
        workerStacks[cog] = (uint32_t *) (((uint32_t) workerStorage[cog] + 15U) & ~15U);
        for (int i = 0; i < C_STACK_WORDS + 2 * GUARD_WORDS; i++) workerStacks[cog][i] = STACK_PATTERN;
        int started = _cogstart_C_cog(workerLoop, worker, &workerStacks[cog][GUARD_WORDS],
                                    C_STACK_WORDS * sizeof(uint32_t), cog);
        if (started < 0) return 0;
        while (!worker->initialized) _waitx(64);
    }
    return 1;
}
int p2NativeRunning(int cog) {
    return cog >= 0 && cog < COGS && (workers[cog].nativePending || workers[cog].nativeActive);
}
int p2NativeCanStart(int cog) {
    return !p2IsWorker() && cog >= 0 && cog < COGS && cog != mainCogID && cog != receiverCogID &&
        !workers[cog].active && !p2NativeRunning(cog) && (workers[cog].initialized || !_cogchk(cog));
}
int p2NativeStart(int cog, P2NativeJob function, void *argument) {
    if (p2IsWorker() || cog < 0 || cog >= COGS || cog == mainCogID || cog == receiverCogID ||
        workers[cog].active || p2NativeRunning(cog) || !ensureWorker(cog) || !stackOK(cog)) return 0;
    Worker *worker = &workers[cog];
    worker->event = 0; worker->eventValue = falseObj;
    worker->stop = 0;
    worker->nativeFunction = function; worker->nativeArgument = argument;
    worker->nativePending = 1;
    while (worker->nativePending) _waitx(64);
    return 1;
}
void p2NativeStop(int cog) {
    if (cog < 0 || cog >= COGS || !p2NativeRunning(cog)) return;
    workers[cog].stop = 1;
    while (p2NativeRunning(cog)) _waitx(64);
}

OBJ primP2CogStart(int count, OBJ *args) {
    if (p2IsWorker()) return fail(primitiveNotImplemented);
    int cog = requestedCog(count, args, 1);
    if (cog < 0 || !IS_TYPE(args[0], StringType)) return falseObj;
    int chunk = chunkIndexForFunction(obj2str(args[0]));
    if (chunk < 0 || workers[cog].active || p2NativeRunning(cog)) return falseObj;
    Worker *worker = &workers[cog];
    p2CollectWorkerEvents();
    if (!ensureWorker(cog)) return falseObj;
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
    worker->requestState = 0;
    memset(&p2InterpreterContexts[cog], 0, sizeof(P2InterpreterContext));
    worker->active = 1;
    return trueObj;
}

OBJ primP2CogStop(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0);
    if (p2IsWorker() || cog < 0) return falseObj;
    workers[cog].stop = 1;
    while (workers[cog].active || workers[cog].nativePending || workers[cog].nativeActive) _waitx(64);
    workers[cog].event = 0;
    workers[cog].eventValue = falseObj;
    workers[cog].requestState = 0;
    workers[cog].requestResult = falseObj;
    return trueObj;
}
OBJ primP2CogRunning(int count, OBJ *args) {
    int cog = requestedCog(count, args, 0);
    return cog >= 0 && (workers[cog].active || p2NativeRunning(cog)) ? trueObj : falseObj;
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
    return p2WorkerValueAllowed(value) ? value : fail(primitiveNotImplemented);
}
OBJ primP2SharedWrite(int count, OBJ *args) {
    int index = sharedIndex(count, args);
    if (index < 0 || count < 2 || !p2WorkerValueAllowed(args[1])) return fail(primitiveNotImplemented);
    p2WriteShared(index, args[1]);
    return args[1];
}
OBJ primP2SharedAdd(int count, OBJ *args) {
    int index = sharedIndex(count, args);
    if (index < 0 || count < 2) return fail(notEnoughArguments);
    return p2AddShared(index, args[1]);
}
OBJ primP2ListAtomicAdd(int count, OBJ *args) {
    if (p2IsWorker()) return fail(primitiveNotImplemented); /* must use the service */
    if (count != 3 || !IS_TYPE(args[0], ListType)) return fail(needsListError);
    if (!isInt(args[1]) || !isInt(args[2])) return fail(needsIntegerError);
    int index = obj2int(args[1]), length = obj2int(FIELD(args[0], 0));
    if (index < 1 || index > length || (uint32_t)index >= WORDS(args[0])) return fail(indexOutOfRangeError);
    OBJ old = FIELD(args[0], index);
    if (!isInt(old)) return fail(needsIntegerError);
    OBJ result = int2obj(obj2int(old) + obj2int(args[2]));
    FIELD(args[0], index) = result;
    return result;
}
OBJ primP2RuntimeRevision(int count, OBJ *args) { (void) count; (void) args; return int2obj(8); }
