# Read-only MicroDuck camera checkpoint

The dedicated local `media.frame` path follows Pollen commit
`96b89d8613f06722c1d64ce75ab0d7124fed9d8f`, API 44. Source hashes and exact
file names are recorded in `source-audit.json`. The endpoint uses a JSON header
followed by raw bytes and is deliberately excluded from generic JSON forwarding.

Camera and Simple Camera share a checked private Unix gateway. Capture one UYVY
frame, read its dimensions, format, reported rotation, exact unsigned 128-bit
Unix-microsecond timestamp or raw Y/U/V pixels, then release it. Raw Y is not lux.
Coordinates are stored-image pixels; rotation is reported, never silently applied.
Unknown, expired, malformed and unavailable readings cannot be extracted as zero.

The reader has a 3-second transaction deadline, 4 KiB JSON header limit, 16 MiB
raw frame limit, four retained/in-flight slots and five-second handles. Cancellation
and shutdown release resources. Raw frames remain outside SmallVM JSON buffers.
No generic camera command, recording, microphone, motion or credential path is added.

The optional **MicroDuck Camera Lab** combines the existing ten Starter modules
with Camera and Simple Camera: 12 modules and 227 compiled functions. Simple and
advanced blocks remain available together. The ordinary six-module and ten-module
Starter bundles keep their original content and function counts (169 and 211).

Focused validation passed 19 Unix/native tests and 3 JavaScript import/native
execution tests, with no failures or skips. These cover fragmented and malformed
framing, API/UID/config checks, timeout/cancellation, capacity, expiry, raw zero and
255, paired chroma, exact timestamps and garbage collection. The actual pinned JS
editor importer, compiler and serialization classes compile and reopen the bundle;
representative simple and advanced compiled blocks execute on the sanitized VM.
This is headless editor testing, not a graphical browser acceptance claim.

Earlier failures are retained: tiny fragments in the malformed-header fixture hit
the transaction deadline before the malformed framing assertion; that case now
uses large fragments while separate fragmentation and timeout tests remain. A
Windows sandbox temp-directory denial was resolved by selecting writable workspace
temp; native tests subsequently ran in Linux. No production limit was relaxed.

All camera input is a fictional 4 by 2 UYVY fixture. No camera or robot was used,
and no new binary was installed on the Pi. Physical camera, shipping socket/API
commissioning, graphical acceptance, RGB conversion, preview and continuous video
remain separate work. The Pi installer service and denied reboot were untouched.

The full unchanged repository validator will run from frozen source inputs; its
separate final receipt records the result and hashes. No publication is performed.
