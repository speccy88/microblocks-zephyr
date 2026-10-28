# P4 hosted connection opening and heartbeat

Historical deadline follow-up. The current firmware and resolution of the
small-packet/SD-session delay are in [P4 TCP latency](P4_TCP_LATENCY.md).

The graphical failure was diagnosed before changing production code. On the
unchanged a4e49b75 application/30ef126c editor pair, the browser opened the
correct same-origin WebSocket but closed it at an observed5094ms, before the
handshake. Packaged GP's open-port loop has a5000ms deadline. A fresh browser
HTTP200 from the real P4 measured8906.404ms in TCP establishment, then prompt
headers; no proxy/cache was involved. The application deadline is shorter than
a measured successful TCP opening.

Independent read-only probes reproduced a five-second TCP timeout among
successful HTTP/WS openings. Eight ICMP probes with a1s bound returned six
replies (42..795ms) and two timeouts. This diagnoses loss/latency in the link
or stack, but not its physical/driver cause. There is no evidence justifying
a C6 firmware, router, security or power-save change. The pinned WebSocket
unregister implementation closes both logical and real sockets.

The bounded correction sets GP's opening wait to30s only for the hosted P4
editor. USB P4 and other packages retain5s. The existing one-socket provider
keeps its same-origin rules, waits for native ready, and never retries or
replays VM/file commands. The panel indicates that Wi-Fi connection is opening.
Changing the bound does not claim to eliminate packet loss.

Tests compare the actual generated adapter with its packaged GP wait: an8.9s
ready event fails under the old5s deadline but succeeds under the hosted30s
deadline; a never-ready connection still closes once, with one socket and no
command replay. Existing secure-origin and old-socket tests remain required.
The actual new gp_wasm.data must contain the30s wait and the bundle hashes must
match the manifest. Native layout/memory/model/DMA guards remain required.

Physical acceptance uses a full-digest-checked application/editor pair, native
station/SD-read/asset verification, then actual GUI connection/reconnection
through ordinary UI controls. Preserve SD contents, settings and compiled
rollback images; no test loss, router/security change or browser restriction
bypass is needed. Keep the patch isolated from Pi/main and retain all failed
baseline observations separately from the after-change results.

The first installed follow-up guarded native application was
`330c891527b9615d07da6cfca1bf9669387835d744fece84d6f6dfa82b6b0a2f`,
15,375,952 bytes at0x2000. Its matching165-file editor is
`24da57e0444b54ea85d3e0f338ab14b532bab4f0d259ec8476346078cf1aa318`,
3,570,589 bytes at0xfe0000. Both full baseline digests and both final device
digests passed; COM5 was closed after reset2026-10-27T15:14:22Z. The old
`a4e49b75`/`30ef126c` compiled pair and installation receipt remain preserved.
No raw device dump, settings/C6/SD write or loss trigger was used.

The incremental helper rejected the581632-byte local application delta before
device access. Its256KiB limit was retained; the normal full-image path was
used after layout/model/memory audits. Model bytes are unchanged. Native boot
then confirmed saved association, valid assets, compatibility PASS, AP off and
normal recovery status (zero losses/retries; diagnostic loss action disabled).
Concurrent read-only SD listing returned zero MBFILES entries and HTTP200 with
the matching new GP data hash in23.265s. Graphical acceptance is recorded
separately from these native checks.

The first on-board follow-up exposed a second, distinct deadline: two ordinary
GUI openings reached HTTP101/native ready after15.284s and15.190s, exchanged
version/initialization messages, then stopped receiving pongs and closed.
Read-only native state still showed ready/associated, zero loss events/retries
and usable native stacks. GP's heartbeat checks both expire after8s.
Two independent native connections each received eight exact pongs: cadence
0.5s returned0.031s then9.719..10.641s; cadence2.5s returned0.031s then
9.672..9.703s. Both connections remained usable for over85s. Sending more
frequently did not remove the delay. The8s GUI heartbeat is therefore also
shorter than successful measured responses.

The final hosted P4 package extends both heartbeat checks to a finite30s;
other packages retain8s. Command and file deadlines, ping frequency, ownership,
origin checks and no-replay behavior are unchanged. This tolerates observed
latency; it does not resolve its driver/link cause. Packaging fails if either
expected heartbeat anchor changes, preventing a partial patch.

The final installed guarded application is
`f63d1cf781dd93dab8ae449b4c51086e0ae8c5f0586235eb8e8a741dcf6f16f1`
(15,375,952 bytes at0x2000), with editor
`3b29bdfa5f086a51b2e769af244c347328379499db02449f79007e744a9a9e5a`
(3,570,589 bytes at0xfe0000). This second update changed only one4KiB
application sector (0xe27000) plus the matching editor partition. Both old/new
full device pair digests passed; reset2026-10-27T15:36:14Z, COM5 closed.
The first follow-up compiled pair and the earlier known-good a4e49b75 pair
remain preserved. Native build/VM/RPC/layout/model/DMA audits pass, with72
root checks and6 generated-adapter tests.

The final real GUI opened after15.235s, displayed the native P4 identity and
remained connected for over120s after ready, until a deliberate UI disconnect.
The file-manager session request still failed its existing shorter deadline;
the open-session reply was observed20.109s after its request. Only that session
request was sent; no SD file operation or replay followed. Native SD listing
and matching HTTP GP-data read passed again on the final pair (HTTP24.328s).
Graphical file-manager use under this latency remains a limitation. Increasing
file/session deadlines or changing the driver needs separate evidence and
lease analysis; the connection tolerance change does not claim that result.

Final graphical acceptance contains two successful openings (both15.235s).
The first stayed connected beyond120s after ready, then was manually closed;
the second reconnected after the old WebSocket's close event and stayed
connected for over100s after ready. Largest observed gaps between pong frames
were26.367s and19.902s respectively, with no unexpected close. This verifies tolerance beyond
the former8s deadline. Immediate reconnect while the old socket is still
closing, longer stability, full power removal and elimination of TCP latency
are not claimed. The final editor was left connected; Network observation
was disabled. SD data, C6, credentials, router/security and Pi/main were unchanged.
