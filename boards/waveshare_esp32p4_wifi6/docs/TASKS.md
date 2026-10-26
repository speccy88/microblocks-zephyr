# Native work ledger

New requests and usability/hardware-audit acceptance are ordered in BACKLOG.md.
Ideas do not interrupt the current task or create concurrent serial owners.

- [x] Portable bounded I2C discovery/identity/measurement registry, native
  Zephyr worker and clear GP blocks/example. Bus 0 physical IMX219/ES8311 ID
  and camera register reads; unknown 0x64 kept address-only. ASan/UBSan fixture,
  stale-reference/reuse/error/Stop All and actual GP execution pass.
- [ ] Attached TMP117 physical temperature test (conversion/error fixtures pass).
- [x] Version 1 exact-board hardware support audit, source/physical evidence
  and attachment/conflict limits in HARDWARE_SUPPORT.md.
- [ ] Cross-library UI polish acceptance (I2C labels/zoom verified separately).

- [x] Confirm exact Zephyr board target in pinned a915b2f tree.
- [x] Confirm IMX219 and ESP-Hosted-MCU SDIO drivers exist.
- [x] Identify upstream P4 CSI/ISP video integration gap.
- [x] Preserve tested IDF proof on separate local reference branch.
- [x] Reuse portable handle/image layer and camera library.
- [x] Native Zephyr SmallVM/UART/PSRAM build and physical tests.
- [x] Native sensor video control and P4 CSI/ISP endpoint.
- [x] Native real-frame capture/resize/grayscale/RGB888/export, three runs.
- [x] Graphical MicroBlocks browser camera-pipeline execution.
- [ ] Companion handshake, approved network configuration, board hosting.
- [x] Companion transport and basic read-only control response: valid boot
  event and MAC-query status, 12 ms; no C6 flash, address logging or RF config.
- [ ] ArduinoCore-Zephyr variant compatibility verification.
- [x] Accurate source/evidence publication: native camera 0fb2aa74 on main;
  all three GitHub workflows passed.
- [x] Truthful image/DSP backend query.
- [x] Native PPA generated-pixel rotation/mirror/smooth resize, bounded
  lifecycle/errors and actual GP previews; timings/limits in DSP.md.
- [ ] PPA blend/fill blocks and measured reference-CPU performance comparison.
- [x] ES8311/I2S bounded PCM transport, DMA rate and lifecycle tests.
- [x] Controlled Windows speaker/P4 microphone acoustic-response test;
  correlation 0.7442, RMS rise 0.57 to 103.49, stopped and private PCM excluded.
- [x] Reuse prior Whistle C99 engine with native allocator/storage/worker.
- [x] Cross-build pinned C99 Whistle engine with 12 MiB bounded job arena,
  flash-mapped verified model and explicit native simple-boot partition map.
- [x] Native P4 fixture transcription, cancellation/reuse and memory metrics.
- [x] Native microphone handle to actual STT text and graphical example;
  experimental accuracy, scalar latency measured, no generic model runtime.
- [x] Actual GP per-block expandable image snapshots and explicit audio
  playback; native generated pipeline and bounded microphone widget tested.
  See INLINE_RESULTS.md and p4-media-browser.json. Board hosting is separate.
- [ ] Separate lightweight wake-word listener and MicroBlocks event contract.
- [ ] Measure compatible NN/DSP kernel optimizations against reference paths.
- [x] Native bounded NN model/tensor lifecycle, builtin INT8 catalog, custom
  static float32/int8 dense import, restricted ONNX conversion, physical golden
  and rejection/cancellation/reuse tests, and actual GP builtin execution.
- [x] Browser custom file-import submit and actual GP custom-model output, plus
  combined station-image USB NN/media/Whistle regression. Direct ONNX Runtime,
  arbitrary CNN import and P4 NN acceleration remain unavailable; the dedicated
  pinned KWS model is tested separately.
- [x] Native Zephyr TFLM INT8 fixture cross-build and physical inference on P4;
  ten bounded outputs, no sensor sampling/actuation; catalog/blocks subsequently
  completed and tested as recorded above.
- [x] Both native hosted and USB-only profiles cross-build with mapped Whistle;
  full app/model/assets/NVS overlap checks and bounded COM5 asset flashing.
- [x] Native C6 initialization and safe USB credential provisioning using the
  approved AP settings; secret is private and excluded from source/evidence.
- [x] Retire AP after Fred's explicit cancellation; keep historical failure evidence.
- [x] Station-only profile with DHCP, same-origin service checks and existing
  encrypted handoff/persistence approval; cross-build and whole flash map PASS.
- [x] Station credentials saved and readback-verified using the single encrypted
  handoff; no second prompt and no secret in source/evidence.
- [ ] Actual station association, reboot reconnection and board-served
  GP/WebSocket acceptance. No AP fallback or new credential prompt.

Native VM evidence: `evidence/2026-10-25/p4-zephyr-vm.json`. This establishes
actual UART programming, full-frame-sized PSRAM allocation, blank-image
preprocessing and safe handles. It does not establish sensor capture.

Receiver implementation: native video endpoint and sensor source,
dedicated Zephyr worker, bounded DMA completion polling, cache synchronization,
sensor stop and DMA abort/reset before release. HAL comes from the pinned
Zephyr Espressif module; ESP-IDF RTOS drivers are not linked. Three actual
IMX219 captures passed with live VM execution, transform/export and release,
recorded in `evidence/2026-10-25/p4-zephyr-camera.json`. Image quality is untuned.

## Wake-word increment

- [x] Pinned Apache-2.0 Okay Nabu model and separate trained frontend/resolver.
- [x] Bounded native worker/arena/ring, explicit listening and stop/cancel.
- [x] Host/P4 exact feature and score parity, positive/negative fixture events.
- [x] ASan/UBSan frontend reset/chunking and all allocation-failure cleanup.
- [x] Physical bounded microphone timing, cancellation, reuse and owned clip copy.
- [x] Real GP event hats (two handlers), unrelated-phrase rejection and screenshot.
- [x] USB and station cross-builds; complete flash/model/assets/settings bounds.
- [x] Final USB hash flash; PPA, I2C, dense NN and Whistle fixture regressions.
- [ ] Acoustic wake detection: Windows output muted at 0%; settings unchanged.
- [ ] Deliberately injected stream overflow/DMA-stop faults and long-run false triggers.
- [ ] New publication: explicitly on hold pending Fred's current confirmation.

Evidence is in `p4-kws-*.json`; model/audio binaries remain ignored locally.
Station association/hosting and acoustic recognition are independent open gates.

# Local portable JSON increment (publication/installation held)

- [x] Separate strict portable service, 96 KiB bounded workspace, exact numbers,
  immutable CRUD, RFC6901 pointers, UTF-8/duplicate-key/size/depth/value checks.
- [x] Append json primitive set at 22; preserve all existing p4:* indices.
- [x] Separate JSON library, clear errors, example and unclipped actual GP render.
- [x] 62 sanitizer cases, 10,000 malformed inputs, memory-exhaustion checks;
  47 canonical repository tests; native USB/station compilation and layout.
- [ ] Physical JSON blocks, latency, responsiveness and VM GC stress after
  firmware installation is permitted. No physical JSON claim yet.
- [ ] Commit/push/Pages deployment after the separate publication hold resolves.

## Local clock/timer and step/transition increment

- [x] Separate portable fixed-storage cores and `clock:*` / `steps:*` libraries;
  append primitive sets 23/24, preserving existing IDs.
- [x] Fake monotonic/calendar tests with ASan/UBSan: clock validity, jumps,
  offset gaps/repeats, missed events, stale references and cleanup.
- [x] Deterministic logical scans: initial steps, conflicts, fork/join,
  no same-scan cascade, timed guards, self-loops and stop/reset.
- [x] USB/station compilation and complete app/model/assets/settings layout.
- [x] Actual disconnected GP palette/example rendering at 1280 x 720.
- [x] Carried-forward JSON sanitizer suite and 50 canonical repository tests.
- [ ] Physical timing, Stop All/restart, GC and concurrent VM responsiveness.
- [ ] Actual RTC/NTP providers and verified retention/synchronization.
- [ ] Installation and publication after the existing holds resolve.

## Local file-manager frontend increment

- [x] Shared real-editor dialog, disconnected state, literal text editor,
  capacity, conditional save and explicit opaque download request.
- [x] Bounded transport contract and separately opted-in browser-memory fixture;
  Flash/SD unavailable, production packages exclude fixture code.
- [x] 16 Node tests, 10,000 malformed paths, four packaging/security contracts;
  carried-forward JSON/automation/storage sanitizer tests.
- [x] Actual GP synthetic-file walkthrough and 1280 x 720 screenshot;
  Escape/dirty-edit protection, narrow 560 x 720 layout without horizontal clipping.
- [ ] Browser download completion: test interrupted; copied bytes/MIME/name
  verified in core tests only. Do not count the button click as a completed download.
- [x] Native file revision guards, controller-owned dispatcher and injected
  existing-frame adapter; synthetic JS Client-to-C harness validation.
- [x] Local USB/WebSocket session hooks and VM routing; generated-adapter tests
  with synthetic transport streams. Physical transfer remains unverified.
- [ ] Installation and publication after the existing holds resolve.

## Local storage dispatcher increment

- [x] Non-reused file revisions, conditional begin/commit and revision-bound reads.
- [x] Session ownership, replay rejection, inactivity/rollback expiry and cleanup
  that preserves completed files and unrelated VM writes.
- [x] Bounded binary codec and injected JS frame adapter; no automatic connection.
- [x] 23 sanitizer scenario groups, 10,000 malformed packets and all 24 combined
  JS tests, including real native C harness roundtrips and lost-commit handling.
- [x] USB/station cross-builds and complete hosted flash-layout validation.
- [x] 61 canonical repository regressions; unrelated FruitJam bytes preserved.
- [x] Trusted controller grant/close/expiry hooks and VM-thread routing locally;
  production sender/framing and controller lifecycle tested without a board.
- [ ] Approved installation, physical USB/WebSocket file tests and publication.

## Local RAM-storage increment

- [x] Separate portable fixed-capacity service: safe paths, binary/UTF-8,
  generation-checked staged writes, explicit replace, cancel and cleanup.
- [x] 49 named sanitizer checks and 10,000 malformed inputs; no hardware access.
- [x] Separate Storage library/set 25, save/replace/read/list/delete/status,
  capacity reporters and temporary text-file example.
- [x] Native USB/station builds, full flash layout and disconnected real GP UI.
- [ ] Physical write/read, Stop All/reconnect, timing and VM/GC stress.
- [ ] Flash/SD adapters, storage layout, media streaming, web file manager and DB.
- [ ] Installation and publication after the existing holds resolve.

## Authorized USB RAM physical acceptance, 2026-10-26

This follow-up supersedes the earlier installation/physical-storage holds above;
publication remains separately held. See `docs/STORAGE_PHYSICAL.md` at repo root.

- [x] Confirm COM5 CH343, ROM P4 revision 1.3 / 32 MiB and current USB profile.
- [x] Verify final build/artifact hashes and flash only the guarded USB image once;
  esptool hash verification succeeds. C6, COM12 and credentials untouched.
- [x] 918 actual framed requests: limits/revisions/replay/session cancellation,
  malformed recovery, repeated writes and shared storage primitives.
- [x] Genuine GP RAM example, file-manager create/edit/reopen/dirty protection,
  independent COM5 UTF-8/JSON byte readback; production package has no fixture.
- [x] Full 64 KiB store beside 8.29 MB images; PPA, NN and Whistle pressure/
  failure/recovery regressions. No camera capture, microphone or speaker use.
- [x] Reset clears RAM; protocol and fresh GP editor show zero bytes/eight slots.
  Stop All, listening/capture inactive, file session closed and COM5 released.
- [ ] Completed browser download, physical cable/power loss, general heap and
  all-thread/GC stress remain unverified; existing interrupted download not retried.
- [ ] Station HTTP/C6 decode-pool/runtime acceptance remains a separate blocker.
- [ ] Flash/SD, large media archive and database remain future stages.
- [ ] Commit/push/publication/deployment still require the pending authorization.

## Isolated Flash backend increment (local only)

- [x] Read existing app/model/assets/settings layout; no dedicated file partition.
- [x] Separate portable Flash record service and Zephyr VFS/LittleFS adapter;
  bounded quotas, persistent revisions, conditional writes and fail-closed recovery.
- [x] Keep production CMake/profiles, installed RAM image and Flash-unavailable
  capability unchanged. No live flash/credential/partition access.
- [x] Native simulator and ASan tests for mount/limits/errors/atomic outcomes;
  separate-process persisted-image check. See root `docs/FLASH_STORAGE_LOCAL.md`.
- [x] Measure standalone RV32 state and verify unchanged USB/station ELF/config/
  map/binary hashes; no additional production memory reservation.
- [ ] Review a new file partition and migration/initialization authorization.
- [ ] Budget PSRAM, worker stack and filesystem caches before VM routing.
- [ ] Physical NOR/cache/power-loss/wear acceptance and Flash blocks/UI integration.
