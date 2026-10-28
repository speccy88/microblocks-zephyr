# Fresh isolated P4 build and optional SD diagnostic fix

The requested model/servo checkpoint9c60ae6 is retained. A fresh minimal P4
camera/audio/SD cross-build then exposed an undefined
z_impl_k_thread_stack_space_get reference. Pinned Zephyr kernel/thread.c:1180
compiles that implementation only with both CONFIG_INIT_STACKS and
CONFIG_THREAD_STACK_INFO. The worker now uses the same guard, reporting
stack_unused0 and stack_error=-ENOTSUP when unavailable. Existing diagnostic
profiles retain their measurements. Worker cancellation, ownership and file
semantics are unchanged. The owner-source baseline remains in
dependencies/p4-native-owner.json with an explicit post-reconciliation delta.

**Final full validator:541 tests passed**, zero failures/skips,336.188s;
wrapper 344.218s. All2412 exact inputs
matched working tree and Linux replica afterward. The new regression links and
runs the actual worker with both prerequisites, neither, init-only and info-only
under ASan/UBSan, retaining25 lifecycle runs per variant; the four file-worker
runs and balanced allocation/release assertions also pass. The unchanged
sanitized local Linux MicroDuck VM7ed25bbe is source-hash verified before reuse.
The actual211-function starter execution and all model/servo tests still pass.

**Fresh isolated cross-build passed**, including VM memory placement.
Target esp32p4_wifi6/esp32p4/hpcore; pinned Zephyr
a915b2f12675b48b16d56653ea145dcd8f20cbbf with the complete12 reviewed patches
applied only to a new temporary clone. Existing modules were read through
workspace links; original SDK source was not patched. HAL Espressif pin is
b16851b3c20e6fad3d2da42ec24a3e82d0b8b444. The SDK was initially missing; official
Zephyr SDK1.0.0 GNU RISC-V toolchain was installed inside this project's ignored
build-artifacts directory. GCC14.3.0 is recorded. Existing esptool5.6.0 required
only a process PATH correction; no original venv package change was needed.

The exact west configuration and cmake --build commands are in final-receipt.json.
Environment adds ZEPHYR_SDK_INSTALL_DIR to the project-local install and prefixes
/home/fred/microblocks-zephyr-work/.venv/bin on this process's PATH.
Use profiles/sd-files.conf and profiles/sd-readonly.overlay over prj.conf;
SmallVM417 raw sources were exported/hash-verified from the existing official
cache and prepared by the normal build script. Source identity is9c60ae6 plus
the exact SD guard delta in validation-inputs.json. No source changed during
the frozen tests/build. The final documentation/evidence was added afterward.

Build elapsed 219.129s. Image zephyr.bin440160B SHA256
b66e6b0eee0214608bd4b03efd5dfc119869d347eb212ba696013a1f7baec6c0.
ELF5229188B SHA256
6f0158ea3f4793d2aa00490005247bda51ab3755689d574a809f9820199e3657.
Memory validator:5240 VM task bytes at0x48010000 in external RAM;16KiB main
stack at0x4ff5ac00 internal. Link usage:163680B SRAM,17188256B external DRAM.
The ELF/bin remain ignored build artifacts and are excluded from this evidence
archive. This raw build image is not a release, flash instruction or boot test.

This scope omits station/network/hosted assets, neural, Whistle and KWS/private
media inputs. It does not rebuild the owner's full installed image; those
private inputs remain excluded from the protected checkout. No board flash,
serial session, service/network/security setting, GP/main/live or paused-SFC
change occurred. No new Pi or physical MicroDuck validation was performed.
Mediad audio remains unsupported in the reviewed interface; live robot control,
continuous stream commissioning, calibrated geometry and graphical/physical
acceptance remain separate. No push or deployment was performed.
