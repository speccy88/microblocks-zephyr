# SmallVM Linux ARM64: object representation audit

This checkpoint does **not** implement or compile an ARM64 VM. It reproduces the
unmodified upstream memory guard on x86_64 Linux, measures the incompatible
layout, and tests the separate GP engine's offset-reference macros as a design
reference. No Pi, robot, bytecode, IDE upload or network connection is exercised.

## Pinned sources and observed obstacle

SmallVM v417, canonical commit
`2071df569623ba9cdcd6f8106b61796e047df38b`, is the existing repository pin.
The probe reads exact Git blobs and verifies the VM files against
`dependencies/smallvm-v417.json`; it does not depend on a mutable checkout or
download a newer VM.

| Upstream source | Relevant contract |
|---|---|
| [`vm/mem.h`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/vm/mem.h) | `OBJ` is `int *`; `FIELD` indexes `OBJ *`; headers and byte counts use 32-bit words. |
| [`vm/mem.c`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/vm/mem.c) | `memInit` panics unless `int`, `int *` and `float` are all four bytes. Allocation, resize, pointer reversal, forwarding and compaction assume four-byte words. |
| [`vm/interp.c`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/vm/interp.c) | Code/literal traversal and several byte-array operations use four-byte counts alongside object fields. |
| [`vm/persist.h`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/vm/persist.h) | Persistence records contain two 32-bit header words and word-counted data; bytecode uses its official format. |
| [`linux+pi/buildVMLinux.sh`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/linux+pi/buildVMLinux.sh) | Generic Linux build explicitly uses `gcc -m32`, SDL and i386 libraries. |
| [`linux+pi/buildVMRaspberryPi.sh`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/linux+pi/buildVMRaspberryPi.sh) | Historical Pi build links SDL and WiringPi; it does not establish Pi 5/ARM64 support. |

On the tested LP64 host, `sizeof(OBJ)` is eight bytes while `sizeof(*OBJ)` is
four. The address of `FIELD(obj, 0)` is eight bytes from the header; raw
`obj[HEADER_WORDS]` is four bytes from it. A wide native address also loses its
upper bits when narrowed into the collector's 32-bit forwarding word. These are
independent problems: removing `-m32`, disabling `memInit`'s guard, suppressing
pointer warnings or changing `OBJ` to a pointer-sized integer does not fix them.

The executable probe calls **the unchanged `memInit` from pinned `mem.c`**.
Its mocked output callback records the expected panic and exits the intentional
infinite panic loop with `longjmp`. It never proceeds into the incompatible
heap. A separate compile-time four-byte-OBJ assertion must also fail.

## A source-backed direction

The same upstream repository includes a distinct GP engine's
[`chromeApp/emscripten/mem.h`](https://codeberg.org/MicroBlocks/smallvm/src/commit/2071df569623ba9cdcd6f8106b61796e047df38b/chromeApp/emscripten/mem.h).
It documents a 32-bit `OBJ` offset and a native `ADDR` pointer, with `O2A` and
`A2O` conversion at the heap boundary on LP64. The reference probe verifies
offset/address round trips, four-byte field stride and a positive tagged
integer using those unchanged macros on a real allocated host buffer.

That header is **not a drop-in SmallVM port**. GP has different immediate
constants, type IDs, header layout (five words on this host) and object semantics.
Only the separation of compact references from native addresses is a useful
starting point. A SmallVM port must retain its own false/true tags, one-word
header, official 31-bit integer behavior, bytecode and persistence format.

A bounded 32-bit offset arena is the preferred direction to investigate next.
All object-field reads/writes, string/byte-array addresses, code pointers,
temporary roots, task stacks, GC pointer reversal/forwarding and resizing need
explicit checked conversion. Code backed by persistence can live outside the
heap, so references to code and embedded literals must be audited separately;
a single unchecked heap-base macro is insufficient. External hardware/native
pointers must never be truncated into a VM field. This design must not require
fixed low virtual addresses, disabled ASLR or executable heap memory.

Before a runtime change is accepted, exercise signed integer boundaries,
non-ASCII strings, byte lengths 0–9, nested/cyclic lists, garbage-collection
compaction with live roots in variables/task stacks, resize forwarding, code
literal access, save/restore and the official upload/start/stop/reconnect
protocol. Repeat under address/undefined-behavior sanitizers on an LP64 host,
then compile and execute natively on the real Pi. Those acceptance tests are
**not yet implemented or passed** by this layout probe.

## Reproduce this checkpoint

On LP64 Linux, with GCC and a local official Git clone containing the pin:

```sh
python3 tools/probe_smallvm_lp64.py \
  --upstream /path/to/smallvm \
  --output build-artifacts/lp64-probe
```

The JSON evidence records source hashes, compiler diagnostics and the exact
commands. Expected results are `EXPECTED_REJECTION` for SmallVM and
`PASS_REFERENCE_ONLY` for GP. This distinction is deliberate: neither result
means the Linux ARM64 VM works.
