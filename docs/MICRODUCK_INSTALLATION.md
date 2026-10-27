# MicroDuck Installation

The physical robot is expected around Christmas 2026. This is a commissioning
procedure awaiting the shipping image; the Pi is a stand-in, not compatibility
proof. Use the [arrival checklist](MICRODUCK_CHRISTMAS_HARDWARE_VALIDATION_CHECKLIST.md)
to record evidence and blockers before enabling physical actions.

1. Inventory the shipping OS/architecture/glibc, API version, free storage,
   existing services, service sockets and trusted numeric UIDs. Compare the
   pinned API-44 schemas with the shipping revision. Preserve robot services.
   The optional [filesystem-only preflight](../linux/microduck/PREFLIGHT.md)
   helps inspect local metadata without contacting a daemon. Its expected API
   and configured/file UIDs are not observed protocol or peer identity. It
   returns INCOMPLETE or BLOCKED, never robot-ready or mutation authorization.
2. Discover the robot in the portal from a supported secure-context browser.
   Current real BLE support is discovery/version only. Configure Wi-Fi from a
   trusted robot console until confidentiality is established; do not enter real
   credentials into the simulation or send them over unverified BLE.
3. Establish the robot's IP and verify its SSH host identity through a trusted
   channel. Use ordinary secure authentication; the Pi's SSH key does not grant
   access to another device. Never disable host verification to proceed.
4. After a reviewed ARM64 release exists, use its immutable version, installer
   and independently verified SHA-256. Run the installer as the intended local
   user. Until publication, only a manually reviewed local candidate is available
   and the website's install-copy control remains disabled.
5. Run the VM self-test and read-only core/IDE acceptance in a private data
   directory. Begin with the self-hosted loopback editor and a verified SSH
   tunnel; use trusted WSS only when that endpoint is commissioned.
6. Configure a private gateway file with actual authoritative daemon socket
   paths and verified numeric UIDs; start the gateway read-only. Supply its
   private socket explicitly with `--microduck-socket`. Verify `capabilities`,
   health and absent/optional data before any action.
7. Validate a specific supported sound/skill with a present operator and the
   robot's normal safety procedure. Enable only its concrete gateway method and
   confirm each invocation. Respect unknown outcomes; no automatic retries.
8. Separately test service startup and OS reboot when authorized. Foreground
   execution and process-persistence tests do not establish reboot readiness.

The [gateway guide](../linux/microduck/README.md) gives exact configuration,
ownership and command schemas; placeholders in examples require real inventory.
Socket or daemon refusals are commissioning blockers, not permission to change
UIDs/groups/service security. No locomotion controller replacement, raw joint
control, firmware update or security change is needed for initial read-only
SmallVM acceptance.
