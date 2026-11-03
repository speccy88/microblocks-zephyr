/* SPDX-License-Identifier: MPL-2.0 */
#ifndef P2_COGS_H
#define P2_COGS_H

typedef struct {
    uint8 error;
    int sleepUsecs;
    uint32 timerStart;
} P2InterpreterContext;

typedef void (*P2NativeJob)(void *argument, volatile int *stop);
int p2NativeCanStart(int cog);
int p2NativeStart(int cog, P2NativeJob function, void *argument);
void p2NativeStop(int cog);
int p2NativeRunning(int cog);

extern P2InterpreterContext p2InterpreterContexts[8];
int p2CurrentCog(void);
int p2IsWorker(void);
void p2CogsInit(int mainCog, int receiverCog);
int p2WorkerPoll(void);
int p2WorkerOpcodeAllowed(int opcode);
int p2WorkerPrimitiveAllowed(int set, const char *name);
int p2Scalar(OBJ value);
int p2WorkerLiteralAllowed(OBJ value);
int p2WorkerValueAllowed(OBJ value);
int p2PrimitiveNeedsService(int set, const char *name);
OBJ p2RequestService(int opcode, int set, const char *name, int count, OBJ *args);
OBJ p2ExecuteServiceOpcode(int opcode, int count, OBJ *args);
int p2ReturnHasSpace(OBJ value);
void p2ServiceWorkerRequests(void);
void p2MarkWorkerRoots(void (*visitor)(OBJ));
void p2ForwardWorkerRoots(OBJ (*visitor)(OBJ));
void p2PauseWorkers(void);
void p2ResumeWorkers(void);
void p2StopWorkers(void);
void p2CollectWorkerEvents(void);
int p2WorkerEvent(int kind, int chunk, OBJ value, int where);
OBJ p2ReadShared(int index);
void p2WriteShared(int index, OBJ value);
OBJ p2AddShared(int index, OBJ delta);
void p2RunTask(Task *task);
OBJ primP2CogStart(int count, OBJ *args);
OBJ primP2CogStop(int count, OBJ *args);
OBJ primP2CogRunning(int count, OBJ *args);
OBJ primP2CogError(int count, OBJ *args);
OBJ primP2CogStackOK(int count, OBJ *args);
OBJ primP2CogStackUsed(int count, OBJ *args);
OBJ primP2SharedRead(int count, OBJ *args);
OBJ primP2SharedWrite(int count, OBJ *args);
OBJ primP2SharedAdd(int count, OBJ *args);
OBJ primP2RuntimeRevision(int count, OBJ *args);
OBJ primP2ListAtomicAdd(int count, OBJ *args);

#endif
