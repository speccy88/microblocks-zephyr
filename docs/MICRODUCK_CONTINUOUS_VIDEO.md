# Continuous video assessment

Reviewed Pollen commit `96b89d8613f06722c1d64ce75ab0d7124fed9d8f`;
this assessment does not upgrade that pin or enable a stream.

| Path | Pinned behavior | Integration status |
|---|---|---|
| Local `media.frame` | One JSON header followed by exact UYVY bytes, then close. The daemon registers demand for a snapshot. | Implemented finite native capture and typed raw/RGB pixels. It is not a subscription. No polling loop is added. |
| Browser WebRTC | Upstream recommends WebRTC for a person watching the robot. GStreamer signaling negotiates the producer offer, consumer answer and ICE; the media/control session reports video geometry. | Existing receive-only observer and bounded frame callback lifecycle use fake signaling/RTC. Trusted shipping signaling, peer identity, codec/DTLS/ICE and actual native decoding remain unverified. |
| Outbound `media.stream` | No URL key asks for status; a URL starts a stream to that receiver, and `url:null` stops it. The robot dials outward. The hello declares encoding. Binary messages carry JPEG images or H.264 access units. | Existing simulation exposes diagnostics; this preview adds no destination, start/stop or receiver. Starting a stream changes where footage is sent and requires a separately reviewed destination and transport. |

Sources: [frame endpoint](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/frame.rs),
[session routing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/session.rs),
[outbound stream](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/stream.rs),
[pipeline](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/pipeline.rs).

JPEG frames are independently decodable; the upstream queue drops old frames
when a consumer falls behind. H.264 uses inter-frame prediction, so after a drop
the upstream path waits for a new keyframe and supplies SPS/PPS at keyframes.
A future decoder must bound encoded input, dimensions, queue bytes, outstanding
frames and session duration, close decoded frames promptly, reject stale sessions,
and handle keyframe loss without displaying corrupt or stale output. Native
decoder behavior needs real browser tests, not callback injection.

The new RGB snapshot lab converts a fixed fictional UYVY array into one capped
canvas. It is neither JPEG/H.264 decoding nor a live viewer and is not connected
to SmallVM's per-block image rendering. P4's media RPC and firmware handles are
not a MicroDuck protocol and must not be reused as if robotd/mediad provided them.
A separately designed bounded VM-to-editor snapshot bridge remains necessary for
inline MicroDuck image results. Simple and advanced numeric RGB pixel blocks are
usable together through the existing gateway today with fixture validation.

Audio is not carried by this frames-only path. No audio API, local capture,
credentials, receiver listener, live signaling or movement is invented here.
Shipping commissioning and physical camera acceptance remain gates; Pi execution
against fictional services cannot establish them.
