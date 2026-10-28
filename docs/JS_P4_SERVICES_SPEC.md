# P4 services in the JavaScript editor

Continue from `87d70ed` with local overlays. The P4 native/media/neural/files
sources match the public main snapshot inspected at `6e2b4f9`; no newer P4
branch is published. Their current private owner checkpoint remains unknown.
Do not access that owner's checkout or COM5/COM12, change firmware, resume SFC,
modify GP or publish this work. Hardware acceptance requires coordination.

The P4 profile may offer explicit WSS in addition to USB. Accept only a bounded
`wss://` URL with exactly `/ws/vm`, no credentials, query, fragment or control
characters, on an HTTPS/loopback editor. Keep the browser's normal certificate
verification, require the existing `ready` marker and then the selected board
identity, and never fall back to insecure WS. Store no endpoint or credentials.
Synthetic socket tests establish frontend behavior only; a trusted board TLS
endpoint, C6 networking and real WSS acceptance remain uncommissioned.

Use the existing identified connection for all services. Add no second port,
connection discovery, credentials or automatic camera/audio execution. Preserve
the pinned upstream engine and private P4 primitive map.

## Protocol and lifecycle

The native source bounds response bodies: image206 at514 bytes, preview207 at4,
media208 at526, site209 at12, neural216 at1010 and files217 at640. Consume only
complete length-framed replies, preserve ordinary VM messages and order, and
cap aggregate receive data at128 KiB. Malformed extension lengths disconnect
that session. Drop extension traffic before board identity verification. Give
each consumer its own frame copy; contain consumer failures.

Queue validated request frames through the existing bounded sender, after
identity verification. A synchronous accepted-byte result means queued, not
delivered or successful. Bind subscriptions and send closures to the connection
generation. Disconnect cancels pending service work and invalidates old closures;
old replies/queued writes must never feed a replacement connection.

Connect the preserved device-files controller/wire/client/UI and neural import
panel through this seam. Keep their existing explicit buttons, conditional RAM
writes, uncertainty/cancellation behavior, bounded model manifest/hash checks
and lack of actuator binding. Do not introduce a fixture into a production
package. A disconnected panel must make no service requests. Media capture and
per-block image/audio rendering require additional adapters, not merely dispatch.

## Acceptance

Use actual pinned connection/CommPort classes and the new guarded transport
with faithful USB fixtures. Test fragmented and interleaved VM/extension frames,
every response size boundary, pre-identity traffic, handler failures, byte-copy
isolation, malformed requests, disconnect/reconnect and stale send closures.
Exercise file-session replies through the existing typed controller and native
storage service fixture where available. Verify the actual neural/files panels
graphically while disconnected and preserve error/unavailable semantics.
Run the unchanged full repository validator and record exact source hashes.
No fixture or old GP physical result constitutes JS hardware acceptance.
