# Pi HTTP and HTTPS editor through Tailscale/Caddy

## HTTPS/WSS extension contract

An administrator may explicitly add a canonical `https://machine.tailnet.ts.net`
origin on port 443 to the same loopback proxy configuration. The name must have
two valid lowercase DNS labels before `.ts.net`; no wildcard, credentials,
explicit port, trailing dot, path, query or fragment is accepted. The backend
must keep exact Host/Origin matching, loopback-only peers and per-origin CSP.
The Pi browser and updater choose WSS for the current HTTPS origin; HTTP/WS LAN
and numeric tailnet access continue to work. Other targets and Pages do not
gain an HTTPS programming path.

Caddy terminates TLS and obtains its certificate from the local Tailscale
daemon using the documented `TS_PERMIT_CERT_UID=caddy` permission. Applying that
permission, issuing a public certificate, adding the HTTPS proxy route and
restarting services require explicit administrator authorization. The installer
does not perform those privileged actions automatically. The public name may
enter Certificate Transparency logs; the website remains restricted to tailnet
clients. Rollback must restore config/code and preserve the program, binary,
Python profile and existing HTTP routes.

Acceptance requires normal certificate validation and hostname matching,
HTTPS200, WSS101/ready, correct WSS CSP, rejected wrong/missing/cross origins,
and successful existing HTTP/WS endpoints. Real iPhone acceptance is separate.

## Configure an HTTPS site

Retain the LAN/numeric origins and add your own exact Tailscale HTTPS name:

```sh
--proxy-origin http://192.168.2.50 \
--additional-origin http://100.100.10.20 \
--additional-origin https://pi.tail-example.ts.net
```

For an existing deployment the equivalent configuration retains its full service
settings and includes both additions in `additional_origins`. The loopback
backend remains plain HTTP, while Caddy handles the HTTPS connection. The
package's `encryption: false` describes the embedded listener, not the external
TLS connection. No operator name or address is compiled into the package.

After reviewing the exact administrator action, use Tailscale's documented
non-root Caddy integration: add `TS_PERMIT_CERT_UID=caddy` to
`/etc/default/tailscaled`, preserving its other settings, then restart
`tailscaled`. Keep Caddy running under its existing non-root account; changing
the socket mode or granting general Tailscale administration is unnecessary.
See [the official certificate integration](https://tailscale.com/docs/integrations/web-servers/caddy/caddy-certificates).

Add the reviewed block in
[Caddyfile.tailscale-https.example](../linux/arm64/Caddyfile.tailscale-https.example)
to the existing configuration. Set `MICROBLOCKS_HTTPS_ORIGIN` to the HTTPS name
and `MICROBLOCKS_PROXY_BACKEND` to its existing loopback backend. Its source
filter covers Tailscale IPv4 and IPv6, and other Caddy sites/HTTP routes stay in
place. The `.ts.net` name uses Tailscale's public certificate integration, not
an internal self-signed CA. Issuance can publish the node name in public
Certificate Transparency logs. No router or public port-forward change is
needed for this tailnet-only site.

Stage the runtime, browser and updater modules together and update their package
receipts. Back up configuration/program first and check for an active editor.
After the authorized restart/reload, verify normal certificate trust, HTTPS200,
WSS101/ready for VM and updater, correct per-origin WSS CSP, and the retained
LAN/numeric HTTP endpoints. Reject wrong/missing/cross origins and non-tailnet
sources. Preserve the VM binary, program and Python profile. Rollback restores
the prior files and certificate grant; an already issued certificate cannot be
removed from public transparency logs.

## Contract and acceptance criteria

The default installation remains loopback-only. Direct LAN mode keeps its
existing exact address, client subnet and unprivileged port. An optional proxy
mode keeps the backend on `127.0.0.1` and accepts only explicitly configured
canonical IPv4 HTTP origins on port 80, or explicitly configured Tailscale-name
HTTPS origins on port 443. HTTP IPv4 origins may use RFC1918 or Tailscale's
`100.64.0.0/10` range. No wildcard, HTTPS downgrade or forwarded-header trust is
added. Each browser Origin must match the request Host, and a WebSocket
requires that exact Origin. The proxy controls client source addresses.

An installation's `origin` and `additional_origins` survive source upgrades,
native VM updates and failed-update recovery. Packaged Pi browser code supports
the currently opened same-origin Tailscale IPv4 site without embedding an
operator's address. Other board packages and Pages remain unchanged.

Required checks: preserve the LAN route; reject unconfigured, duplicate and
mismatched Host/Origin headers and direct non-loopback backend access; generate
the correct CSP and WebSocket origins; package a Pi editor that connects only
to its current host; preserve configuration and program data across successful
updates and rollback. Real Pi acceptance must use both LAN and Tailscale HTTP
and WebSocket, without sending program commands or replacing its VM/program.

This feature does not install Tailscale, change its ACLs, expose a router port,
configure a firewall, grant certificate access, or overwrite an existing
Caddyfile. An administrator configures HTTPS/WSS separately as described below.
Physical Safari/iPhone and full OS reboot remain separate
acceptance tests.

## Configure an installation

Use your own LAN and Tailscale IPv4 addresses. The following values are examples,
not defaults and not address discovery. Confirm the Pi is online in Tailscale and
that you can reach its Tailscale address before changing the application.

The source installer accepts these options after the checksum-pinned bootstrap
has selected a revision containing this feature (`--bootstrap-info` shows its
selected source identity):

```sh
sudo -v
curl -fsSL https://raw.githubusercontent.com/speccy88/microblocks-zephyr/main/scripts/install-pi5.sh | \
  bash -s -- --service \
    --proxy-origin http://192.168.2.50 \
    --additional-origin http://100.100.10.20
```

This prepares the owned backend on `127.0.0.1:8877`. It does not modify Caddy or
bind the application directly to Tailscale. `--port` can select another free
unprivileged backend port. `--proxy-origin` is mutually exclusive with direct
`--lan`, `--bind` and `--clients` options. An occupied or unrelated listener is
preserved. An existing legacy `microblocks-lan` prefix is still not automatically
adopted by the newer source installer.

For an existing proxy deployment, retain these settings in its private
`service.json` while deploying the shared `lan_service.py`/`lan_editor.py` and a
new `package_pi_lan_editor.py` editor package:

```json
{
  "origin": "http://192.168.2.50",
  "additional_origins": ["http://100.100.10.20"],
  "backend_port": 8877
}
```

This is an endpoint fragment, not a replacement for the full service config:
retain its VM, editor, data and Python selections. Omit `direct_bind`/`clients`
in proxy mode. Up to four additional unique origins are allowed. Leaving out
`additional_origins` permits only the primary origin. A package update must
deploy both canonical runtime modules and the freshly packaged browser assets;
do not reintroduce a deployed one-off browser copy.

For owned source-installer updates, omitting the endpoint options preserves the
stored origin list. Repeating `--additional-origin` explicitly replaces the
entire additional list; `--clear-additional-origins` removes it while preserving
the primary origin. Those changes restart only the owned service after staging
and backup. The native VM updater retains the endpoint config on success and
restores it with the program on failed-boot recovery. No native update repackages
or replaces the browser/runtime source files.

## Existing Caddy configuration

Review [Caddyfile.tailscale.example](../linux/arm64/Caddyfile.tailscale.example).
It adds separate LAN and tailnet routes, with the backend still in loopback.
Populate these values in Caddy's own service environment, or substitute the
reviewed literal values before adding the blocks to the existing Caddyfile:

```text
MICROBLOCKS_LAN_ORIGIN=http://192.168.2.50
MICROBLOCKS_LAN_CLIENTS=192.168.2.0/24
MICROBLOCKS_TAILSCALE_ORIGIN=http://100.100.10.20
MICROBLOCKS_PROXY_BACKEND=127.0.0.1:8877
```

The explicit `http://` origins avoid Caddy's automatic HTTPS redirect. Keep the
LAN source filter on the LAN route and the `100.64.0.0/10` source filter on the
tailnet route. Host and Origin must be forwarded unchanged. Never rewrite an
arbitrary browser Origin to an allowed one. Validate the entire resulting
Caddyfile and reload the existing service only after reviewing and authorizing
the exact change. This installer does not perform that administrator action.

## Verification and recovery

Use a normal HTTP **GET**, not HEAD: the Python WebSocket server only supports
GET. Check both public addresses for 200, no HTTPS redirect, the same-address
WebSocket URL in CSP, and current browser resources. Open `/ws/vm` with the exact
browser Origin, expect HTTP101 then `ready`, and close without program commands.
Incorrect/missing Origin, unconfigured Host and cross-origin Host/Origin pairs
must fail. Confirm the backend still listens only on `127.0.0.1` and the stored
program hash is unchanged.

Before changing a running deployment, preserve the config, runtime, package
receipts and program, compare reviewed hashes to detect concurrent changes, and
check that an editor is not connected. Retain the previous code/package and
service selection for rollback. The source installer already stages and backs
up its owned installation; it refuses unknown prefixes and modified releases.

If a browser cached an earlier HTTPS redirect, open the explicit HTTP URL in a
fresh private window. A separate HTTPS certificate failure is not evidence of
a Tailscale transport failure. This feature does not configure HTTPS/WSS or
claim physical Safari/iPhone acceptance.
