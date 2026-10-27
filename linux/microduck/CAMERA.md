# Receive-only camera transport specification

## Scope before implementation

Implement the reviewed camera signaling/peer interfaces as a separate observer.
Do not add locomotion, control forwarding, local capture, authentication or a
live network endpoint to the portal. Accept an existing signaling link only;
automated acceptance uses an internally constructed in-memory link and fake
browser peer. No real camera, private footage, robot or Edge control is used.

Primary sources: Pollen MicroDuck commit
96b89d8613f06722c1d64ce75ab0d7124fed9d8f, especially
mediad/webclient/index.html, mediad/src/pipeline.rs and mediad/src/session.rs;
and the [GStreamer0.15.3 signaling protocol](https://raw.githubusercontent.com/GStreamer/gst-plugins-rs/0.15.3/net/webrtc/protocol/src/lib.rs).
The producer offers; the consumer answers. Signaling uses welcome, list,
startSession, sessionStarted, peer with SDP/ICE, and endSession. A producer
listing does not authorize automatically selecting its first camera.

Upstream mediad creates a reliable ordered control data channel with a much
broader robot API. This observer exposes no general RPC interface. Its sole
application request is the documented read-only media.video metadata query;
it rejects/closes other channel labels and never sends robot.*, credentials,
updates or provisioning. The LAN signaling server has no authentication gate
in this pinned source. A future live connection therefore requires separate
operator/network/privacy commissioning; this is not a confidential BLE bridge.

## Acceptance contract

1. Construction/attachment sends nothing. Discovery and selection are explicit;
   select only a currently discovered producer and require a fresh confirmed
   start. No arbitrary URL, token, PIN, PSK or RPC parameter is accepted.
2. Validate bounded JSON, exact signaling envelopes, IDs/session ownership,
   source-shaped SDP offers/answers and ICE candidates. Serialize asynchronous
   signaling work, queue early ICE within fixed bounds, and discard late/stale
   events. Never retry or reconnect automatically.
3. Use browser answer APIs with video transceivers recvonly and audio inactive.
   Never getUserMedia/getDisplayMedia, add a local track, create a data channel,
   or permit an existing local sender. Accept one remote video track only;
   exclude/stop audio and unexpected tracks. No implicit STUN/TURN service.
4. The fixed metadata request is sent only on the reliable control channel after
   the local answer is queued. No incoming method can invoke a browser or robot
   action. Metadata is optional, bounded and typed. Missing/bad orientation is
   unknown, never guessed upright; do not convert unrepresentable clock values.
5. Success means a local answer was sent and a remote track event was received,
   not decoded frames, a live physical camera, verified identity or robot-ready.
   Metadata and producer advertisements do not attest authentication or shipping
   API compatibility. No stream/SDP/ICE/address/remote-error payload is logged or
   persisted in snapshots.
6. Bound discovery/negotiation deadlines, session duration, message/queue/candidate
   counts, producers, data channels and metadata. Stop, timeout, failure or drop
   clears timers/handlers, closes peer/signaling and stops retained tracks.
   Send endSession only for the owned known session; local cleanup is not a
   camera-off guarantee, motion stop, robot shutdown or emergency stop.
7. Mock tests must exercise actual signaling and browser-adapter code, including
   final-answer/early-track races, offer/candidate ordering, wrong/stale sessions,
   malformed/oversized input, callback errors and cleanup. In-memory fixtures
   label all IDs, tracks, SDP and geometry fictional and never open a real
   WebSocket/RTCPeerConnection or access a real media device.

## Implemented interface

CameraSession takes {link, makePeer, onVideo, onState, simulation=false,
timeoutMs=10000, durationMs=60000}. An existing link provides subscribe/send/close;
the observer never dials it. discover() requests producers; start(id,{confirmed:true})
answers an explicitly selected session; stop() closes it. snapshot() contains
bounded sanitized state/metadata/counters, no signaling payloads or media object.

BrowserPeer takes explicit constructor providers (or browser APIs when explicitly
created), plus onVideo/onIce/onMetadata/onFailure. Its methods are answer(offer),
addIce(candidate), activate() and close(). No raw connection/channel/RPC handle
is exported. A dedicated fixture uses these actual classes with internal fakes.

The modules are [protocol](../../web/microduck/camera-protocol.js),
[browser peer](../../web/microduck/camera-peer.js),
[session](../../web/microduck/camera-session.js) and
[fictional fixture](../../web/microduck/camera-fixture.js). They export CommonJS
and browser globals, with no work at load time. The portal packages them but
does not load or instantiate them in an existing user flow. The fixture accepts
only finite limits, named faults and observation callbacks; it rejects endpoint,
transport, provider and credential options. Its synthetic SDP is not a valid
codec/DTLS interoperability test, and its video track contains no real frames.

Discovery and negotiation default to ten seconds each, bounded to thirty seconds.
An active observation defaults to sixty seconds, bounded to five minutes.
Signaling limits are 64KiB/message, 48KiB/SDP, 4KiB/candidate, 32 producers,
32 queued events/early candidates, 64 ICE candidates per direction and 256
received or ordinary outgoing signaling messages. Cleanup may attempt one
additional owned endSession, without claiming remote delivery. A peer accepts
at most eight channels, one reliable ordered control channel, and 32 control
messages of at most 16KiB. It makes at most one metadata query. Missing metadata
becomes unknown after five seconds by default; invalid/changing metadata closes
that channel without claiming the video is calibrated or motion-safe.

Run the focused tests without network, browser control or hardware:

```sh
node --test tests/test_microduck_camera.cjs
```

Run the same internal fixture interactively from the repository root:

```sh
node -e "(async()=>{const f=require('./web/microduck/camera-fixture.js').createFixture();try{const rows=await f.session.discover();await f.session.start(rows[0].id,{confirmed:true});console.log(JSON.stringify({session:f.session.snapshot(),simulation:f.snapshot()},null,2));}finally{f.close();}})().catch(e=>{console.error(e.code);process.exitCode=1;})"
```

Here confirmed:true approves only the fictional session in this internal fixture.
It does not commission a live camera or authorize any robot command. Source and
validation receipts under [tests](tests/camera-validation.json) distinguish the
executed real JavaScript modules from injected signaling, browser and media APIs.

This checkpoint prepares transport code, not a commissioned live camera UI.
Trusted signaling, live browser/media interoperability, codecs/ICE/DTLS,
mount geometry, playback/decoded-frame proof and actual robot behavior remain
distinct acceptance gaps. Continuous motion/direct motors remain unimplemented.
In particular there is no live signaling dialer, endpoint configuration, trusted
signaling identity, production viewer, frame rotation UI or native SmallVM camera
primitive in this checkpoint. Receiving a track event does not prove playback.
Future work must validate the actual shipping image and media.video fields,
privacy/authorization, trusted browser transport and negative disconnect cases
before exposing live camera selection. Never attach the broad upstream control
channel to the advanced BLE console or bypass an insecure-content/certificate
warning to exercise it.
