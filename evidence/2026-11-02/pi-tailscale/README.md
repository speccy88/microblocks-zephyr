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
