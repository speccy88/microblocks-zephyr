# Receive-only camera core: local acceptance

Branch: codex/pi5-watch-integration-20261027. Base before this additive phase:
79ed6cbd5f1e99b4caec901a3f8c686c85bea62a. Read-only public main recheck:
9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226. No shared-main change, push,
release, Pages deployment or access to the active P4 checkout occurred.

## Implemented and exercised

The [camera contract and reproduction](../../../linux/microduck/CAMERA.md)
describe a separate GStreamer consumer signaling/session core and owned
receive-only browser peer. The actual JavaScript modules execute with internal
fake signaling, RTC and media providers. They answer producer offers, queue
early ICE, hold early tracks until the answer write succeeds, disable audio,
reject local senders and expose one video track. The sole application query is
the fixed read-only media.video metadata request; no robot control RPC is sent.

- [38 focused tests](../../../linux/microduck/tests/camera-focused.txt): PASS,
  no skips. Malformed/bounded input, session ownership, final-answer ordering,
  channel restrictions, metadata, deadlines, races and cleanup are exercised.
- [207 selected Node tests](../../../linux/microduck/tests/camera-node.txt):
  PASS, no skips, including all previous 169 selected checks.
- [203 required repository tests](../../../linux/microduck/tests/camera-linux.txt):
  PASS in 246.227 seconds on existing WSL Linux, no skips.
- [End-to-end fixture](../../../linux/microduck/tests/camera-scenario.json):
  zero signals at construction, one media.video query, zero other application
  methods, video-only output and owned peer/tracks closed once. Its tracks,
  SDP/ICE and 1280x720/90-degree geometry are fictional; no frames are decoded.
- [Seven-profile package comparison](../../../linux/microduck/tests/camera-packaging.json):
  all GP JS/data hashes and hardware-connection flags match the prior canonical-LF
  watch package. Four new modules copy exactly. Existing console/simulation HTML
  is unchanged and retains connect-src 'none'; no existing page loads the camera
  modules. The unavailable release/copy gate remains intact.
- [Source audit](../../../linux/microduck/tests/camera-source.json): four exact
  Pollen Git blobs and independent official GStreamer0.15.3 protocol bytes
  match the retained SHA-256 values. No media implementation is redistributed.
- [Validation receipt](../../../linux/microduck/tests/camera-validation.json)
  binds source hashes, results and raw-versus-LF capture hashes. The
  [evidence index](../../../linux/microduck/tests/camera-evidence-hashes.json)
  additionally covers retained supporting files.

Focused reproduction:

```sh
node --test tests/test_microduck_camera.cjs
python tools/validate.py
python tools/package_pages.py --ide-source build-artifacts/ide-source --output build-artifacts/pages-NEW
```

The full explicit selected Node command is in the additive Linux workflow.
The repository validator used the existing WSL venv with its pinned WebSockets
dependency; Python mocks use real private Unix paths/sockets where applicable.
The camera JavaScript tests use no network sockets or native browser APIs.

## Remaining acceptance and boundaries

This is transport preparation, not a working live camera viewer. No live dialer,
trusted signaling identity, endpoint configuration, production viewer/rotation
UI or native SmallVM camera primitive is supplied. Codec/ICE/DTLS, browser
playback, decoded frames, shipping image and actual mounting geometry remain
unverified. The pinned LAN signaling server has no authentication gate; metadata
and discovered IDs do not attest identity, confidentiality or permission to move.
Local cleanup is not a camera power-off, robot shutdown or emergency stop.

No actual RTC, GStreamer, robot, camera, BLE, motion, media capture or Edge-control
operation ran in this phase. No Pi command was necessary: native SmallVM, UBL,
gateway and existing portal/BLE/console sources are unchanged from the base.
Historical real Pi evidence remains separately scoped and is not reused as
camera evidence. Continuous motion/direct motors remain unimplemented.

The stopped Edge URL-policy operation and previously safety-denied actions were
not retried or bypassed. There is no pending approval for this software phase.
Live transport/privacy commissioning, physical MicroDuck arrival, P4 coordination,
hosted CI, final publication provenance and reboot/startup remain separate gates.
