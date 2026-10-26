# P4 USB RAM storage: physical acceptance, 2026-10-26

The owner explicitly authorized replacing the P4 firmware and testing RAM storage.
COM5 identified as CH343 1a86:55d3; the ROM reported ESP32-P4 revision 1.3 and
32 MiB flash. Existing SmallVM reported the USB-only profile. That profile was
preserved: no C6 access, Wi-Fi association, credential/security change, AP,
COM12 access, firmware backup or GitHub publication occurred.

## Installed artifact

Both pre-existing USB/station ELF, configuration and binary hashes matched the
completed local RPC-memory audit before any flash. Only the USB image was used.
The ROM revision guard changes the revision header fields, so its installed
hash differs from the compiled image hash. One flash at 0x2000 succeeded and
esptool verified the written data; no uncertain retry or second flash occurred.

- Native Zephyr / SmallVM v417, Waveshare ESP32-P4 WIFI6.
- Image: 15411312 bytes; installed guarded SHA-256
  `b46a58136e264d54ab7944471f8cfc5ae918d29f9e5ca3dca620ca34c8beb065`.
- Compiled USB SHA-256
  `3b334cf5b7fb45c75b38fa3e89a10af00679ce1e0120543605bdd267591b990b`.
- Flash erase range 0x2000..0xeb4fff, below assets at 0xfe0000 and settings at
  0x1fe0000. Those regions were not read back or rewritten by this test.
- Firmware source/ELF/configuration remain the locally validated build; the
  only subsequent product-code edit corrects a browser connection label.

## Actual board results

`tools/test_p4_storage_usb.py --execute --evidence <local.json>` opens COM5 only
and requires the USB profile. It stops if RAM already contains files rather
than clearing unrelated contents. Its cleanup removes only its own test paths.

918 framed file requests passed. Maximum observed request round trip was 63 ms
in this run; this is not a real-time guarantee. Checks include empty, UTF-8 and
8192-byte binary files, exact readback, shared VM-block/file-manager ownership,
revision conflicts, duplicate IDs, malformed-message recovery, unavailable
backends, invalid paths, oversize/full-store rejection, cancellation, Stop All,
session close/stale-session rejection, USB reconnect and 16 full-size replace/
read cycles. All eight file slots were filled to 65536 payload bytes while
8294400 bytes of independent image buffers were allocated and released.

The genuine GP 2.5.8 editor ran the RAM-file example, displaying
`Hello from MicroBlocks`. Device files listed and opened that board-created
file. A UTF-8 edit and a second JSON file were saved, reopened after a new file
session, and independently read back through COM5. Dirty-edit protection was
also exercised. The production package has no browser fixture enabled.

The browser path was **GP editor -> loopback WebSocket bridge -> COM5 -> native
Zephyr RAM**. This proves the actual application/USB path, not Web Serial's
browser device chooser or board-hosted Wi-Fi. The local bridge label now says
`USB bridge connected`; it no longer incorrectly claims a secure WebSocket.
That wording was verified in a fresh tab with the final adapter hash. The
corresponding 47 transport/editor tests passed.

The files survived PPA, NN and Whistle regression work. A single subsequent
P4 reset cleared them; both the protocol and fresh real editor then showed
0 bytes and eight free slots. Final capture/listening state was inactive.
The editor was disconnected and COM5 released. The loopback editor may remain
open for inspection; it opens COM5 only on an explicit Connect action.

## Memory and related regressions

- PPA generated-pixel identities, rotations, mirrors, scaling, eight cancellation/
  reuse cycles, result-capacity cleanup and 8.29 MB reallocation passed. No camera
  capture or microphone recording was performed.
- Native NN builtin/custom golden vectors, malformed/unsupported/oversized model
  rejection, repeated load/run/unload and cancellation passed. No actuation.
- Whistle correctly rejected its 12 MiB reservation under image pressure,
  preserved the image handles, then transcribed the existing flash fixture after
  release. Requested workspace peak was 2266424 bytes inside the 12582912-byte
  reserved arena. Runtime reported 21572 unused bytes in its 65536-byte worker
  stack. Inference completed in 21143 ms and released its buffers. This was
  synthetic stored PCM, with no microphone or speaker use.
- These tests show the CPU-owned RAM store/transfer placement working alongside
  the exercised PSRAM allocations and PPA path. They do not prove every cache-
  disabled or DMA interleaving, or provide all-thread stack/heap watermarks.
- `freePSRAM` is explicitly unimplemented; no free-heap measurement was invented.
  The USB linked internal/libc totals remain 243856 / 149360 bytes. The station
  build's 9424-byte libc arena and isolated 64 KiB protobuf pool were NOT exercised
  on hardware: that profile would involve the excluded C6.

The canonical regression suite passes 61 checks using the existing unchanged
FruitJam CRLF/provenance workaround. Earlier simulator, sanitizer, build/layout
and RPC allocator evidence remains in the 2026-10-25 local reports; it is not
relabelled as physical evidence.

## Deliverables and remaining limits

Machine-readable results are under `evidence/2026-10-26/p4-storage-*.json`, with
the combined record `p4-storage-physical-summary.json`. Actual editor screenshots
were reviewed privately and are excluded from the public repository. Numerical
readback and cleanup evidence remain available without private artifact references.

Flash/SD filesystems, larger media archives and databases remain unavailable.
The earlier interrupted browser-download outcome is unresolved and was not
retried. Current raw file transfer bytes are physically verified; a completed
browser download is not claimed. Cable removal and power interruption were not
tested; reboot and explicit reconnect were.

Station request 284, HTTP/Wi-Fi acceptance and runtime testing of the isolated
protobuf pool remain separate blocked work. No permission for C6 operations,
network changes or publication is inferred from this RAM-flash authorization.
This acceptance preceded repository publication; the later release preserves
these validation boundaries. See [the release matrix](P4_RELEASE_2026_10_26.md).
