# Receive-only camera viewer: local acceptance

Branch: codex/pi5-watch-integration-20261027. Base before this additive phase:
b6df7d010d588e4ed19fb6fec33f2fede83884e0. Shared main and the active P4 checkout
are unchanged. No release, Pages deployment, credential or startup change occurs.

The [viewer contract and reproduction](../../../linux/microduck/CAMERA_VIEWER.md)
describe an owned video-element adapter, frame-callback observation, reported
rotation layout and a standalone simulation lab. The actual viewer, panel,
camera session and browser-peer modules execute against fake DOM, signaling,
RTC and media/callback providers. The page draws a locally generated fictional
test card. It does not capture, encode or decode video and contains no live
endpoint, credential or robot-command control.

- [36 focused viewer tests](../../../linux/microduck/tests/camera-viewer-focused.txt):
  PASS, zero skips. Playback promises/events do not count as frame evidence;
  callback metadata, rotation, source ownership, failure bounds and lifecycle
  cancellation are exercised.
- [243 selected Node tests](../../../linux/microduck/tests/camera-viewer-node.txt):
  PASS, zero skips, including all prior 207 selected checks.
- [203 required Linux repository tests](../../../linux/microduck/tests/camera-viewer-linux.txt):
  PASS in 124.481 seconds, zero skips, using the documented, provenance-verified
  external sanitizer VM inputs described below. Both default-build timeout
  attempts remain separate failed results.
- [Complete fixture scenario](../../../linux/microduck/tests/camera-viewer-scenario.json):
  construction sends nothing; three simulated callbacks reach FRAME_LIMIT;
  the sole application method is media.video. The owned fake track/peer and
  pending callback close without replay. Native decoding is explicitly false.
- [Seven-profile packaging](../../../linux/microduck/tests/camera-viewer-packaging.json):
  all GP JS/data hashes and connection flags match the earlier camera-core
  package. Eight camera assets copy exactly, seven local scripts resolve, and
  the panel links to microduck/camera.html. The standalone console and
  commissioning HTML remain byte-identical. CSP blocks network/media URLs and
  the unavailable-release/copy gate remains intact.
- [Primary browser interface sources](../../../linux/microduck/tests/camera-viewer-sources.json)
  distinguish interface review from execution. The existing pinned Pollen and
  GStreamer source audit remains unchanged; no media implementation or video
  file is redistributed.
- [Validation receipt](../../../linux/microduck/tests/camera-viewer-validation.json)
  binds final sources and captures; the
  [evidence index](../../../linux/microduck/tests/camera-viewer-evidence-hashes.json)
  records retained file hashes and lengths.

An initial combined run exposed a fixed-sleep assumption in the stall fixture
test. It now waits for the bounded closed outcome before checking the exact
code. Production timeouts were not increased. Final captures above contain
the successful run against the final source.

The first Linux validation attempt ran 182 tests in 424.403 seconds and reported
three existing sanitizer-build deadline errors, each at 120 seconds. Its
[failed capture](../../../linux/microduck/tests/camera-viewer-linux-initial-timeout.txt)
is retained. WSL load was 6.53 on two logical CPUs, which is consistent with
resource contention but does not establish the exact cause. The desktop then
disconnected during a read-only diagnostic; no process cleanup executed.
After reconnection, load was 0.08 and no processes remained in the three exact
failed temporary build directories. The unchanged validator was rerun once,
without compiler, sanitizer, source, timeout, security or device changes. It
ran 185 tests in 338.813 seconds, with one remaining VM setup compilation timeout;
the [second capture](../../../linux/microduck/tests/camera-viewer-linux-unchanged-rerun.txt)
is retained too. The
[recovery record](../../../linux/microduck/tests/camera-viewer-recovery.json)
keeps these observations separate from the final test result.

A single fresh pinned ASan/UBSan VM then compiled and self-tested successfully
in 144.238 seconds. Its [provenance](../../../linux/microduck/tests/camera-viewer-native-provenance.json)
checks the binary hash, native x86-64 ELF, source pin, sanitizer flags, successful
self-test and all 12 current port-source hashes. That actual build duration exceeds
the unchanged 120-second setup limit; no compiler or sanitizer assertion was
removed. Final full discovery uses the suites' existing documented external
inputs SMALLVM_MICRODUCK_BINARY and SMALLVM_NUMERIC_BINARY, both naming this
verified binary. All test classes, assertions and runtime deadlines remain.
The default repeated-build path remains timing-sensitive on this host; a pass
with the documented binary input must not be described as a successful default
rebuilding invocation.

## Reproduction and limits

```sh
node --test tests/test_microduck_camera_viewer.cjs
node --test tests/test_microduck_camera.cjs tests/test_microduck_camera_viewer.cjs
python tools/validate.py
python tools/package_pages.py --ide-source build-artifacts/ide-source --output build-artifacts/pages-NEW
```

For the retained full Linux run, first build/verify the pinned sanitizer VM,
then use its absolute path through the existing supported test inputs:

```sh
SMALLVM_MICRODUCK_BINARY=/absolute/verified/smallvm \
SMALLVM_NUMERIC_BINARY=/absolute/verified/smallvm \
python tools/validate.py
```

The full explicit selected Node command is in the Linux workflow. The required
validator uses the existing WSL Python venv and local native/Unix fixtures.
No new Pi run is needed or claimed: native VM, UBL, gateway and core camera
transport are unchanged. Historical Pi execution evidence remains separately
scoped; it does not establish camera playback.

The video-element adapter observes requestVideoFrameCallback metadata rather
than inferring a frame from play(), loadeddata or a track event. In the lab,
frameEvidence is simulated-callback; decodedFramesVerified, native decoding
and physical MicroDuck status stay false. Counts retained after close are
historical only and freshness clears. Clocks, footage, source URLs and raw
media/browser error text are not stored. Reported rotation is unattested display
adjustment, never calibration or motion authorization.

Native decoder/codec/ICE/DTLS execution, graphical layout, actual browser playback,
trusted live signaling identity/transport and shipping camera/API/geometry are
unverified. The actual HTMLVideoElement integration still needs that separate
commissioning and browser acceptance. This page accepts no live source and its
drawn canvas is not decoder evidence. Any native SmallVM camera primitive and
continuous motion/direct motors remain unimplemented.

The stopped Edge window18679338 operation remains blocked because the platform
could not determine its current browser URL confidently enough to enforce policy.
It was not retried or bypassed. No real robot, motion command, camera, media
capture, BLE, alternative UI-control route or previously denied action ran.
No approval is pending. Hosted CI, coordinated P4 integration, publication,
trusted transport/real BLE confidentiality and startup/reboot remain separate gates.
