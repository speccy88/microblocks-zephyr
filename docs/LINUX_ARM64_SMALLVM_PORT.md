# Linux ARM64 SmallVM Port

This headless Linux port keeps the official SmallVM v417 bytecode and four-byte
object/code format. Source is pinned to
`2071df569623ba9cdcd6f8106b61796e047df38b`; MPL-2.0 sources and the exact MIT yyjson
dependency notices accompany a candidate. It is separate from the Zephyr targets.

On LP64, native pointers do not fit the original four-byte object fields. The
port uses checked 32-bit offsets into one native arena, retaining signed31
integers. Native pointers exist only at explicit boundaries. Moving compaction,
all roots, persistence, code pointers and typed primitive callbacks are adapted
together. It neither removes `-m32` blindly nor depends on low virtual addresses.
The [LP64 audit](SMALLVM_LP64_AUDIT.md) and [native contract](../linux/arm64/SPEC.md)
give the details.

```sh
python3 linux/arm64/build.py --upstream /path/to/pinned-smallvm-git --output build-artifacts/native --test
# Add --sanitize for an instrumented development binary.
build-artifacts/native/smallvm --data-dir /absolute/private/programs
```

On Windows, `--source-only` stages verified sources for a native Linux builder.
Source files read from the exact upstream Git commit are hash checked before
guarded transformations. The baseline ARMv8-A ordinary build links libc and uses
glibc symbols requiring 2.34 or newer; only the Pi's glibc 2.41 has been exercised.

The VM owns one mode-0700 program directory, an exclusive lock, atomic durable
program storage and a private PTY discovery file. It listens on no network port.
Optional MicroDuck jobs are polled around bounded VM slices and retain their
buffers outside the moving heap. Unsupported board hardware is explicit; GPIO,
display, camera and Zephyr peripherals are not supplied by this port.

Native memory fixtures passed 82,307 checks and the MicroDuck adapter passed 380
ASan/UBSan checks. Real Pi builds execute actual bytecode and the official IDE
protocol. Local Linux tests and synthetic fixtures are described separately in
the [evidence indexes](PI5_MICRODUCK_STATUS.md).

The [candidate tool](../tools/prepare_linux_arm64_release.py) binds a tested
ordinary binary to its native report, immutable port commit, exact prepared
source manifest and deterministic self-contained source archive. It records
any exact LF-to-CRLF checkout conversion rather than modifying tested bytes.
Neither packaging nor compilation publishes or constitutes runtime acceptance.
