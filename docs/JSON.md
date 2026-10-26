# Portable JSON library — local implementation contract

This library is separate from image, speech, network and board drivers. Existing
`p4:*` calls and the legacy tinyJSON functions keep their behavior and indices.
The first target is the native Zephyr P4 port; other ports must explicitly link
the same portable service before advertising support. JSONata is a separate,
unimplemented feature, not an alias for JSON Pointer.

## Behavior

JSON stays ordinary text in MicroBlocks variables. Each operation validates its
input and returns a new value; failed edits never alter the original text.
Operations: validate, compact, get a JSON value, get decoded string text, inspect
type/length, list object keys, set/create an object field, replace an array item,
append to an array, remove an existing value and quote text as a JSON string.
Empty object/array builders are ordinary `{}` and `[]` values.

Paths use RFC 6901 JSON Pointer: empty path means the whole document; `/sensor`
selects a field, `/readings/0` selects the first array item. Escape `/` as `~1`
and `~` as `~0`. Array indices are zero-based without leading zeros. Set does
not create missing parents. Append targets an existing array. Removing the
document root is rejected. Missing values and JSON null remain distinct.

The parser accepts RFC 8259 JSON with valid UTF-8 and paired Unicode escapes.
Comments, trailing commas, nonfinite numbers, duplicate decoded object keys,
trailing data and embedded raw NUL bytes are rejected. JSON strings containing
escaped NUL can be preserved as JSON; decoded text rejects NUL because the VM's
string operations use C-string conventions. Numbers stay their exact lexical
JSON form (including integers outside floating-point exact range); there is no
implicit conversion to an imprecise SmallVM integer/float.

## Bounds and ownership

Inputs/output at most 4096 UTF-8 bytes, pointer/text at most 1024 bytes,
128 values including object keys, nesting depth 16. All parser, edit and writer
allocations come from one caller-owned 96 KiB arena, with no system heap
fallback. The operation is synchronous and bounded; target latency must be
measured before declaring responsiveness proven. The adapter owns scratch
outside the VM heap and allocates the result only after native work finishes.
No native pointer or handle escapes, and no VM pointer is retained across GC.
Errors are explicit and do not include the user's JSON content.

yyjson 0.13.0, commit `6447536015f3d600f3d65323b10976103b337ca7`, is an MIT
dependency. Strict parsing and raw-number reading are used; permissive modes
are disabled. Source/hash/license metadata lives in `dependencies/json.json`.

## Plan and acceptance

1. Portable C service and independent library, with parser/allocator bounds.
2. Host tests: valid/invalid syntax, Unicode, exact numbers, duplicate keys,
   pointer escaping, CRUD, arrays, error atomicity, bounds and allocation failure.
3. Native VM adapter appended after existing primitive sets, compiler mapping
   and clear blocks/example/help; preserve all old primitive indices.
4. Offline ASan/UBSan, packaging/contract tests and native compile/layout checks.
5. Physical block execution/latency and graphical result screenshot require a
   later firmware installation. No physical PASS is inferred from a host test.

Local status: portable service, separate SmallVM primitive set, GP library and
sensor-data example are implemented. ASan/UBSan passes 62 boundary/behavior
cases, 10,000 malformed inputs and workspace-exhaustion checks. Both native
USB and station profiles compile, preserving camera/audio/Whistle/KWS/NN code;
the complete application/model/assets/settings layout passes. This is compile
evidence, not a new physical regression run. Existing `p4:*` primitive indices
remain unchanged; `json` is appended at index 22.

The actual GP editor imports the library/example; its 1280x720 render was checked
after correcting long palette defaults and overlapping example scripts. It was
disconnected during this check. Native JSON execution, VM GC stress and latency
are **not yet tested on the P4**. The later approved RAM acceptance installed
an image containing this library, but did not execute its separate JSON suite.
See [the release validation matrix](P4_RELEASE_2026_10_26.md).

Host reproduction on Linux/WSL with GCC and Python 3:

```sh
python3 tools/test_json_service.py
python3 tools/validate.py
```

The host report is generated under `build-artifacts/json/report.json`.
On this Windows checkout, the root validation uses unchanged canonical HEAD
bytes to avoid the recorded pre-existing CRLF/provenance hash issue; it does not
rewrite unrelated files. The current canonical validation passes 47 tests.
For firmware, use the pinned workspace/profile commands in the P4
[START_HERE](../boards/waveshare_esp32p4_wifi6/START_HERE.md); JSON is linked by
the P4 CMake target in both USB and station builds. The dependency is vendored
and hash-pinned, so configuring JSON needs no network download.

Evidence: [host](../evidence/2026-10-25/p4-json-host.json),
[builds/layout](../evidence/2026-10-25/p4-json-builds.json),
[editor](../evidence/2026-10-25/p4-json-editor.json).
The 96 KiB arena plus 4097-byte output buffer are reserved outside the VM heap
(PSRAM on this P4 profile); this is reserved capacity, not measured peak usage.
The next separate stage is [JSONata feasibility](JSONATA.md).

References: [RFC 8259](https://www.rfc-editor.org/info/rfc8259/),
[RFC 6901](https://www.rfc-editor.org/info/rfc6901/),
[yyjson](https://github.com/ibireme/yyjson/tree/6447536015f3d600f3d65323b10976103b337ca7).
