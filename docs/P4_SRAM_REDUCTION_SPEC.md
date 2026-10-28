# P4 SRAM review: retain stacks, freeze pinned permutations

The full-profile link reserves 382,880 of 393,216 internal SRAM bytes, leaving
10,336 bytes for libc. This includes executable IRAM, initialized data, BSS,
network/DMA pools and native stacks. It is not a runtime free-heap measurement.
The 64 KiB Whistle stack must remain: existing physical evidence measured
43,964 bytes used and records corruption with the former 24 KiB allocation.

Two 512-element mutable int32 Whistle permutation arrays account for 4,096
internal bytes. They are initialized solely from the pinned flash-resident model
and subsequently read by the CPU inference worker, never DMA or an ISR. Generate
identical const tables from that exact hash-checked model during preparation,
retain the pinned upstream source unchanged, and patch only a generated copy.
Keep a runtime equality check against the model so an incompatible model fails
before inference. Do not alter stacks, network limits, heap reservations, model
weights, inference arithmetic or cancellation/deadline handling.

Acceptance: a bounded CACT v4 reader rejects malformed metadata/noninteger or
out-of-range values; an independent C oracle using the original loader produces
identical tables and deterministic synthetic encoder output; the adapted loader
rejects mismatched permutation data. The full P4 image must cross-build with all
existing guards, place both const tables in flash and reduce internal allocation
by at least 4,096 bytes. Source pins and preparation hashes must remain auditable.

No flashing, microphone capture, recorded audio, live-site update or physical
runtime claim follows. Physical worst-case inference/cancellation/concurrency,
stack high-water marks and allocator margins remain release gates.
