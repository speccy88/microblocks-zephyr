# OLED robot eyes and person tracking

## Preview speed and resolution contract (2026-10-29, before implementation)

Preserve the user's current tuple 1156/195/3831 while testing faster snapshots.
Add 160x90, 320x180, 640x360, 1280x720 and bounded custom dimensions. Sensor
capture remains the established 1280x720 mode; output resolution selects native
image resize only. Message 213 operation 3 accepts width/height in its first
two u16 argument fields, third zero; 0/0 retains legacy 320x180. Reject one
zero, width outside 16..1280 or height outside 16..720. Report requested size,
capture time, transfer time and complete-preview time. Keep a bounded lease
large enough for the selected image at baseline baud (maximum five minutes),
and release only the client's image. Existing setting/reset messages and
320x180 default block semantics remain compatible; add a sized snapshot block.

For the USB-only profile, retain 115200 at boot and for ordinary/direct browser
clients. Negotiate 460800/921600 only when an explicit host companion supports
it. New message 214: 16-byte `P4BR`, version 1, operation, reserved u16 zero,
token u32 and baud u32. Reply uses the same layout with status/state bytes
in place of reserved bytes. Operations: 0 capabilities, 1 prepare, 2 confirm,
3 restore baseline, 4 lease heartbeat (no response). Prepare is acknowledged
at the current rate; wait >=40ms and UART TX completion before changing via
Zephyr uart_configure. Confirm at the new rate within 1.8 seconds, then keep
the rate lease alive only with valid token/rate heartbeat frames. Loss of
lease or normal close restores 115200. Stop All does not change rate. The
network-hosted firmware explicitly rejects negotiation. No baud setting is
written to flash and no C6, network or GPIO pin mapping changes occur.

The local bridge defaults to requested 921600 after successful negotiation,
with explicit --baud 115200 fallback. Old firmware stays usable at 115200.
Inject heartbeats only between complete VM frames. Acceptance: protocol/range/
transition/replay/lease fixtures, native compile, physical byte-identical
image export at each baud, CRC/fragmented upload and reconnect/lease recovery,
measured preview timings at two sizes, and real graphical selector/snapshot.
Do not promise eightfold application speed from the baud multiplier alone.

## Current delivered status

The speed/resolution update keeps the native sensor mode and adds selectable
preview output: 160x90, 320x180, 640x360, 1280x720 or custom width 16..1280
and height 16..720. **Take snapshot width _ height _** exposes the same output
choice in blocks; the original snapshot block keeps its 320x180 default.
The panel reports actual capture, preview-transfer and complete-preview time.
It exports the resolution, baud and timing with the capture settings.

The local bridge now requests a negotiated 921600-baud link. Hardware tests
measured 320x180 RGB565 transfer at 11.529s / 115200, 3.239s / 460800 and
2.319s / 921600. The captured bytes matched exactly between rates. A 160x90
capture plus transfer took 0.755s at 921600. Larger sizes were physically
captured and dimensions checked; full export timings for those sizes are not
claimed. Three orderly reconnects, fallback after a deliberately crashed
controller, legacy-firmware fallback, and fragmented CRC/execution at all
three rates passed. No raw images are stored in this evidence. See
`preview-speed-native.json`, `preview-old-firmware-compat.json`,
`preview-speed-host.json`, `preview-speed-flash.json`, and
`p4-preview-speed-build.txt` under the dated evidence directory.

Actual graphical end-to-end timings include additional browser overhead:
320x180 4.08s, custom 192x108 1.65s, and 160x90 1.22s. The resolution
dropdown, custom numeric fields, restored tuple, real image dimensions and
timing/status labels passed in GP. See `preview-speed-graphical.json`.

Boot/direct-browser UART remains 115200. The bridge negotiates fast mode only
after recognizing the board; explicit `--baud 115200` disables negotiation.
Confirm deadline is 1.8s; the active link lease is 5s, renewed with valid token
heartbeats between full VM frames. Orderly close restores baseline. An old
115200 client can reconnect after the lease expires if its predecessor crashed.
The hosted network firmware rejects baud negotiation. Image leases are sized
for the chosen payload at baseline speed, capped at five minutes, and normal
UI completion releases the thumbnail immediately.

Fred's current preferred tuning tuple is **1156 / 195 / 3831**. It is restored
in RAM after the speed tests. It has not been written as a new firmware default.

The installed native Zephyr image includes RoboEyes, shared camera RPC, face
engagement and runtime snapshot tuning. Test pattern is OFF. Original manual
defaults remain 800/128/256. The user confirmed visible OLED alignment at
0x3c with the SSD1306 profile; controller silicon is still unidentified.
103 repository tests and portable ASan/UBSan tests pass. The real USB demo
traversed looking around, sleepy, sleeping, happy/following, waiting, then
looking around with explicitly simulated face input. This is not evidence
of real face detection or motion accuracy.

Use `http://127.0.0.1:8874/?bridge=1`, choose **Camera snapshot sliders
(Pi Camera v2.1)** under Projects & board, connect and press Start. The
Camera image panel opens with three sliders and numeric inputs. Adjust and
choose Take snapshot. Apply settings updates the reporter block too; Read
current settings queries the P4; Reset restores 800/128/256. Each browser
snapshot shows its exact tuple and offers local PNG/settings downloads.
The browser releases its owned native thumbnail after transfer. The block
returns an ordinary image handle; release it when finished. Captures never
enter project code or Git. Baseline 115200-baud colour preview takes about
12 seconds; the new bridge fast mode reduces transfer to about 2.3 seconds.
Errors retain the previous preview.

The brighter measured starting tuple **1156 / 232 / 512** gives mean image
brightness 77.68/255 versus 14.72/255 at the original defaults, but remains
noisy. The user can tune it without reflashing. No preferred tuple is saved
to flash. The colour-bars diagnostic covered 0..255; the unsuccessful 150ms
startup-delay experiment was removed. These are transport/control and
brightness-response tests, separately from scene or recognition quality.

Restart the shared editor and local companion with:

```powershell
python tools/fetch_face_model.py
build-artifacts/pose-windows/Scripts/python.exe tools/serve_p4_ide.py --editor build-artifacts/p4-robot-eyes-editor --pose-source p4 --tracking-mode both
```

It waits until a P4 tracking-camera block is enabled. **Happy face tracking +
sleepy idle** enables it. Use `--tracking-mode face` to omit YOLO arm pose.
The 3,758,596-byte official MediaPipe float16 v1 bundle detected a public
portrait and rejected a blank frame. The tiny face in the full-portrait
192x108 thumbnail was not detected: sufficient face detail is required.
Uncertain eyelids report unknown. Live P4 face following, head/eye-direction
calibration and arm-motion accuracy remain unverified. Eye direction is a
rough expression estimate; the USB acquisition rate can miss brief blinks.

A camera/model-free demonstration with nobody present is reproducible with
the exclusive COM5 command below (close the editor connection first), or
restart the bridge with `--pose-source demo` and choose its SIMULATED example:

```powershell
build-artifacts/pose-windows/Scripts/python.exe tools/eyes_demo.py --execute --seconds 36
```

Numerical evidence under `evidence/2026-10-29`: `camera-tuning-native.json`,
`eyes-attention-simulated-usb.json`, `face-model-host.json`,
`robot-eyes-flash.json`, `robot-eyes-host.json`, `robot-eyes-validation.txt`.
Requested photos and panel screenshots stay in ignored build-artifacts.

The following sections preserve the staged implementation contracts and
earlier test observations. This current status supersedes historical pending
statements; it does not change the unverified live-tracking limits above.

## Runtime snapshot tuning contract (user-requested, before implementation)

Install firmware support once, then tune the Pi Camera v2.1 / IMX219 without
further flash writes. Three manual controls: exposure 4..1156 lines, analogue
gain register 0..232 (1x..10.67x), digital gain 256..4095 (1x..15.996x).
The original defaults are 800/128/256. Validate the entire tuple atomically;
reject unsupported sensors or a busy capture. Stage in RAM, snapshot a copy
at sensor configuration, apply over Zephyr I2C before stream-on. Stop All
cancels captures but keeps the tuple; reset/reboot restores original defaults.
No AE, AWB or optical focus control is implied.

Add a take-snapshot reporter, parameter/reset/status blocks and a Camera
image panel with labelled range sliders, numeric values, Take snapshot and
Reset buttons. Changes apply on Apply or Take snapshot. Show the tuple used
with each preview; retain the previous browser image on error. Export PNG
and settings only on explicit user actions. New message 213: 24-byte request
`P4CC`, v1, op, reserved u16, request u32, session u32, exposure/analogue/
digital u16, reserved u16; 16-byte reply header with status/state/request/
session followed by bounded JSON. Ops 0 get, 1 set, 2 reset, 3 snapshot,
4 status, 5 release. A snapshot owns a separate camera owner and at most one
320x180 RGB565 image; original full frame is released. Session and 20-second
thumbnail lease prevent another client releasing/retaining its image.
Block snapshots use the existing VM camera owner and return a normal image
handle. Neither path overwrites block scripts. Disabled/busy/error/Stop All/
disconnect must release only owned resources. Acceptance: strict bounds and
ownership tests, native build, real USB parameter readback/reset, real snapshot
at two tuples, and graphical sliders/capture/preview. Real scene quality is
judged by the user, separately from successful transport.

## Confirmed first-test setup (2026-10-29)

After the successful user-confirmed OLED alignment test, the next contract is
shared P4-camera use with the graphical blocks. A host companion must not
overwrite VM chunks or stop the user's block program merely to capture.
Add a bounded camera RPC on message 211, separate from editor image requests,
and explicit `pose camera on/off` blocks. It is off on boot and Stop All;
the companion waits while off. Camera requests have explicit ownership so
ordinary VM camera-result reads cannot consume a companion capture.
Only the companion's thumbnail is released; existing VM handles are preserved.
Capture/export has a deadline and disconnect/Stop All cancellation. The same
USB connection carries editor traffic, RPC and pose samples, with whole-frame
insertion and bounded buffers. The computer performs YOLO locally.

Message 211 requests are exactly 24 bytes: `P4CP`, version=1, operation byte,
reserved u16=0, request u32, session u32, packed offset u32, count u16,
reserved u16=0 (little endian). Operations: 0 capabilities, 1 capture,
2 metadata/status, 3 packed read, 4 release/cancel. Responses have a 16-byte
header (`P4CP`, version, operation, status, state, request, session) followed
by <=512 data bytes. A nonzero session owns a capture. Max 192x108 thumbnail,
10,368 packed bytes, 512-byte reads, and at most one capture/thumbnail exist.
Idle camera lease expires; an old client cannot release another session.
Acceptance includes disabled/no-capture behavior, ownership rejection, packet
bounds and cancellation, plus real GP eye execution and, once Fred confirms
lighting, bounded actual-camera capture/YOLO/gesture tests. Private frames
remain in memory or ignored local outputs; Git evidence is numerical only.

The first six actual P4 captures on this profile all exported near-black
images (decoded range 0..17) and YOLO found no people. Capture ownership,
ordinary-VM result isolation, wrong-session rejection and preservation of a
VM-owned image passed. Cleanup left zero images and an idle camera. Fred
confirmed lighting, so sensor first-frame startup, exposure and ISP handling
must be investigated rather than lowering the scene-quality threshold.
First experiment: let IMX219 stream for 150 ms before opening the CSI-to-memory
gate, retaining all existing formats, exposure/gain defaults and shutdown
guards. Treat this as an unproven startup hypothesis, measure actual frames,
and retain it only if image validity/quality improves. No inference success
is claimed from camera transport alone.

Fred selected the camera attached to the P4 and a 128x64 OLED whose label may
say 0x78; the controller is not yet known (SSD1306 or SH1106). The primary
companion mode will therefore default to `--source p4`, keeping YOLO on the
computer. Normalize only the documented 8-bit write-address aliases 0x78/0x7a
to the 7-bit bus addresses 0x3c/0x3d. Do not probe reserved 7-bit address 0x78.

Before implementing this follow-up: add an explicitly triggered, asynchronous
address-only probe of 0x3c and 0x3d, with no initialization or identity claim.
Zero/multiple responses must be reported clearly. Add an explicit alignment
pattern for comparing the two selected controller profiles; neither an ACK nor
a pattern proves chip identity. The disconnected board prevents actual
identification. Preserve both selectable profiles and the existing shared bus.

For bounded P4-camera export, extend existing message 206 with read operation
3: grayscale packed at four bits per pixel, high nibble first, logical packed
offset, max 512 bytes per response. It is a lossy diagnostic input, not a
replacement for existing image formats/reads. The initial 160x90 candidate was
rejected after it detected no people in the public fixture. The selected
192x108 frame is 10,368 bytes instead of 41,472; no baud-rate or boot/transport changes. Host decoding
must validate byte counts and use camera-frame age in freshness checks.
The P4-source tracker must tolerate the slower acquisition interval so
debounce and identity hold can span successive samples. Wave detection still
depends on actual sample rate; do not claim live performance without hardware.

Acceptance: native build, existing regression suite, fake-probe cases for
absent/single/ambiguous addresses and alias conversion, alignment-buffer
bounds, packed-image bounds/odd pixels/quantization tests, mocked P4 capture
and cleanup, and actual YOLO on the quantized public fixture. Physical
identification, camera quality, eye appearance and tracking remain untested.

## Contract written before implementation

The first target is the native Zephyr Waveshare ESP32-P4-WIFI6 port, using
the existing I2C0 on SDA GPIO7 and SCL GPIO8 at 100 kHz. These wires are shared
with the camera and ES8311: do not remap pins or reset/configure their devices.
Initial display assumption: SSD1306, 128x64, address 0x3c (7-bit). A 128x32
SSD1306 and 128x64 SH1106 are selectable explicitly; probing an address cannot
identify the controller. Use a 3.3 V compatible module/pull-ups and common GND.

MicroBlocks exposes initialization, status, mood, cardinal and continuous gaze,
blink/wink/open/close, idle/autoblink, curiosity, cyclops, sweat, flicker,
laugh/confused animations and geometry. Animation and I2C transfers run outside
the VM thread, with bounded storage and frame rate. Startup never touches the
OLED until explicitly initialized. Stop All stops animation and pose following.
Bus jobs must defer to camera/audio initialization and I2C discovery.

Use the actual pinned FluxGarage RoboEyes library through a small native
framebuffer/GFX compatibility surface, without claiming ArduinoCore support.
Keep its GPL-3.0-or-later source/license external and hash-verified; adapters
retain individual notices. Redistribution of a combined RoboEyes firmware must
retain the applicable upstream terms and corresponding build sources.

YOLO pose inference initially runs on a local computer with Ultralytics and a
webcam or video file; a P4-camera source can use the existing bounded image
export. It sends only a compact current pose sample over the existing VM
transport. This is not onboard YOLO: the P4 dense-only TFLM backend cannot run
the model. The pose library reports visibility, gaze and arm gestures and can
automatically follow/react. Webcam/camera capture requires explicitly running
the companion command; loading the IDE never starts it. Frames/model binaries
and private capture/log artifacts stay outside Git. USB has one controller;
the editor bridge must share the same serial connection for simultaneous use.

Tracking uses confident COCO nose/shoulders/wrists, a stable person selection,
normalized coordinates, smoothing, gesture debounce and a freshness timeout.
Lost/invalid/stale people stop arm reactions and return gaze to the center.
Left/right gestures use the person's anatomical labels; horizontal mirroring
is configurable. Hands above shoulders, both raised, arms extended, and wave
motion are distinct. Missing wrists must never count as raised hands.

Non-goals: flashing disconnected hardware, changing C6/Wi-Fi, training models,
face identity, full Arduino compatibility, onboard YOLO performance claims,
or claiming physical display/camera/gesture acceptance from fixtures.

Dependencies: pinned native Zephyr/SmallVM toolchain, external RoboEyes header,
optional local Python Ultralytics/OpenCV/pyserial/websockets environment and
downloaded pose weights. Existing camera scene-quality limitations still apply.

## Testable acceptance

| Check | Required evidence | Current status (2026-10-29) |
|---|---|---|
| Native firmware | Exact command, target/source revisions, compiler/link log | USB profile compiled and linked; see build evidence |
| OLED packets | Fake-bus init, page/chunk bounds, addressing, failure recovery | host ASan/UBSan pass, 3 controller/size combinations |
| Animation | Real RoboEyes framebuffer/moods/gaze/actions | 36 mood/gaze cases and close-during-tracking pass; physical GP animation/Stop All and simulated native engagement pass |
| Pose decisions | Confidence, missing joints, person selection, gestures, stale/lost, mirror fixtures | Python fixtures and native wire/freshness tests pass |
| Transport | Strict bounded wire and one-controller bridge | packet/mux tests and real shared-camera ownership/capture pass |
| Real YOLO | Actual model inference on public/local test image, no board claim | Windows and WSL: 12 repeated public frames, 11 usable person samples, first warm-up discarded |
| IDE | Real GP 2.5.8 libraries/examples | physical eye example, camera-controls block and snapshot sliders/preview executed |
| Regression | `python3 tools/validate.py` | 103 tests pass |
| Physical OLED | Connected module and visible alignment | 0x3c ACK; SSD1306 profile complete border/center cross confirmed by Fred; silicon identity unknown |
| Physical tracking | Live camera/person and display observations | real transport and synthetic engagement tested; real face/arm motion unverified |

Builds and host fixtures never change a physical row to PASS.

## Blocks and default reactions

**Robot Eyes** contains stackable commands and dropdowns for the four RoboEyes
moods, nine gaze directions, continuous gaze, blink, left/right wink, open,
close, laugh, confused, automatic blinking/idle, curiosity, cyclops, sweat,
geometry and horizontal/vertical flicker. `eyes ready?` and `eyes status` report
initialization and I2C errors. The start command takes the controller, height
and decimal 7-bit address: 60 is 0x3c, 61 is 0x3d. Width is fixed at 128.
SH1106 requires height 64. For 128x32 custom geometry, use height <=28.

**Person Pose** provides `person visible?`, person X/Y/confidence in 0..1000,
an arm-gesture reporter and a gesture dropdown predicate. Start the OLED, then
enable `eyes follow person true react to arms true`. With reactions disabled,
use the gesture predicate in your own MicroBlocks program. Mirroring affects
horizontal gaze only; left/right gesture labels remain anatomical.

| Gesture | Automatic reaction |
|---|---|
| Neutral / arms down | Default eyes following nose or shoulder center |
| Left hand above shoulder | Curious eyes, left wink on entry |
| Right hand above shoulder | Curious eyes, right wink on entry |
| Both hands above shoulders | Happy eyes |
| Both arms extended sideways | Angry eyes |
| Raised hand moves side to side with two reversals | Happy eyes, laugh on entry |
| Person absent or packet older than 1 second | Center gaze, default mood, clear pending arm reaction |

Gesture changes require 250 ms stability. Wave detection uses a bounded
1.3-second history and meaningful horizontal travel. Person selection first
chooses the largest box, then the closest box within 0.30 normalized image
distance, holding identity through a brief occlusion; this is spatial matching,
not identity recognition. Gaze uses time-based smoothing (120 ms). These
heuristics passed fixtures; live accuracy/false-positive rates are unmeasured.

Stop All stops the animation worker's output and disables following. The last
displayed frame stays visible. Start eyes again to resume. A new run must
enable following explicitly. An I2C failure latches a status and stops the
worker; fix wiring/settings and initialize again. Animation commands have an
eight-entry queue; automatic pose reactions keep only the latest pending
reaction and expire. Camera/audio/discovery jobs defer display pages. The
Zephyr I2C driver serializes individual transactions; no bus speed is changed.

## Test on this Windows computer

The prepared Python environment is `build-artifacts/pose-windows`. The local
editor is `build-artifacts/p4-robot-eyes-editor`, and the downloaded model is
`build-artifacts/pose/yolo11n-pose.pt`. The firmware build is USB-only and
includes the ordinary camera/audio APIs plus eyes/pose. Optional Whistle,
TFLM dense and KWS model profiles are not included in this small artifact;
their source/profile integration is retained. Fred subsequently connected the
board and explicitly authorized replacing its firmware. The guarded P4 image
was installed at 0x2000 and hash verified. C6/assets/settings were not written.

The first physical OLED check failed: neither 0x3c nor 0x3d
ACKed; both probes timed out with -116. GPIO reads report SDA7=1, SCL8=0.
An address-only scan also timed out without finding the onboard devices.
On Fred's subsequent "try again now", 0x3c ACKed, 0x3d NACKed, and the
SSD1306-profile alignment pattern completed successfully. IMX219 ID0219 and
ES8311 ID8311 also read correctly; five VM arithmetic reporters returned 12
during the display test. The pattern is retained on screen while the worker
is stopped. Fred then confirmed a complete border, centered cross and working
display. Controller silicon identity remains unknown. GPIO snapshots during active
OLED refresh can legitimately read low; compare idle values after stopping.
See `robot-eyes-flash.json`, `robot-eyes-probe.json` and
`robot-eyes-address-scan.json`, `robot-eyes-probe-retry.json` and
`robot-eyes-alignment-native.json` in the dated evidence directory.

First, with the editor/bridge closed, use the prepared OLED diagnostic:

```powershell
build-artifacts/pose-windows/Scripts/python.exe tools/pose_eyes.py --serial --identify-oled
build-artifacts/pose-windows/Scripts/python.exe tools/pose_eyes.py --serial --alignment-test --controller ssd1306
```

The address-only diagnostic does not initialize the OLED or capture camera
images. Both commands use VM test chunk 10. The alignment command initializes
the selected controller profile and shows all four borders, a center cross
and distinct edge marks. An ACK or an aligned image does not prove a chip ID.
Use Ctrl+C to stop it. If needed, repeat with `--controller sh1106`; physical
appearance is needed to choose the working profile. Entering `--address 0x78`
is accepted as the write-address alias for 0x3c, never sent as 7-bit 0x78.
With two responding candidate addresses, select one explicitly. The IDE also
has **Find OLED address (controller unconfirmed)** and an **eyes alignment
test** block; the address helper stops eye animation before probing.

The primary person-tracking command now uses the P4-attached camera:

```powershell
build-artifacts/pose-windows/Scripts/python.exe tools/pose_eyes.py --serial --source p4 --preview --controller ssd1306
```

The source defaults to `p4`. Close the graphical editor/bridge before using
this exclusive controller. It stops running VM scripts, uses chunk 10,
checks the OLED address, initializes the selected profile, then captures
through the native P4 camera and exports 192x108 packed grayscale in chunks
of at most 512 bytes for host YOLO. It releases images and stops eyes on exit.
The 10,368-byte payload alone takes at least 0.9 seconds at 115200 baud,
before capture/protocol overhead. Input older than two seconds is discarded;
the receiver still expires the most recently delivered pose after one second.
Acquisition gaps above one second can therefore cause gaze to center between
samples. No live frame rate/latency or fast-wave recognition is claimed.
The tracker allows three-second acquisition gaps and a four-second wave
window for this slower source. The P4 camera still needs its lit-scene retest.

From the repository root, after compatible firmware is installed and the OLED
is wired, an optional shared editor + computer-webcam alternative is:

```powershell
build-artifacts/pose-windows/Scripts/python.exe tools/serve_p4_ide.py --editor build-artifacts/p4-robot-eyes-editor --pose-source 0 --pose-model build-artifacts/pose/yolo11n-pose.pt
```

Open `http://127.0.0.1:8874/?bridge=1`, choose the **Person tracking eyes**
example under **Projects & board**, connect and press Start. Camera 0 starts
only after the editor connection, because `--pose-source` was supplied. Only
COM5 CH343 with the expected P4 board identity is accepted. The editor and
companion share one controller; pose samples are inserted only between full
VM frames, including when an upload is fragmented. No script chunks are
injected by the webcam companion. Ctrl+C closes the bridge and camera; the
board clears pose on disconnect or freshness expiry. Add `--pose-mirror` if
horizontal motion is reversed. Test the **OLED robot eyes** example first
without `--pose-source` to isolate display wiring from vision.

For a camera preview without any board access:

```powershell
build-artifacts/pose-windows/Scripts/python.exe tools/pose_eyes.py --source 0 --dry-run --preview --model build-artifacts/pose/yolo11n-pose.pt
```

Replace `0` with an existing local video/image for offline input. Q closes the
preview. Frames, recordings and model weights are never committed. The model
runs locally; optional Ultralytics sync is disabled in a separate task-local
settings directory. First-use model loading/inference may exceed one second;
those samples are discarded rather than renewing the board lease with old data.

`--serial --source 0` also supports webcam following without the editor.

## Reproduce dependencies and build

RoboEyes is the unmodified upstream 1.1.2 header (its banner says 1.1.1), pinned
at `b42f8e596535234932be3514ac7a813d4ced0046`. Its full GPL license is fetched
and verified with the source. The facade uses only a fixed 1,024-byte buffer,
the library's C++ template and native Zephyr I2C; it does not link ArduinoCore.

```powershell
python tools/fetch_roboeyes.py
python tools/fetch_p4_sources.py --output build-artifacts/p4-sources
python tools/package_p4_ide.py --ide-source build-artifacts/p4-sources/ide --output build-artifacts/p4-robot-eyes-editor
py -3.12 -m venv build-artifacts/pose-windows
build-artifacts/pose-windows/Scripts/python.exe -m pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
build-artifacts/pose-windows/Scripts/python.exe -m pip install -r dependencies/pose-requirements.txt
```

Use the existing pinned west workspace and apply the reviewed native patches
to its exact Zephyr revision first. The actual build used a separate detached
Zephyr worktree to leave the existing SDK checkout unchanged. The patch tool
now normalizes CRLF patch streams in memory so Windows checkouts build too.
The provenance tests also normalize text line endings; their pinned expected
hashes and source contents are unchanged.

```bash
source /home/fred/microblocks-zephyr-work/.venv/bin/activate
export ZEPHYR_BASE=/home/fred/microblocks-zephyr-work/zephyr-robot-eyes
export ZEPHYR_SDK_INSTALL_DIR=/home/fred/microblocks-zephyr-work/tools/zephyr-sdk-1.0.1
cd /home/fred/microblocks-zephyr-work
west build -b esp32p4_wifi6/esp32p4/hpcore \
  -s /mnt/c/Users/fred_/Documents/Codex/microblocks-zephyr/boards/waveshare_esp32p4_wifi6/zephyr \
  -d build-p4-robot-eyes -- \
  -DSMALLVM_SOURCE_DIR=/mnt/c/Users/fred_/Documents/Codex/2026-10-25/task-2/microblocks-zephyr/build-artifacts/p4-sources/smallvm
```

Zephyr: `a915b2f12675b48b16d56653ea145dcd8f20cbbf`; Espressif HAL:
`b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`; SDK 1.0.1 / GCC 14.3.0.
Repository base: `622c0c09fd0ad942f34048806629c0dd7a62c045` plus the local
eyes/pose changes identified by source hashes in the build summary. Nothing
was committed/pushed. The P4 application was installed with Fred's later
explicit authorization. Later rebuilds use
`west build -d build-p4-robot-eyes`. Generic reproduction can use the fetched
`build-artifacts/p4-sources/smallvm` instead of the existing verified cache.

Run `python3 tools/validate.py`, `python -m unittest discover -s tests -p
test_pose_tracker.py -v`, and on Linux/WSL `python tools/test_eyes_pose.py`.
The latter needs C/C++ compilers and uses the actual pinned library with
ASan/UBSan. The wire protocol is message 210, exactly 20 payload bytes:
`P4PS`, version 1, visible byte, gesture byte, reserved zero, little-endian
sequence u32, X/Y/confidence u16 each, reserved u16 zero. Confidence must be
500..1000 for visible people. Invisible samples must be centered, neutral,
confidence zero. Duplicate/backward sequence numbers cannot refresh a live
one-second lease; an expired sender can restart its sequence.

Evidence is under `evidence/2026-10-29/`: native build log/summary, portable
sanitizer results, real Windows/WSL inference summaries, validation log and
the actual editor screenshot. Public input/weights and firmware binaries
remain under ignored `build-artifacts`. The guarded pre-v3 image is
`build-artifacts/p4-robot-eyes-firmware/robot-eyes-pre-v3.bin`; do not install
it on revision-v3 silicon or use it to replace the C6 companion image.

Upstream references: [RoboEyes](https://github.com/FluxGarage/RoboEyes),
[Ultralytics pose API and COCO indices](https://docs.ultralytics.com/tasks/pose),
[YOLO11 pose weights](https://docs.ultralytics.com/models/yolo11), and
[Ultralytics licensing](https://www.ultralytics.com/license).
## Face engagement contract (2026-10-29, before implementation)

An opt-in `eyes greet and follow face` block owns gaze, mood, autoblink and
idle animation until disabled or Stop All. It accepts face presence separately
from COCO body pose. Face position makes the eyes happy and follows smoothly;
arm reactions still use the pose library. A three-second missing-face grace
holds the last gaze, then returns to the selected idle routine: sleep, wander,
or an eight-second wander / four-second drowsy / eight-second sleep cycle.
Waking opens both eyes. Sleeping disables autoblink so it cannot reopen them.
This moves OLED eyes only; no motors are controlled.

Message 212 is exactly 20 payload bytes: `P4FC`, version 1, visible byte,
left/right eyelid enum (0 unknown, 1 open, 2 closed), sequence u32, X/Y u16
(0..1000), head-direction and approximate eye-direction enums (0 unknown,
1 left, 2 center, 3 right), reserved u16 zero. Invisible packets are centered
with unknown states. The two-second receiver lease and sequence checks reject
replay; a missing/stale result must never renew presence. Directions refer to
the subject, before optional output mirroring. Eye direction is an expression
estimate, not calibrated screen gaze. Brief blinks cannot be validated at the
current USB acquisition rate.

The host uses the official MediaPipe Face Landmarker bundle, locally, with
face detection/presence thresholds >=0.6, optional YOLO arm pose, and bounded
P4-camera ownership. No image leaves this computer or enters Git. A separate
explicit `demo` source emits synthetic face/pose packets without a camera or
model and is labelled simulated throughout. It must demonstrate idle, wake,
left/right tracking, short occlusion, arm reactions and return to sleep; it
is not evidence of real vision. Acceptance: strict wire/missing-state tests,
policy transition tests, model inference on a public test face and a blank
frame, native compile/flash, and numerical real-USB state-transition evidence.
Actual face tracking still requires a usable live image and observed motion.

Camera diagnostic acceptance: the user confirms Pi Camera v2.1 with a clear
lens and lit room. The 150 ms startup delay did not improve pixels and is
removed. Add bounded compile-time manual IMX219 exposure/gain settings with
the original defaults preserved, plus explicit test-pattern diagnostics
(default OFF). A temporary colour-bars image can validate the pixel path,
but cannot count as a scene or detection. Restore pattern OFF before any
real capture/delivery. Compare a real high-gain capture with the original;
retain a changed default only with measured image improvement. Limits follow
the upstream Linux IMX219 register driver: analogue gain <=232, digital gain
256..4095, exposure <=1160 frame lines minus four. No AE/AWB claim.
