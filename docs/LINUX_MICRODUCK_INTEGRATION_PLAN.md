# Isolated Linux/MicroDuck integration plan

All work is in `microblocks-zephyr-pi5`, on local branch
`codex/pi5-microduck-preparation`, based on
`9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226`. No push, release or Pages deployment
has occurred. The active P4 checkout, board and serial ports are not accessed.
Integrate only after coordinating with its owner; do not overwrite their shared
portal/editor changes or push an older local main over newer remote work.

## Auditable units

| Commit | Unit | Review focus |
|---|---|---|
| `a860d36c64eee7c24ca32c16cb883063d4d87256` | Guarded ARM64 packaging and BLE protocol mock core | Installer validation, API-44 permissions, confidentiality gate and initial candidate scope. |
| `c880c87c2592ca02553bc14829eb8ecdc70eb83a` | Native LP64 port, Pi acceptance, loopback editor/bridge, portal and Unix gateway | Offset object representation, all GC roots, bytecode/code persistence, Host/Origin/PTY checks, board-specific compiler paths. |
| `191d52404a1b2e40709b05b598a62377215c63be` | Nonblocking MicroDuck primitive set 22, UBL and explicit Unix simulation | Native buffer lifetime, bounded jobs, error/unknown outcomes, method/confirmation/discovery gates, cooperative block compiler behavior. |
| `84e060e` then `91a6b51` then `957e42f` then `b9cf30c` | Candidate provenance and corresponding source | Preserve order: initial tool, declared LF/CRLF conversions, protocol-runner binding, installer-compatible artifact name/release notes. No history rewrite needed. |
| `5e37b60` | In-memory browser lab, portal copy/link, graphical evidence | Fictional-only controls, no network/GATT/secrets, confirmation consumption and clean reset. All seven editor code hashes preserved. |
| `af742e8` | Additive native CI and local execution reports | Explicit architecture/pins, skip/empty-suite guards, no publication; hosted runs remain untested. |
| `87f0bbc` | Requirements/status/checklist and release receipts | Six requested guides, physical/simulated/blocked matrix, publication/conflict gates and final validation index. |
| Typed-readings checkpoint following `87f0bbc` | Two pure converters, source-backed sensor/readiness records, library0.2 and eighteen feature tests | Preserve signed31 scaling, optional/default/invalid semantics, simulation origin and GC roots. New VM and library must travel together. Graphical typed-example execution remains unverified. |
| Protected-console checkpoint following `1876772` | Production controller/panel, explicit in-memory fixture, portal link and CI | Strict JSON, confidential-only structured secrets, one-use confirmation, fresh skills, unknown outcomes/no replay. No actual robot or Edge-control request used in acceptance. |
| Update-watch checkpoint following `961b440` | Authenticated notification-only progress, bounded watch ownership and fictional preview | Preserve the no-reply upstream protocol, final write-ACK races, time/event/visible-sample bounds, omitted arbitrary detail, no update outcome inference and no replay. |

Use `git log --reverse --format=fuller 9db5c3f..HEAD` and `git diff --stat
9db5c3f..HEAD` in this checkout for exact final identities. The candidate's
`candidate.json` records its exact recipe commit and every artifact hash.
Evidence indexes: [core Pi](../linux/arm64/tests/README.md),
[native MicroDuck on Pi with simulated daemons](../linux/microduck/tests/README.md),
[browser simulation](../linux/microduck/docs/commissioning-browser.md).

A transferable local bundle is retained at
`build-artifacts/pi5-microduck-integration.bundle`, containing this branch's
commits after the base above. Verify it with `git bundle verify` in a repository
that contains that base; the separate checkpoint records its SHA-256 and exact
branch tip. The bundle is local review material, not a pushed branch or release.

## Conflict handling and integration order

1. Fetch and inspect the destination history read-only after the P4 owner
   supplies its intended integration point. Create a separate integration branch
   or checkout. Preserve both existing worktrees and their uncommitted work.
2. Apply isolated commits in order. Never force-push. Do not copy a complete
   older portal/packager file over its newer P4 version to resolve a conflict.
3. Merge the new Linux/MicroDuck paths first. Resolve shared
   `tools/package_pages.py`, `web/portal/portal-adapter.js`, `portal-core.js`,
   `portal.js`, `index.html`, `portal.css`, `dependencies/*`, `tools/validate.py`,
   `tests/*` and documentation indexes by preserving board-specific behavior.
   The exact changed set comes from the diff, not this risk list.
4. Retain the original five boards, P4 compiler/primitive mappings, project
   persistence and transport ownership. Linux is selected only by its own
   profile; MicroDuck appends primitive set 22 only in its own editor. Its lab
   adds one standalone HTML asset and a labelled link; real discovery remains
   passive and sends no RPC write.
5. Add `.github/workflows/linux-arm64.yml` without replacing existing workflows.
   Run its guarded suites and the repository validator. Hosted CI must execute
   on both actual runner architectures before claiming hosted CI PASS.
6. Rebuild all seven editor profiles from the exact GP asset pin. Compare the
   original five profiles against the destination P4 owner's expected artifacts;
   rerun portal, file/project and board tests relevant to any conflicts. Avoid
   touching boards owned by other tasks.
7. If any native input changes, regenerate prepared-source hashes, rebuild the
   ordinary and sanitizer binaries, and repeat the applicable safe Pi runtime
   acceptance. Never reuse an earlier native report for a changed executable.

## Local candidate review

`tools/prepare_linux_arm64_release.py` reads a retained ordinary native report,
binary and source manifest, verifies committed recipe inputs and regenerates
the tested sources. It creates a deterministic binary archive with the exact
installer convention `smallvm-linux-arm64-VERSION.tar.gz`, corresponding source,
notices, installer/uninstaller, release notes, reports and SHA256SUMS. It always
sets `published: false` and `available: false`. Its evidence is auditable data,
not a signed runtime attestation. Keep independent logs and review the report.

Review `SOURCE-CHECKOUT.json` in the source archive: only exact LF-to-CRLF
checkout conversion is allowed, both hashes are recorded, and tested raw bytes
are preserved. Building `prepared/build.sh` requires no upstream download. The
retained source archive rebuilt natively on the Pi to the identical binary hash
and passed its real self-test. Source-level tests and package-header fixtures
are separately labelled; neither replaces the Pi evidence.

Reproduce local preparation with the retained native files (use a fresh output
directory; replace all paths/version with the reviewed inputs):

```sh
python3 tools/prepare_linux_arm64_release.py \
  --binary /absolute/native/smallvm \
  --manifest /absolute/native/source/source-manifest.json \
  --report /absolute/native/report.json \
  --upstream /absolute/pinned-smallvm-git \
  --version IMMUTABLE_CANDIDATE_VERSION \
  --output build-artifacts/release-candidates/NEW_DIRECTORY
```

The currently retained local candidate is based on port commit
`b9cf30cb3e51e03e5204629b073d55f37295b6e6`. Its
[artifact manifest](../linux/arm64/tests/release-candidate.json),
[checksums](../linux/arm64/tests/release-candidate-SHA256SUMS.txt), and
[actual Pi rebuild report](../linux/arm64/tests/candidate-source-rebuild.json)
are committed. Its actual archives remain local build artifacts. Regenerate
provenance after final integration; do not substitute an integrated commit
into an existing manifest by hand.

That candidate predates the typed-reading primitive names and library0.2.
The newer [typed native evidence](../linux/microduck/tests/typed-validation.json)
has different ordinary/sanitizer binary hashes. Regenerate a candidate from
those exact reports after integration; do not publish the earlier binary with
the newer library. The original bundle above is retained unchanged; the typed
checkpoint has a separate `build-artifacts/pi5-microduck-typed-readings.bundle`.

## Publication gates

- Obtain the coordinated integrated commit and run all required regression
  checks. Review the corresponding source/licenses, build flags, architecture,
  glibc requirement and exact binary/native evidence binding.
- Actual optional user-service startup and OS reboot are still NOT RUN. Isolate
  any required confirmation rather than changing startup/security settings while
  the user is unavailable. A release may only describe the tested scope and
  explicitly retain these limitations; it must not imply reboot-ready service.
- Publish the reviewed immutable release assets only when parent coordination
  permits it. Verify the real GitHub tag, exact artifact name, bytes, checksum,
  source archive and installer URL; a locally generated URL is not evidence.
- Test installation from those published downloads on the Pi in a private prefix,
  including failure preservation/reinstall/upgrade/uninstall. Test actual copied
  PowerShell and POSIX commands without embedding credentials.
- Set `web/portal/linux-release.json` to available only with reviewed, verified
  version, binary archive hash, exact installer commit and installer hash. Keep
  strict host verification, dependency checks and the decoded-script review.
- Deploy through the repository's existing Pages workflow after P4 integration.
  Verify the live board selector, simulation link, editor assets, copy command
  and browser transport. Trusted WSS or the supported loopback editor is needed;
  do not claim a working Pages-to-LAN connection from the tunnel test.
- Follow the [arrival checklist](MICRODUCK_CHRISTMAS_HARDWARE_VALIDATION_CHECKLIST.md)
  before changing any physical MicroDuck status. Actual BLE confidentiality,
  shipping API/OS/socket UIDs, battery/sensors and motion remain unverified.

## Denied and pending paths

The extra Pi numeric-specific test action was safety-denied and was not retried.
An optional delegated native-design/library-contract review was also flagged
for possible cybersecurity risk, did not complete and was not retried. Concrete
implementation tests are reported separately; they do not imply that review
passed. Neither action is pending in a loop. There is no current approval
request. Publication coordination, actual OS reboot/startup, hosted CI and
physical robot acceptance remain explicit separate gates.

The typed example additionally has an isolated graphical-test blocker: requesting
native control of Edge window18679338 via `cua.getApp` timed out awaiting app
approval. After Fred explicitly requested a fresh attempt, one new request for
that same window was made. The platform stopped Computer Use because it could
not determine the current browser URL confidently enough to enforce policy.
There was no input, retry or bypass after that stop. The editor loads the example
and connects to its Pi VM, but graphical compilation/execution was not verified.
This does not block the completed native bytecode, fixture or repository tests.

The protected console is tested independently through actual RPC/core/UI modules
with mock DOM/GATT. It does not retry that native Edge-control request. Its
graphical browser and deployed Pages acceptance remain unverified. A separate
`build-artifacts/pi5-microduck-console.bundle` retains this checkpoint. The
native C/header and the typed VM binaries are unchanged in this UI-only phase.

## Published upstream rehearsal

The separate branch `codex/pi5-upstream-integration-20261027` remains at
`e5fd3d0a1d77f7024cade03136e9d6e859947cc5`. Its original local merge
`acd315cd711b80e317d0651c4d43f836fba3dbdc` tested published main
`9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226` and exactly preparation961b440.
Its zero-conflict historical result, fresh native Pi checks and bundle remain
unchanged. See the [original receipt](../evidence/2026-10-27/linux-integration/README.md).

The new separate branch `codex/pi5-watch-integration-20261027` incorporates
update-watch commit `62fb982268a9db7f749057842696ad3b74c6b85b` into that candidate.
One append-only integration-plan conflict was resolved by retaining the original
receipt and this follow-up scope. Product code merged automatically; its exact
staged bytes are compared with the preparation commit before testing.
The current fetched main still has zero upstream-only commits. Unpublished P4
work was not read, and its eventual committed integration point still needs
coordination and affected regression checks. No shared-main push, release,
Pages deployment or P4 checkout modification is performed by this rehearsal.

The [watch/preflight receipt](../evidence/2026-10-27/microduck-watch-integration/README.md)
records merge 5272ce8, its resolved documentation conflict, 169 Node/181 Linux
checks and preserved seven-profile package. A following additive preflight
commit passes 22 focused tests and 203 repository tests and observes only the
authorized Pi stand-in host, returning INCOMPLETE without daemon requests.
See the [remaining objectives](MICRODUCK_REMAINING_OBJECTIVES.md) for missing
software versus physical, platform and publication gates. The earlier candidate
and preparation branches remain unchanged; only the new isolated branch advances.

## Receive-only camera follow-up

The same isolated watch-integration branch adds the source-reviewed
[camera observer core](../linux/microduck/CAMERA.md). There is no new merge from
shared main and no change to the P4 checkout, native SmallVM, UBL, BLE transport,
gateway or existing portal user flows. The package includes four additive JS
modules; no existing page instantiates a live RTC/signaling connection.

The observer consumes the producer's SDP offer, sends its recvonly video answer,
disables audio, closes unexpected channels and can send only the fixed read-only
media.video metadata request on the broad upstream control channel. It contains
no robot control forwarding or live dialer. Internal tests use actual module
logic with synthetic signaling/RTC/media, not a live camera, and claim neither
decoded frames nor authenticated identity. A source audit records exact pinned
Pollen and GStreamer protocol hashes. See the
[camera evidence](../linux/microduck/tests/camera-validation.json).

Review the eventual live signaling adapter, viewer and privacy/transport trust
separately. The pinned LAN server has no authentication gate, so a discovered
producer or successful session is not trusted identity or authority to move.
Keep the real BLE confidentiality gate unchanged. Physical camera/codec/browser
acceptance, native camera primitives and continuous motion remain incomplete.
No blocked Edge operation or previously denied test is retried for this phase.

## Viewer follow-up

The additive [viewer contract](../linux/microduck/CAMERA_VIEWER.md) extends the
isolated camera core with a video-element frame observer, reported-rotation
layout and explicitly fictional standalone lab. Its native interface is driven
only by an owned video-only stream; it does not add signaling transport, robot
commands or local capture. Simulation exercises the actual observer through
internal fake media callbacks and a locally drawn test card, never a real media
decoder. The portal adds a lab link and the package copies camera.html plus
the new modules. Existing console/simulation HTML and security gates stay intact.

Native decoded-frame, graphical, trusted signaling and physical camera acceptance
remain unverified. Shared main, active P4 checkout, native VM, UBL and gateway are
unchanged. No existing stopped/denied operation is retried for these independent
viewer and packaging tests.

## Motion-simulation follow-up

The [bounded motion lab](../linux/microduck/MOTION_SIMULATION.md) adds three
local-only simulation wrapper names to the existing native job validator, a
dedicated simulator subclass and a separate UBL library/status-only example.
The real gateway allowlist and camera/BLE transports are unchanged; robot.move
itself remains unavailable to the native begin primitive. Only the internal
recording service receives source-shaped notifications. No real motor/controller
or live WebRTC transport is opened, and no applied movement is modelled.

The C source changed, so the earlier binary/source reports and local ARM64
candidate remain historical. This phase needs a fresh verified native build
for tests and new ARM64/Pi acceptance before release. The MicroDuck GP profile
intentionally gains the simulation library/example; the six other profiles and
every hardware-connection flag must remain unchanged. Do not attach the local
simulation wrapper methods to the real gateway or production BLE console.
Publication and final binary/library pairing remain held for P4 coordination.
