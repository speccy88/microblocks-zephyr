# Camera viewer and frame observation contract

## Scope before implementation

Add a reusable receive-only video-element viewer and a standalone, clearly
labelled simulation lab on the isolated camera branch. Consume only the owned
video-only stream delivered by CameraSession, with its typed reported geometry.
Do not add a live signaling dialer, device picker, endpoint, credentials, local
capture, recording, image export, robot RPC or motion command. Do not change the
BLE/console security boundaries or retry blocked Edge control.

The documented browser [video frame callback interface](https://wicg.github.io/video-rvfc/)
reports a frame submitted to the compositor; a track event, dimensions,
loadeddata/playing event or resolved play() promise alone is not this evidence.
The [media play interface](https://html.spec.whatwg.org/multipage/media.html#dom-media-play)
can reject or remain pending. Both paths need bounded cancellation without
replay. Pollen's pinned media.video rotation remains reported, unattested data;
display adjustment must not become calibration or motion authorization.

## Acceptance criteria

1. Viewer construction is passive and requires a fresh, empty video element.
   Explicit attach accepts exactly one live video track and no audio. It sets
   muted/playsInline, assigns only srcObject and attempts play once. No URL,
   getUserMedia, addTrack, captureStream, canvas capture or general control API.
2. Observe requestVideoFrameCallback only with its cancellation pair available.
   Require owned current source, a live track, usable media readiness, positive
   bounded frame dimensions and an increasing safe presentedFrames counter.
   Media events and playback promises never increment the observation count.
   Ignore stale callbacks after cancellation. Snapshots store bounded numbers
   and fixed codes, never pixels, stream handles, URLs or browser error text.
3. A callback is labelled simulated whenever a fixture supplied it. No mock test
   claims native decoding, displayed physical footage, trusted identity or
   physical MicroDuck acceptance. Separate historical frame observation from
   current freshness; pause/wait/stall removes the fresh-frame indication.
4. Bound first-frame wait, stalls, total duration and callback count. Playback
   denial, media/track failure, source replacement or stop clears timers/events,
   cancels the outstanding frame callback, pauses/detaches media, stops the owned
   track and closes the owning session once. No automatic play/reconnect retry.
5. Report unknown orientation without guessing zero. Allow only typed 0/90/180/270
   reported rotation; use validated video display dimensions for display layout.
   Preserve callback media-pixel dimensions separately for anamorphic sources.
   Rotation is a display adjustment, not robot/world geometry or calibration.
6. Simulation composes the actual CameraSession/BrowserPeer/viewer with internal
   fake signaling, RTC, tracks and media callbacks. It creates no actual browser
   video, media source or decoder. A canvas test card is explicitly fictional;
   no capture, encoding or captureStream is used. Named failure cases include
   absent frames, blocked play, stall and unavailable frame callbacks.
7. The lab starts detached, discovers only after a click, requires explicit
   producer selection/start, and closes on stop/pagehide/hidden page. It accepts
   no connection parameters and renders untrusted labels as text. CSP forbids
   network and media URLs. Tests exercise actual modules with fake DOM/media,
   including pending play, stale callbacks, limits, metadata and lifecycle races.

## Unverified scope

Tests of injected callbacks do not execute native media decoding or establish
graphical layout/browser interoperability. Live trusted signaling, shipping
camera/API geometry, codec/ICE/DTLS, physical playback and browser permissions
remain separate acceptance gates. No real robot or motion test is performed.

## Implementation and reproduction

[VideoViewer](../../web/microduck/camera-viewer.js) takes an empty owned video
element, an explicit simulation flag, state/close callbacks and finite limits.
It exposes attach(stream), setGeometry(reportedOrNull), snapshot() and close().
The owning CameraSession is closed through onClose; the adapter never dials a
transport or selects a source. A native integration must keep the video element
exclusive and wire session-close events back to viewer.close(). It must supply
the trusted transport/commissioning independently; this lab provides none.

The observer records only numeric dimensions/counters and fixed outcomes. A
snapshot's frameEvidence is none, simulated-callback or browser-frame-callback.
browserFrameCallbackObserved reports the latter case, without asserting a real
camera or trusted source. decodedFramesVerified and physicalMicroDuckTested
remain false: test-injected callbacks are not native decoding evidence.
playResolved, track receipt and media events never establish frame observation.
frameFresh clears on pause/wait/stall and all closes; earlier counts remain
historical only. Media/capture timestamps and pixels are not retained.

First-frame and stall timeouts default to five seconds, each at most thirty
seconds. Viewer duration defaults to sixty seconds, at most five minutes.
Callbacks default to 1,800 and are capped at 18,000, with one outstanding request.
Every close clears the deadlines, callback, media/track listeners, source and
owned track. A foreign replacement source is left untouched. A newly inserted
source child is refused without loading its URL during cleanup.

Reported rotation affects only presentation. Missing/invalid rotation remains
unknown even when the display is unadjusted. Callback media dimensions may
differ from videoWidth/videoHeight; the latter determine the element's aspect
ratio. The quarter-turn layout swaps that ratio and sizes the centered media
element to fit. No calibration, world geometry, framerate, latency or motion
authorization is inferred.

[The lab page](../../web/microduck/camera.html) is linked from the MicroDuck panel
and packaged as microduck/camera.html. It uses the actual camera transport and
viewer with internal fake RTC/media callbacks, plus a locally drawn 640x360
test card. The card is never captured, encoded or decoded video. All exported
fixture options are bounded simulation settings/callbacks; arbitrary endpoints,
credentials, transport and media providers are refused. Native browser video is
not constructed by the fixture. The page's CSP blocks network and media URLs.

Use an existing trusted project preview server or the packaged local portal to
open the lab. Starting a new server is not required by these automated tests:

```sh
node --test tests/test_microduck_camera_viewer.cjs
node --test tests/test_microduck_camera.cjs tests/test_microduck_camera_viewer.cjs
python tools/validate.py
```

The focused suite exercises real viewer/panel code with fake DOM and media APIs.
It checks all failure scenarios and cleanup without an external network, native
RTC, browser media decoder, recording, actual robot or Edge-control operation.
Source and validation receipts are under tests/camera-viewer-*. No physical or
graphical acceptance box is checked by these tests.
