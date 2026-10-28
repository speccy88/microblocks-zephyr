# JavaScript editor across preserved targets

Extend the isolated migration with explicit packages for Fruit Jam, Waveshare
RLCD, Propeller 2, ESP32-P4, XRP RP2350 and the UNO Q reference, alongside the
existing Pi 5 and MicroDuck profiles. This is an editor/transport migration;
retain the independently pinned runtime and GP fallback. Keep SFC paused and
the P4 owner's checkout, board and COM5/COM12 untouched.

## Required behavior

- One catalog records each target's private primitive namespaces, exact library
  inputs, expected VM version/board prefix, USB filters and reset-line policy.
  These editor settings do not replace the hardware capability manifests.
- Include coherent dependency bundles, exact separate sources and provenance.
  Preserve the production XRP library rather than selecting its beta variant.
  Keep the existing 13 by 8 UNO Q matrix's104-character string representation.
- Use the real pinned parser, library picker, compiler and serializer. Compile
  all functions and native palette blocks; reject missing target functions and
  unknown primitive sets. No skipped operations may pass acceptance. Correct
  the authored Clock/Storage `while` loops to supported `repeatUntil` syntax;
  neither pinned upstream compiler implements a `while` selector.
- For enabled serial targets, use an explicit Web Serial chooser on HTTPS or
  loopback. Never open a device automatically, enumerate granted ports, install
  firmware or configure security. P2 keeps DTR false and its known v405 runtime.
  XRP retains native actuator locks; no fixture can establish motor readiness.
- Before any stop, code upload or project synchronization, verify the actual
  board's version response matches the selected profile. Ping/version requests
  alone are allowed before verification. A mismatch closes only that session.
- Cap USB input at128 KiB and queued output at32 KiB. Copy byte views, preserve
  message ordering and63-byte pacing, handle cancellation/partial open/cleanup,
  and bind queued writes to the original port and connection generation.
  A reconnect must discard stale receive bytes and cannot inherit an old upload.
- UNO Q remains an offline reference until its independent firmware identity is
  reconciled. MicroDuck remains an offline placeholder. Pi 5 stays independent
  of robot libraries. Board-network/WSS paths and P4 media/files/NN extensions
  require their own subsequent adapters and acceptance.

## Acceptance

Package all eight profiles while retaining every existing GP output byte and
every pinned upstream engine byte. Exercise actual library import, dependency
resolution, all-function compilation, native namespace/argument encoding and
canonical project round trips. Independently compare used P2 opcode numbers
with preserved native v405 dispatch. Exercise actual connection classes with
fragmented protocol replies, including rejection of a wrong board before the
editor's upload hook, plus bounded USB ownership/queue fixtures. Inspect the new
hub and representative target palettes graphically without opening hardware.
Run the unchanged full repository validator with verified native test inputs.

Fixture success is neither physical hardware acceptance nor a deployed website.
Keep source-only publication, P4 owner reconciliation, new graphical peripheral
views, board-network transport and physical acceptance as explicit remaining
gates. Do not resume the paused SFC implementation; importing its already
preserved ordinary library only checks compatibility.
