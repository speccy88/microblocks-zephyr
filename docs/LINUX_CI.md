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
The required Linux repository validator passes181 tests with zero skips. The
workflow includes those suites; a hosted execution is still not claimed.
