# Typed servo diagnostics and reference-model geometry

Pinned official protocol96b89d8613f06722c1d64ce75ab0d7124fed9d8f:
BusHealth.missing and ModelResult/FramesState/PoseState/SkeletonLink.
Source and editor/runtime pins are unchanged. No native primitive index changed.

Normal health now has29 selectors, adding missing-servo count and indexed u8
IDs with preserved order. Missing data stays not_reported; an explicit empty
vector gives count0. Empty lists have several documented causes and never prove
bus readiness. ID/type/range bounds are checked before I/O and after decoding.

Model capture uses the actual checked Unix RPC path: hello then robot.model{},
with no subscription or control call. Four shared pending/retained slots,
0.5s capture deadline,16KiB line bound, five-second TTL and explicit release
apply across health/state/model.18 typed model selectors expose reported asset,
reference trunk height, joint/head names/counts, ToF directions/FOV, zero-joint
frame poses and skeleton names/parents. Bounds:128 joints/links, four head
joints,64 beams. Scaled units mm/mdeg/ppm retain signed31 overflow semantics.
Absent geometry is not invented from serde defaults. Quaternion order is wxyz;
no FK, normalization, calibration or live-pose inference is performed. Skeleton
parents are index1/root0; omitted root defaults are marked ipc_default. The
upstream beta/head-IMU reference-mount caveat remains explicit.

23 advanced functions and two simple capture/read/release helpers were added.
Normal import:6 modules/169 functions; optional Starter Lab:10 modules/211
functions. Actual JS import, compilation and fresh source reopen pass. All211
compiled functions execute on the freshly rebuilt native VM with fictional
robot services. The simple model name was SIMULATION_STARTER, missing count2,
and the advanced model height123mm; retained snapshots were empty afterward.

Full unchanged validator: **540 tests passed**, no failures/skips,298.745s;
wrapper 307.630s. All2404 exact source inputs
matched original and replica after validation. Fresh native self-test/build
passed ASan/UBSan on local Linux x86-64. Native binary SHA256:
7ed25bbe2a486ea10909ac283b04b73960c53c875f17b52858b5bef5dbab7f0a.
Tests cover real local Unix transport, all18 model selectors/components,
servo ordering, absent/empty/default/overflow/forged values, closed requests,
shared capacity/expiry/release and coexisting library execution. Resource
limits and behavior assertions were retained; exact function-count fixtures
were updated for the additions. Evidence was added after the frozen run.

No new Pi, graphical MicroDuck or physical robot validation occurred. Fixture
socket traffic is real local IPC; its robot data is fictional. No movement,
secrets, BLE, network/security configuration, board access, push or deployment.
GP/main/live and paused SFC remain preserved. Reviewed mediad audio is unsupported.

Fresh Zephyr review is independent: the initial minimal source configuration
reached official SDK discovery and stopped on missing Zephyr SDK1.0. A project-
local official RISC-V SDK install is in progress; no firmware compilation or
hardware acceptance is claimed at this checkpoint. Exact owner-image inputs
include private media/model files excluded from the protected owner checkout.
