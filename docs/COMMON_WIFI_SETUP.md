# Shared USB Wi-Fi setup and storage contract

This is staged implementation work, not an installed firmware capability.
The current Fruit Jam uses FJNW version 1 without RP2350 credential persistence;
the current Waveshare standalone VM uses WebSocket, not a binary USB VM stream.
Neither installed image implements the common MBNW version 2 path described here.
No credentials are transmitted or retained by the tests in this document.

## Wire format and authorization

SmallVM long message 205 carries an MBNW request, followed by the VM frame's
existing terminator (the terminator is not part of this decoder's input).
The request starts with four ASCII bytes `MBNW`, version byte 2, operation byte
and a nonzero 32-bit little-endian request ID. Operations 1 (probe) and 3
(status) are exactly ten bytes and never join a network or write settings.
Operation 2 (connect) adds one flags byte, SSID length, key length and those
exact byte strings. Only flag bit 0 is defined: explicit remember-on-board.
SSID is 1..32 non-NUL bytes. The key is 8..63 non-NUL bytes, or 64 ASCII hex
digits. Maximum request size is 109 bytes. Unknown flags/versions/operations,
truncation, trailing bytes and zero request IDs are rejected.

The transport owner must be the local USB controller for every setup request.
A WebSocket controller must never submit credentials. Remember requests are
rejected unless that board actually supports the separate settings backend.
Parsing provides borrowed views only; a worker must copy accepted credentials
into bounded private storage before the VM input buffer is wiped. Replies
contain identity/capabilities/state/IP/error and the request ID, never the key.
The portal must match board identity and capabilities before offering remember.

## Portable storage component

An abstract read/erase/write interface addresses two logical slots, not raw
board addresses. Board integration must map these to separate erase pages in
a dedicated settings partition, with build-time overlap checks against the
application, program store and existing settings. No backend or partition is
selected by this portable component.

The board worker must serialize load/save operations and implement the flash
device's actual alignment/programming constraints in its backend. The journal
must not be mapped over an existing NVS store or filesystem to add persistence.

Each 116-byte record contains magic/version, lengths, a generation, zero-padded
SSID/key fields, CRC32 and a separately written four-byte commit marker. Save
erases only the inactive slot, writes data and CRC, then the commit marker, and
verifies the record. The previous valid slot is retained. Load validates exact
format, credentials and CRC before choosing the newest generation, including
wraparound. A read error aborts saving; an unreadable active slot must not be
overwritten. Intermediate buffers and rejected outputs are wiped. There is no
heap allocation, diagnostic credential output or implicit network action.

This format stores credentials in plaintext flash. CRC detects corruption;
it is not encryption or authentication. Interrupted-write fixtures model the
interface in RAM and do not prove real flash power-loss behavior.

## Acceptance and integration boundary

1. Compile and execute the actual portable C decoder/store with bounded tests:
   malformed frames, local-owner policy, capability checks, all partial record
   writes, corrupt records, failed I/O, generation wrap and buffer clearing.
   Fixtures use synthetic public strings and no network/device access.
2. Integrate each board's worker, exact reply schema and settings partition;
   advertise persistence only after its backend is actually implemented.
3. Add Waveshare USB ownership alongside the existing WebSocket path, keeping
   Wi-Fi startup off the VM thread so offline USB configuration remains usable.
4. Cross-build both full images from recorded source, audit partition bounds,
   and preserve each current image, program and settings before any installation.
5. Perform target-verified physical tests and explicit user credential entry/
   remember action. Preserve current Fruit Jam program CRC `651a01da`; the old
   `297d191b` snapshot is not the current program and must not be restored.

Stages 2..5 remain pending. The portable component does not provide a finished
setup flow, automatic full-power recovery, mDNS, TLS or new coprocessor firmware.

The actual C component passes 7,319 checks in wasm32/Node WASI, including 117
interrupted-write positions and 928 single-bit corruptions of the newer slot.
The exact compiler command and source hashes are recorded in
`evidence/common-network-setup-wasi-2026-10-19.json`. CI also compiles/runs the
same fixture natively with `python3 tools/test_network_setup.py --native-compiler cc`.
Neither result substitutes for a real flash/board/power-loss test.
