# Raspberry Pi 5 and MicroDuck delivery status

Evidence date: 2026-10-27. This work is isolated from the active P4 checkout.
No ARM64 release or updated GitHub Pages deployment has been published.

| Requirement | Status | Evidence or remaining gate |
|---|---|---|
| Native SmallVM v417 on Pi 5 | Implemented and physically tested | AArch64 GCC builds, ASan/UBSan, real bytecode and PTY, [core evidence](../linux/arm64/tests/README.md). |
| IDE arithmetic, loop, reconnect, browser project restore | Implemented and physically tested | Actual graphical editor and Pi execution, screenshots in core evidence. |
| Local installer, reinstall, upgrade, uninstall | Implemented and physically tested | Private test prefix, actual binary, programs preserved; [adapter installer evidence](../linux/microduck/tests/pi5-adapter-installer.json). |
| Program autostart after VM process restart | Implemented and physically tested | Acknowledged durable code survived process termination; this is not OS reboot acceptance. |
| Optional user service | Implemented and simulated | Unit generation/lifecycle tests use a systemctl mock; actual user-service startup remains untested. |
| Full OS reboot and Windows SSH persistence | Implemented but untested | No reboot performed. The Windows agent is automatic and fresh-process SSH works; actual reboot is a separate check. |
| Release artifacts and corresponding source | Implemented, local candidate only | Deterministic archives, native evidence binding and hashes; [release contract](../linux/arm64/RELEASE.md). No public download URL verified. |
| Pi/MicroDuck board selection and install command generation | Implemented and simulated | Local portal and validation tests; copy remains disabled until reviewed artifacts are published. |
| HTTPS Pages to device network transport | Blocked | Trusted WSS endpoint/certificate and actual browser local-network behavior not commissioned. Pi loopback editor through existing SSH tunnel is physically tested. |
| Web Bluetooth discovery panel | Implemented and simulated | Mock chooser/version/cleanup tests; physical radio and browser/device compatibility untested. |
| API-44 BLE JSON-RPC client | Implemented and simulated | Mock framing, IDs, ACK writes, auth/permission/timeouts; [coverage](MICRODUCK_PROTOCOL.md). |
| Advanced browser JSON-RPC console and protected-command UI | Implemented and simulated | [Protected console](../linux/microduck/CONSOLE.md):27 reviewed raw methods, structured auth/provisioning, exact one-use confirmations, fresh skill discovery, redacted transient results and no replay. Real BLE secret/protected operations remain blocked by unverified confidentiality. |
| Real BLE PIN authentication/Wi-Fi provisioning | Blocked | Shipping BLE confidentiality cannot be attested. PIN is not encryption; no real secrets are sent. |
| Browser commissioning controls | Implemented and simulated | Standalone, explicitly fictional simulation; no physical transport or credential inputs. See browser commissioning guide when merged. |
| JSON-RPC local gateway | Implemented and simulated | Real Unix sockets and peer identities; robot daemon replies are mocks. |
| Native MicroDuck primitive adapter | Implemented on physical Pi with simulated robot | Real VM bytecode, moving GC, jobs, gateway, errors, timeouts and graphical health block. [Adapter evidence](../linux/microduck/tests/README.md). |
| Sensor, battery, sound and skills on actual MicroDuck | Implemented but untested | API envelopes and simulated replies implemented; no physical device available. |
| Continuous locomotion/camera/direct motor control | Not implemented | Outside the selected BLE/local gateway surface; preserve robotd controller and use supported future transport. |
| Typed battery/temperature/loop/bus/IMU readings | Implemented on physical Pi with simulated robot | Eighteen source-backed fields, explicit status/value/unit/origin records, fixed-point signed31 values and refusal of missing/invalid values. [Contract and use](../linux/microduck/TYPED_READINGS.md). |
| Reported health verdict and IMU convergence state | Implemented on physical Pi with simulated robot | Documented health/default/stale-run semantics; no global safe-to-move claim. |
| Universal robot-ready / motion authorization block | Not supplied by the reviewed API | No such signal is invented. Use reported diagnostics and supported robot authorization/safety interfaces. |
| Shipping MicroDuck OS/API/socket ownership | Blocked | Inventory and authoritative permission checks on arrival; never guess daemon UIDs or change permissions to force access. |

Milestone A is partially complete: native Pi execution is verified, while the
published installer/reboot gates remain. B awaits coordinated Pages/release
publication. C has a tested mock protocol core and an explicit real BLE security
gate. D has native Pi end-to-end tests against simulated daemons. E has a
commissioning checklist; it is not a physical compatibility claim.

The typed-readings checkpoint passes 181 required Linux tests, 18 feature tests
on each of ordinary and sanitizer native Pi binaries, and 442 native sanitizer
fixture checks. The updated graphical example loads and connects, but execution
of that example remains unverified: native Edge-window control timed out awaiting
app approval and was not retried. [Typed evidence](../linux/microduck/tests/typed-validation.json)
keeps this separate from bytecode/primitive acceptance. The later protected
console checkpoint passes48 new Node tests (139 selected tests total) and181
required Linux tests with zero skips. Its real modules are exercised through
mock DOM/GATT and in-memory RPC independently of unavailable Edge control.
Actual graphical console acceptance and real robot behavior remain untested.

Start with [Pi installation and tests](RASPBERRY_PI_5_INSTALLATION_TESTING.md),
[port design](LINUX_ARM64_SMALLVM_PORT.md), [Web Bluetooth](MICRODUCK_WEB_BLUETOOTH.md),
[JSON-RPC](MICRODUCK_JSON_RPC_INTEGRATION.md), [robot installation](MICRODUCK_INSTALLATION.md),
and [Christmas hardware checks](MICRODUCK_CHRISTMAS_HARDWARE_VALIDATION_CHECKLIST.md).
The [integration plan](LINUX_MICRODUCK_INTEGRATION_PLAN.md) records ordering,
shared-file conflicts and the publication gates.

| Brief section | Implementation/evidence map |
|---|---|
| 0-1: access and repository review | Verified strict-host SSH, Pi inventory, pinned upstream sources and existing capability/packaging contracts; no credential material in Git. |
| 2/5: portal and copied install | Seven profiles, validated release/target command generator, local packaging and Node/UI tests; published/copy acceptance is pending. |
| 3: native VM | Offset arena, strict transformations, PTY/persistence, bridge and real Pi/graphical evidence. |
| 4/8: installer/release/Pi | Real private-prefix lifecycle and self-tests; local deterministic source/binary candidate; service/reboot/publication gates remain. |
| 6: browser BLE | API-44 compatibility table and mock tests; discovery UI; real secret operations blocked; bounded fictional commissioning lab. |
| 7: robot integration | Checked Unix gateway, native jobs, UBL and real Pi execution against simulated daemon responses. |
| 9: Christmas preparation | Explicit Unix/browser simulators, six requested guides, status matrix and hardware checklist. |
| 10: browser security | Strict real BLE confidentiality gate, trusted WSS configuration only, tested SSH-loopback editor. |
| 11: tests/CI | Required validator plus dedicated native CI workflow; actual hosted runs pending. [CI scope](LINUX_CI.md). |
| 12-13: delivery/autonomy | Isolated local commits, auditable evidence/candidates, independent parallel work; shared publication held for P4 coordination. |
