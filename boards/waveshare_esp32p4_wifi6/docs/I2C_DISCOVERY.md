# I2C discovery and readings contract

Physical acceptance (2026-10-26): address-only scan found 0x10, 0x18 and 0x64.
Explicit identification confirmed IMX219 0x0219 and ES8311 0x8311. Address 0x64
remains unknown, with zero supported measurements. Actual IMX219 register
reads returned exposure 800 lines and analog-gain code 128; these are retained
configuration values, not a new capture. Three rescan rounds, invalid/stale
references, unsupported readings and Stop All passed. Real GP example execution
displayed `537 ID` (decimal 0x0219), with clear non-overlapping native blocks.
The screenshot is delivered separately, not committed. See p4-i2c-native.json.
The fast real scan completed before the next busy poll, so its evidence has
zero VM calls while busy; do not claim a measured long-transfer responsiveness
or hardware timeout/cancellation latency from that sample.

Scan an explicitly selected configured bus, 7-bit addresses 0x08..0x77, using
address-only transactions. Never select mux channels, reset, initialize or
write configuration automatically. Identification is a separate explicit scan
option: only allowlisted documented ID-register reads. A register-pointer
write precedes those reads; address probing and identification cannot be
guaranteed harmless for every unknown device. Use address-only mode for an
unknown bus. Reserved addresses are excluded.

Report address, bus, sensor name, confidence and supported measurements.
The scan reporter returns completion/error text; `devices found` separately
reports the bounded numeric count, including partial results after cancellation.
An ACK is not an identity. Address candidates remain unconfirmed; unknowns
stay unknown. A bounded scan holds at most 32 results and reports truncation,
timeout and cancellation. Every scan invalidates prior sensor references.
Readings recheck identity to reject stale/replaced devices and return an
integer value with explicit unit/scale or an explicit error. Unknown devices
and unsupported measurements never receive guessed register reads.

Initial adapters: TMP117 temperature (milli-degrees C, signed register /128,
reset sentinel/not-ready and shutdown detected), IMX219 identity/exposure-line
count/analog-gain register code, OV5647 identity and ES8311 identity. Camera
controls are configuration readings, not a fresh image. ES8311 PCM travels
over I2S; an I2C codec ID is not a sound reading. External TMP117 hardware is
not currently attached: fixture proof is separate from physical proof.

The portable C registry owns no VM objects, allocator or RTOS dependencies.
Zephyr uses its I2C driver and a bounded worker; P4 exposes only configured
bus 0 (SDA7/SCL8). Camera/audio starts are rejected during discovery/read jobs,
and discovery/read rejects an active capture. All starts originate on the VM
thread; the native I2C controller serializes transfers. No long worker lock
blocks the VM. Stop All cancels; cancellation is checked between transfers.
Pinned ESP32 I2C transfer timeout is 500 ms; a wedged bus can take two such
phases per call, so a two-second overall budget can overrun by one bounded
driver call. Do not describe cancellation as instant.

Acceptance: fixture unknown/candidate/confirmed/hot-swap/negative temperature/
not-ready/shutdown/unsupported/error/bounds/deadline/cancel/truncation cases;
native build and safe real onboard identity/config reads; repeat scan/read,
stale references and VM responsiveness; generated-media and NN regressions;
actual GP example, labels/units/help, no-result/error state and screenshot.
USB and station-hosted packages share the same library. Actual network tests
remain blocked separately by the documented C6 request-284 failure.

Inspired by SparkFun Universal Auto-Detect, MIT software license, commit
39b20cc3a9a1b1163f14fdfb8812c754926734c8. That library's begin/initialize/mux
operations are not imported wholesale. The initial adapter uses documented
register semantics and independently written portable code; no bundled
third-party sensor libraries are copied.

Sources:
- https://github.com/sparkfun/SparkFun_Qwiic_Universal_Auto-Detect
- https://www.ti.com/lit/ds/symlink/tmp117.pdf
- Existing licensed p4_sensors.c and audio_backend.c for onboard identity and
  camera register configuration. Their notices remain unchanged.
