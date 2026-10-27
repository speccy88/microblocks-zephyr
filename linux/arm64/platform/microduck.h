/* SPDX-License-Identifier: MPL-2.0 */
#ifndef SMALLVM_LINUX_MICRODUCK_H
#define SMALLVM_LINUX_MICRODUCK_H

#define LINUX_MICRODUCK_MAX_JOBS 4u
#define LINUX_MICRODUCK_MAX_REQUEST 8192u
#define LINUX_MICRODUCK_MAX_REPLY 65536u
#define LINUX_MICRODUCK_MAX_ID 1073741823u

/* Configure before primsInit/addMicroduckPrims. NULL disables the adapter.
 * This copies a canonical absolute pathname; it does not probe/connect.
 * Returns 0 on success, -1 with errno=EINVAL for an invalid path.
 * Reconfiguration closes/frees all jobs; IDs are never reused in this process.
 * Jobs/results are not durable across VM process shutdown/restart. */
int linuxMicroduckConfigure(const char *path);
void linuxMicroduckPoll(void);
/* Cancel only locally pending work. Sent operations have unknown outcome;
 * terminal jobs remain available for inspection. No robot rollback/stop claim. */
void linuxMicroduckCancelPending(void);
void linuxMicroduckClose(void);
/* Primitive set 22, appended without renumbering older sets:
 * configured()->Boolean; quote(String)->JSON String; jobs()->List of IDs;
 * begin(method:String, paramsJSON:String, confirmed:Boolean)->positive ID;
 * status(ID)->pending/ready/error/unknown; result(ID)->terminal JSON-RPC;
 * release(ID)->command (explicitly discards even a pending/unknown outcome).
 * Standard VM errors: arity28, string14, integer13, boolean12, invalid/blocked/
 * unconfirmed/pending32, absent/released ID18, disabled27, exhausted slots10.
 * Poll/cancellation failures update terminal JSON/status only, never a task's
 * global error. Unknown is reserved for retained possibly executed outcomes.
 * The configured reporter means a CLI path was supplied; it does no I/O and
 * does not claim that a gateway/robot is reachable or authenticated. */
void addMicroduckPrims(void);

#endif
