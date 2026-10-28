# Read-only servo diagnostics and model geometry

Use pinned official API44 commit96b89d8613f06722c1d64ce75ab0d7124fed9d8f,
duck-ipc-proto/src/lib.rs BusHealth, ModelResult, FramesState, PoseState and
SkeletonLink. Preserve the source pin and all21 native primitive indices.

Add missing-servo count and indexed u8 IDs to immutable health captures.
Preserve reported order, reject invalid types/overflow and bound256 entries.
Absent missing-list data remains not_reported; explicit empty lists give count0.
Neither empty nor absent proves bus readiness: the source documents multiple
reasons for an empty vector. Provide a simple capture/read/release count helper.

Extend normal robot captures with kind model: checked finite hello then exactly
robot.model{}, never a subscription or mutation. Keep16KiB lines,0.5s deadline,
four shared pending/retained slots, five-second TTL, explicit release and no
automatic retries. Model reads are scalar only: asset, trunk reference height,
joint/head names and counts, ToF beam components/FOV, reference frame poses,
and skeleton names/parents. Bound128 joints/links, four head joints and64 beams.
Preserve missing sections/keys; do not synthesize geometry from serde defaults.
Return scaled mm/mdeg/ppm with explicit signed31 overflow. Report source
quaternion wxyz; do not normalize, calibrate, apply FK or match captures by tick.
Parent indices exposed to blocks are one-based, root0; omitted parent has the
documented None/root default and is marked ipc_default. Validate parent bounds.
Keep the beta/head-IMU reference-mount caveat explicit.

Expose named advanced blocks and simple model-name helper in the same optional
Starter import. Both layers use the same captures and typed records. Validate
actual JSONRPC Unix transport with a faithful local robotd fixture, compiler,
native sanitized VM, malformed/absent/overflow/default/expiry/capacity behavior
and project roundtrip. Never call physical movement or claim hardware tests.
Mediad audio remains unsupported in the reviewed interface.

Review a fresh P4 Zephyr build in an independent SDK/workspace with exact source
and toolchain provenance; do not modify original SDK, protected owner checkout,
existing board/services, GP/main/live or paused SFC. Report not compiled if an
exact isolated build cannot be completed; host C tests are separate evidence.
