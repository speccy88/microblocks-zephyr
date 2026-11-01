# Filesystem-only commissioning preflight specification

## Contract written before implementation

The next arrival-preparation tool inspects local host and explicitly supplied
configuration/socket/runtime-directory metadata. Python 3.11+ standard library,
Linux only for filesystem/Unix checks. Output is bounded JSON on stdout; there
is no output-file, connect, mutation, install, service or repair operation.

Expected entry point:

~~~sh
python -B linux/microduck/preflight.py --config /absolute/private/config.json --runtime-dir /absolute/private/runtime
~~~

Both inputs are optional. Omitted inputs remain NOT_CHECKED. The existing
private-config schema and gateway/Upstream validation remain authoritative.
Socket metadata uses the existing canonical path/owner/mode checks. The
configured numeric UID comes from the operator; it is not guessed or promoted
from a filesystem observation. Unknown/malformed inputs produce fixed codes
rather than echoing config contents, paths, exception text or secrets.

Host checks cover Linux, ARM64 with 64-bit pointers, Python 3.11+, unprivileged
execution, glibc>=2.34 and the required Unix/peer-credential primitives. Runtime
metadata may report free bytes and a read-only mount flag; no write probe is
performed. Private runtime ownership/mode is checked without creating it.

## Required boundaries and acceptance

- No socket creation, connection, hello, RPC, listener, subprocess, systemctl,
  SSH, BLE, credential access or permission/service changes. No directory/file
  creation, chmod, unlink, lock or repair occurs in the inspection function.
- Use bounded O_RDONLY config loading with O_NOFOLLOW/O_NONBLOCK. Reject
  unknown schema/services, duplicate keys, non-finite JSON, invalid UID/path,
  non-private/foreign files, symlinks, FIFO/devices and oversized input.
- Refuse missing/untrusted/replaced socket metadata and private-runtime
  mismatches without correcting them. Recheck inode metadata for a point-in-time
  observation; still make no durable identity or race-free authorization claim.
- Actual API version and connected peer UID remain null. Expected API 44,
  socket-file UID and supported SO_PEERCRED are separate observations.
- Overall result is BLOCKED when local prerequisites fail, otherwise INCOMPLETE.
  It is never robot-ready/PASS: daemon identity/API/caller policy, runtime I/O,
  physical robot behavior and motion authorization remain unverified.
- Preserve all existing actual-versus-simulated evidence. Automated tests use
  private Linux filesystem/Unix-socket fixtures and injected host observations,
  and prohibit connections, processes and writes during inspection. No actual
  MicroDuck, Edge-control request or safety-denied test is used.

CLI exits 2 for BLOCKED and 0 for an INCOMPLETE observation. A zero exit status
means the limited inspection completed without a local blocker, not acceptance
of a device or a grant of authority. Existing gateway use must still verify
SO_PEERCRED and authoritative daemon refusals at each real connection.
The standalone CLI disables Python bytecode-cache writes for its process as
well. Use -B when launching through any alternate Python module entry point.

## Implemented use and acceptance

Run from the reviewed source checkout. No package installation or gateway
startup is required. With no arguments, only host prerequisites are observed;
configuration and runtime metadata remain NOT_CHECKED. A private config may
select any subset of the existing robot/config/updater services. Missing,
unsafe or changed metadata produces blockers without a repair command.

Twenty-two focused Linux tests pass with zero skips. They use injected host
observations and actual private filesystem/Unix-socket metadata fixtures;
the inspection is forbidden from connecting, starting processes or writing.
Tests cover private-file/UID/schema bounds, FIFO/symlink/mode/parent refusal,
inode replacement, read-only/unknown space, fixed errors and CLI cache absence.
The complete repository validator passes 203 tests with zero skips. The merged
watch still has 169 passing Node tests and preserves all seven editor profiles.

The same source was hash-verified and executed on the authorized Raspberry Pi 5
stand-in with no config or runtime argument. It observed AArch64/64-bit pointers,
Python 3.13.5, glibc 2.41 and UID 1000, and correctly returned INCOMPLETE. All host
prerequisite checks passed, but no daemon/API/socket/robot acceptance was claimed.
Only private project source/evidence files were created by the deployment wrapper;
the inspection itself made no changes, requests or bytecode-cache files. Existing
services, credentials, security settings and startup were not changed.

[Preflight evidence](tests/preflight-validation.json),
[actual Pi host observation](tests/preflight-pi-host.json),
[focused output](tests/preflight-focused.txt) and
[full repository output](tests/preflight-linux.txt) retain the exact scope.
See the [remaining-objectives ledger](../../docs/MICRODUCK_REMAINING_OBJECTIVES.md)
for missing software versus physical/platform/deployment gates.
