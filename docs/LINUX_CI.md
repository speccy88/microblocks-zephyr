# Linux native CI scope

The additive [Linux workflow](../.github/workflows/linux-arm64.yml) compiles and
executes the pinned SmallVM port on native x86-64 and AArch64 GitHub-hosted CPUs.
It uses the explicit `ubuntu-24.04` and `ubuntu-24.04-arm` labels from the official
[runner image table](https://github.com/actions/runner-images#available-images).
It does not deploy a release or access a Raspberry Pi or physical MicroDuck.

The workflow verifies the exact SmallVM and GP editor revisions against the
dependency manifests. The native builder additionally verifies source and JSON
dependency hashes. Both local editor profiles are built from all hash-checked GP
assets. The external VM test binary must match its sanitizer build manifest,
native ELF architecture, SHA-256 and successful self-test.

The runtime checks cover real SmallVM bytecode over its private Linux PTY,
persistence and process restart, the offset arena and moving GC, and native
MicroDuck jobs with private Unix-socket fixtures. Separate bridge tests use an
explicit PTY echo fixture. Gateway and browser tests use simulated robot/BLE
providers; their success does not establish physical robot support. The installer
tests simulate architecture and executables while performing real private
filesystem lifecycle checks. They do not install a service on the CI runner.
Candidate-release provenance and deterministic packaging tests use synthetic,
non-executed ELF fixtures; they do not create a published release.

Every selected Python suite must contain its named test classes, execute at least
one test, and finish without skipped tests. Missing WebSockets, GP assets or a
native VM therefore fails the job. The focused
[workflow test](../tests/test_linux_arm64_workflow.py) executes the actual embedded
guard against passing, skipped, empty, missing-class and failing test suites.
The selection is explicit; it does not invoke broad test discovery or the
separate numeric acceptance suite. Node executes the actual portal, adapter,
transport and MicroDuck client/panel modules using synthetic providers.
The explicit browser simulation tests also exercise the framed RPC client with
an in-memory simulated robot; they do not use Bluetooth or a real robot.

CI retains JSON test reports and build manifests as workflow artifacts, without
release binaries or user programs. A source review or local workflow contract
test is not evidence that a GitHub Actions run completed. Consult the actual run
and its architecture-specific reports for execution results.

The workflow's actual embedded selection was exercised locally on WSL Linux
x86_64 on 2026-10-27: [100 Python tests, no skips](../linux/arm64/tests/ci-local-python-suites.json),
[real sanitizer VM/PTY 50 repetitions and persistence](../linux/arm64/tests/ci-local-vm-protocol.json),
[82,307 memory checks](../linux/arm64/tests/ci-local-memory.json), and
[380 native MicroDuck fixture checks](../linux/microduck/tests/ci-local-native-fixtures.json).
Both pinned local editor profiles built. The final selected Node run passed all
91 tests after the portal simulation link was added. YAML and all twelve shell
blocks were checked locally. These results establish the local x86_64 test path;
they do not claim a hosted run or hosted ARM64 acceptance.

The protected-console checkpoint adds three explicit Node suites: core policy,
in-memory fixture and mock-DOM panel. The selected Node command now passes139
tests, including48 new console tests, with no physical Bluetooth or Edge access.

The later update-watch follow-up adds a dedicated protocol suite and controller,
fixture and mock-panel checks, bringing the selected Node command to 169 tests.
These include 30 new checks for the notification-only upstream protocol, ACK
races, bounded observation, authentication, exclusive ownership, redaction and
lifecycle cleanup. They do not perform a robot update or invoke Edge control.

The commissioning-preflight follow-up adds the explicit PreflightHost and
ReadOnlyPreflight classes to the checked Linux selections. All 22 focused tests
run without skips, and the full repository validator passes 203 tests. Filesystem
fixtures are real private Unix paths; compatible host observations are injected
where required. They do not claim a daemon API, peer identity or robot-ready.
The separate real Pi host-only observation is evidence outside hosted CI.
The required Linux repository validator after preflight passes203 tests with
zero skips. A hosted execution is still not claimed.

The receive-only camera follow-up adds tests/test_microduck_camera.cjs to the
explicit Node selection. It executes the actual signaling/session/BrowserPeer
modules with bounded internal in-memory and fake RTC/media providers, including
answer/ICE/early-track ordering, data-channel restrictions, metadata and cleanup.
It does not use an actual RTCPeerConnection, live WebSocket, camera, decoded
frames, local media capture or native Edge control. Hosted codec/browser/network
interoperability remains untested.
The local camera follow-up passes 207 selected Node tests (38 camera checks) and
203 required Linux repository tests with zero skips; the
[receipt](../evidence/2026-10-27/microduck-camera/README.md) distinguishes these
local results from still-unexecuted hosted runs.

The viewer follow-up adds tests/test_microduck_camera_viewer.cjs to the explicit
Node command. It exercises actual video-element observer and simulation panel
logic with internal fake DOM/media/callbacks, including absent/stalled frames,
blocked/pending play, rotation layout, cancellation and hidden-page cleanup.
These are not native browser decoder or graphical acceptance tests. The lab
page is packaged locally; no live signaling/media URL is enabled or deployed.
The local viewer selection passes 243 Node tests, including 36 focused viewer
checks. The [viewer receipt](../evidence/2026-10-27/microduck-camera-viewer/README.md)
also retains the initial sanitizer-build timeout capture and unchanged-validator
recovery, rather than treating source review or a hosted workflow as execution.
The local full run uses the existing SMALLVM_MICRODUCK_BINARY and
SMALLVM_NUMERIC_BINARY inputs after a fresh pinned sanitizer build/self-test and
provenance checks. Default repeated-build attempts exceeded the host's unchanged
120-second setup deadlines; both failures remain in the receipt. No test class,
assertion, source, compiler flag or deadline is edited to obtain that input mode.
All 203 required repository tests pass in 124.481 seconds with that verified
binary input and zero skips. This is a local WSL result, not hosted CI or native
camera decoding acceptance.

The motion follow-up adds explicit MotionProtocol, MotionModel, MotionUnixBackend
and MotionNativeAdapter classes to the checked Linux selection. Native tests use
the current sanitizer build, real VM bytecode/PTY and private Unix gateway, but
all motion frames remain internal simulation records. The separate packaging
test verifies the new library/status-only example in the actual pinned GP data.
These tests neither exercise physical motion nor graphical UBL compilation.

The sensor follow-up adds SensorProtocol, SensorSamples, SensorUnixBackend and
SensorNativeAdapter to the checked selection. Twenty-one focused tests include
four cases through actual native VM bytecode and PTY, plus bounded source-shaped
Unix stream fixtures and CLI cleanup. These establish simulated depth-zone,
raw-axis and button read paths, not physical sensor input or graphical execution.
Packaging uses independent outputs so a previous MicroDuck rebuild cannot be
mistaken for the default Pi profile. All existing assertions remain in place.

The coherent snapshot follow-up adds SnapshotProtocol, PadObservedState,
SnapshotUnixBackend and SnapshotNativeAdapter. The18 new cases cover immutable
depth rows, four-slot capacity/expiry, observed gamepad held-state, loss/order
handling and typed raw/Boolean/span readings. Five native cases include actual
moving GC while constructing nested depth-row records. Pi execution, when
recorded, still uses only simulated MicroDuck daemons and no numeric acceptance
suite, robot devices or service installation.
