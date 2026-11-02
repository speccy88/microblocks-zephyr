# Configurable Pi tailnet HTTP access

The shared runtime now takes exact `origin`/`additional_origins` from an
installation's own configuration. The source installer has an explicit
loopback proxy mode and preserves that scope on subsequent source updates.
Native update/failed-boot recovery tests retain the same configuration. The Pi
browser package accepts its current same-origin tailnet IPv4 host without an
operator address in the shared code; non-Pi and Pages profiles stay restricted.

See [configuration and Caddy template](../../../docs/PI5_TAILSCALE.md) and
[the structured results](validation.json). The code was tested in an independent
checkout based on `f4d231f8d38a6477f544c64dea9c413398f53931`; exact candidate file
hashes are recorded in the JSON. Existing uncommitted P4 work in another Windows
checkout was not touched.

- Full validation on the actual Pi: **641 tests, 137 expected environment/asset
  exclusions, no failures**.
- Required Pi workflow suites: **70 tests, zero skips**. They cover origin checks,
  source/native updates, repeat install, rollback and preservation of config/data.
- Shared browser and freshly generated real Pi package: **13 tests, zero skips**.
- Canonical Python HTTP/WebSocket server: actual loopback socket tests for both
  configured public Host/Origin pairs and wrong-origin rejection. An isolated
  copy of the existing native ARM64 binary supplied a real `ready` marker from
  an empty private test VM; no VM commands were sent.
- Both existing public HTTP endpoints were rechecked from Windows: **200**,
  current assets, address-correct CSP, no redirect; each WebSocket returned
  **101**, `ready` and normal close. Incorrect/missing origins and cross-route
  requests returned **403**.
- Configurable Caddy example adapted successfully with example environment
  values. The running Caddy configuration was not reloaded.

The permanent bridge intentionally holds exclusive ownership of the live VM
transport. An initial passive attachment was refused by that guard; the
canonical test therefore used a separate VM and preserved that protection.
The live service PID, stored program and native binary hashes remained unchanged,
and MicroBlocks/Caddy/Tailscale stayed active throughout repository integration.

The public service retained its already authorized working hotfix during these
tests. This record establishes shared-source/package readiness and continued
live availability; it does not claim that the live service was redeployed from
this source revision, that a real VM release upgrade was applied, or that Safari,
an OS reboot, sensors, or Zephyr firmware were tested.

## Published bootstrap preparation

The bootstrap now selects source commit
`2b709975444f4e5d1c39ffcf65ac74eb4acc8a16` with independently downloaded archive
SHA256 `cac6ec12c3b55e847731de3c255bf50388bf2d370ac0a54fa74ee1cda571b5a6`.
That exact staged bootstrap completed a real fresh `--prepare-only` install on
the Pi with explicit example LAN/tailnet proxy origins and an unused backend
port in a separate private prefix. Pinned Python/Blinka installation, native
build/self-tests, editor packaging and release receipt checks passed. Its native
binary hash equals the existing live binary's hash.

Repeating it without any origin flags returned `already-current`, retaining
both stored origins and a fixture data marker. No system service was installed;
the existing service PID/program and Caddy/Tailscale stayed unchanged. See
[bootstrap results](bootstrap.json). This preparation does not claim a new boot
service or fresh-OS/reboot acceptance.

The prepared installation's own launcher was then started as an isolated
foreground process. Its managed Python/VM runtime became ready, served HTTP200
and WebSocket101/`ready` for both configured origins, and stopped cleanly after
the check. No VM commands were sent and the existing live service PID/program
remained unchanged. This checks the actual newly prepared application in
addition to the lower-level isolated transport test.
