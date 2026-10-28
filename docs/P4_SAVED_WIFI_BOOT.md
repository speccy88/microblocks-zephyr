# Saved Wi-Fi after P4 restart

## Cause and bounded change

The prior installed SD image enables `P4_WIFI_COMPAT_DIAGNOSTIC`. Its boot worker
consumes its initial semaphore to run the existing synthetic RAM-only C6
configuration check, then always continues to wait. The saved-credential path
therefore runs only after USB control operation 2. This is an intentional
diagnostic gate, rather than a missing credential or DHCP persistence feature.

The opt-in `profiles/saved-boot.conf` profile enables `P4_WIFI_SAVED_BOOT`.
After the same successful response-540/status-0 check, that worker proceeds
directly to load the existing settings, check the exact editor assets and
perform one association/DHCP attempt. No host command, new credential entry,
AP fallback, C6 firmware change or retry loop is added. The default diagnostic
profile retains its manual gate. Failure leaves native USB diagnostics usable.
Additional work wakes cannot repeat the automatic boot attempt.

Acceptance requires host tests of the actual worker for enabled/disabled boot,
bad/missing settings, compatibility/asset/driver/association/DHCP/service errors,
and extra wakes. No credential write or SD operation may occur. Build and
memory/partition/model guards must pass against the pinned native toolchain.

Physical acceptance requires verified installation with the present application
and assets kept recoverable, then at least two P4 restarts with no operation-2
connection command. Record automatic connection timing, HTTP asset hash,
WebSocket arithmetic and read-only SD availability. Do not change SD contents,
provision credentials, access COM12, flash C6 or change router/host networking.
A USB/ROM reset is a warm restart; full power removal is separate evidence.

One attempt per boot is the intended bound. A missing/rejected network, failed
DHCP or a later network loss does not start endless retries. Power-loss behavior
of FAT32 and full graphical peripheral acceptance remain separate objectives.

## Shared-main coordination

Work remains isolated in this task's source snapshot. The active Pi task uses
`microblocks-zephyr-integration-20261027` in its own workspace. Shared main,
the original P4 checkout and Pi/MicroDuck branches are not modified here.
The integration handoff will list exact P4 files and evidence. Any later shared
merge must use the then-current Pi/main state and rerun its broader validation;
do not replace shared portal files or apply the whole snapshot over that tree.

Read-only coordination checkpoint: the Pi integration checkout is clean at
`79ed6cbd5f1e99b4caec901a3f8c686c85bea62a` on
`codex/pi5-watch-integration-20261027`; its shared `main` ref is
`af742e8d34b194603182a303e07c130859f0cf8c`. These refs were inspected only.
The P4 boot change is limited to its network backend, Kconfig, opt-in profile,
focused tests and documentation; it does not change the shared editor or
MicroDuck implementation. No shared-main integration is performed in this task.

## Installed build and physical acceptance, 2026-10-27

Installed application SHA256:
`cc533266f45f1b76be5606ef6608a74611f7f87a919e7630775c6ccd87849ec3`
(15,374,656 bytes at 0x2000). Editor assets remain unchanged:
`30ef126cdbc1ff67ccc5b34e59089afea0680490f4d1d4f1541a758383d0cfe1`
(3,570,557 bytes at 0xfe0000). Full application/assets digests were checked
before installation and after the application-only write. Both subsequent
warm resets also reverified the installed pair through ROM digests. No SD write,
credential-provisioning, C6, COM12 or host/router configuration action occurred.

The build uses pinned Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`,
SDK 1.0.1 and the station/neural/whistle/compat-diagnostic/sd-files/saved-boot
configuration list. Source provenance is the preserved P4 working snapshot
based on `9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226`, including unpublished
SD/C6 prerequisites. The exact argument vector, complete build log, guarded
image and installation receipt are retained outside Git in this task's
`wifi-boot-evidence/`. Internal static usage is 382,608 bytes; libc retains
10,608 bytes above its unchanged 8,192-byte guard, and system heap is 32,768
bytes. Native stacks and the SD/C6 DMA objects remain internal.

Three warm boots passed: installation reset plus two later ROM resets. No
manual saved-connect operation 2 was sent. Each boot reported compatibility
passed, saved credentials present, assets valid, station connected and AP off.
Each also passed a simultaneous HTTP200 editor-data hash check and read-only
MBFILES listing (zero entries, error0), ten wireless arithmetic runs returning
12, and a wireless edit returning13. Observed-ready times were about44,143 and
95 seconds after reset; these include delayed host attachment/recovery and
are upper bounds, not measured association latency. HTTP transfers took
19.47,19.73 and20.99 seconds. Minimum observed unused station/HTTP/system-work
stack space was7,476/5,524/1,804 bytes.

The immediate serial reader encountered ROM text on the first extra reset,
then a version-handshake timeout on the second. Both incomplete receipts are
retained. Neither completed reset was repeated: separate read-only resume
receipts verified those same running boots. The timeout does not establish
an exact firmware boot duration. Final serial and test WebSocket sessions
were closed before reopening the real editor. No SD write was needed in this
follow-up; the earlier exact SD create/read/remove acceptance remains evidence
for the unchanged SD backend.

Host tests compile the actual `network_backend.c` worker with synthetic
Zephyr/settings/radio:133 checks pass under ASan/UBSan in enabled/default
modes, with zero credential writes and maximum status length440 bytes.
Run `python3 tools/test_p4_saved_boot.py` under a POSIX host C toolchain and
`python tools/validate.py` for the67 root checks. See
[curated physical evidence](../evidence/2026-10-27/p4-saved-wifi-boot-summary.json).

Compiled rollback application
`bbaba6feb0ea872b957e67b12988fe5e9e4d60e81ffaed5c047bab28a097cfdc`
and the same assets are retained as `baseline-application.bin` and
`baseline-assets.bin` outside Git; no device backup was read. A later recovery
must verify the then-current installed digests and use the COM5-only guarded
application replacement path. Do not overwrite settings/assets or use a bulk
erase. USB diagnostics remain available after an automatic attempt fails.

Full removal/restoration of power has not been physically tested. One attempt
per boot is deliberate; periodic retry and later link-loss recovery are not
implemented. A browser VM session must be reopened after a board restart.
No new camera/microphone, large SD-file or browser-download acceptance is
implied. The installation and integration patch remain local and unpublished.

Later bounded loss-recovery follow-up: current installed normal application is
`a4e49b75d390a4c24ca011662b5c80972d6b1c3447f69d5d33cecae1df1cad56`, with the same editor assets. The optional
`profiles/wifi-loss-retry.conf` preserves the boot gate and adds a three-attempt
boot-wide budget after an established link is lost. See
[physical results and retained TCP limits](P4_WIFI_LOSS_RETRY.md); the earlier
cc533266 evidence above remains the saved-boot milestone and compiled rollback.
