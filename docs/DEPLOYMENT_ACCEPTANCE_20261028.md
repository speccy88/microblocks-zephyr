# Deployment readiness and remaining physical acceptance

This checkpoint changes no live site, main, GP, SFC, owner P4 firmware, COM port,
security configuration or physical robot state. Fred separately authorized one
Pi reboot after private saved-program backups; that reboot was completed and
its foreground-session disruption is recorded below. Local code is on the isolated
JavaScript migration branch; it is not a published release.

| Component | Verified evidence | Remaining gate |
|---|---|---|
| Raspberry Pi 5 standalone | Actual interpreter, JS graphical arithmetic 42, serialization/reopen/readback/reconnect; hardened user-service lifecycle; authorized full OS reboot, VM automatic startup at 8.65 s, saved code 42/CRC and graphical readback. All three pre-existing saved files preserved; their foreground VMs ended at reboot. | Bridge requires manual foreground restart; Windows SSH agent after Windows reboot; clean-machine package/source reproduction; release publication. The initial transition from a raw protocol fixture to graphical evaluation produced an error resolved by explicit reconnect; preserve/investigate it as a regression gate. Test service removed. |
| P4 full-profile source build | Full-profile compile and four ELF/layout guards; immutable model permutation tables save 4 KiB internal SRAM without reducing stacks/pools. Original C loader and synthetic encoder match. | Revision guard, board-owner coordination, recovery/image identity, boot and all concurrent runtime memory measurements. Never flashed by this checkpoint. Different SDK/assets and omitted private recording prevent exact owner-image equivalence. |
| P4 runtime memory | Linker map inventories code, stacks, heaps, pools and static globals; Whistle 64 KiB stack retained based on earlier measured high water. | Measure each thread high water, stack guards, libc/system/RPC/PSRAM allocator current/peak/largest-free, fragmentation and allocation failures during camera+audio+inference+SD+network contention. Recheck cancellation, timeout, rapid reconnect and recovery. Static build success cannot establish safety. |
| P4 JS media/files/inference/network | Typed libraries, compiler and fixture readback/inline rendering tests; earlier owner's hardware evidence is retained separately. | Broader graphical USB/WSS readback and physical camera/PCM/Whistle/KWS/SD/network integration against the agreed installed image. No assumption that fixture output proves hardware. |
| MicroDuck RK3566 placeholder | Six ordinary libraries plus optional Starter Lab; simple and advanced blocks coexist. Typed robotd/tofd/padd/model/servo service fixtures execute on real Pi. | Physical robot unavailable: inspect shipping revision, real UIDs/socket identities and protocol compatibility before commissioning. All robot data in these tests are fictional. No movement authorized by a health result. |
| MicroDuck control and media | Source-reviewed methods, bounds, confirmation and unknown-outcome handling; receive-only camera fixture and simulated relay diagnostics. | Trusted shipping identities/confidential commissioning, real daemon transport, camera timing and physical control/safety acceptance. Mediad audio remains unsupported where no reviewed API exists. Do not send PIN/PSK via insecure BLE. |
| Other JS targets and custom widgets | Eight generated profiles, pinned upstream source unchanged, matrix serialized-data and compiler/readback fixtures. | Target-specific graphical/hardware acceptance. Preserve GP fallback; paused SFC is outside this checkpoint. |
| Website and release | Existing live site and local eight-profile preview remain available at their previous states. | Coordinate P4/GP integration, review exact committed payload, hosted CI on that revision, then approved publication and live URL/download/hash verification. This checkpoint performs no push or deployment. |

For a coordinated physical P4 test, record the exact revision-guarded image,
silicon/board revision, model/assets hashes and recovery procedure first. Run
bounded single-feature smoke tests, then concurrent worst cases and cancellation,
logging allocation failures and stack high-water marks. Keep evidence from the
new image distinct from historical owner results. The additional4 KiB libc arena
is useful margin, not a sufficient release criterion.

See [P4 memory evidence](../evidence/2026-10-28/p4-sram-service/README.md),
[Pi service evidence](../evidence/2026-10-28/pi-user-service/README.md),
[MicroDuck capability matrix](MICRODUCK_SERVICE_CAPABILITIES.md) and
[remaining objectives](MICRODUCK_REMAINING_OBJECTIVES.md).
