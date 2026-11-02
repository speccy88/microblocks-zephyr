# Complete Pi5 installer and GitHub bootstrap

The requested copy/paste entry point must be a real published file in
speccy88/microblocks-zephyr. Do not invent a native release: none is available.
Publish a readable bootstrap only after a tested payload commit exists; pin its
GitHub source archive and SHA-256. Build native VM417 from verified upstream and
port sources, and package the exact pinned JS editor with SFC/Python/GitHub UI.

Prerequisites: unprivileged Linux AArch64 Raspberry Pi 5 Model B, Python3.11+,
git, gcc, venv/ensurepip, adequate space and HTTPS access to GitHub, Codeberg,
PyPI. Explicit --install-prerequisites may install only documented build tools;
never upgrade the OS, enable I2C, change groups, firewall, router or trust.

Default prefix is derived from the current user's home. No Fred paths, keys or
credentials. Blinka10.1.0/gpiod2.5.0/websockets15.0.1 use an isolated versioned
environment with a complete version/hash lock for all sixteen runtime dependencies, official
PyPI artifact checks and dependency receipts.
Selection is atomic, repeat installs reuse verified environments, failed updates
keep previous selections. Imports/detection never construct I2C/GPIO objects.

Fresh installs create private data/Python state, SQLite enabled, sensor/HTTP/MQTT
extensions disabled. Existing profiles/data are preserved. Runtime supports
explicit direct local/LAN binding while current Caddy/proxy instances keep their
old behavior. Local-only is default; --lan is explicit unauthenticated HTTP/WS
on a private address and /24-or-narrower scope. Port is configurable 1024..65535.
Refuse occupied ports, privileged port80, unrelated prefixes or units before
mutating an installation. Never override an existing Caddy or port80 route.

Optional --service installs a dedicated ordinary-user system service via
explicit sudo action, no root runtime. Existing units require matching owner,
prefix and recorded identity. Stage/test build and dependencies before stopping
only the owned unit and selecting a new release. Retain old release/config and
program backup; restore on failed readiness. Default native update apply is
review-only unless explicitly commissioned. A same-source rerun is idempotent;
source upgrades require descendant project revision, never a silent downgrade.

Uninstall removes only owned launcher/service; retain programs, SQLite, versioned
code and environments. No recursive user-data deletion. Dependency-only setup
on Fred's Pi must not change current service/config/program/native binary.

Tests: clean isolated install/rerun/update/failure/uninstall with explicit fixture
builders/services; port80/occupied-port and unrelated prefix/unit preservation;
source/archive integrity errors; direct loopback/LAN Host/Origin behavior; actual
Pi Blinka imports/detection and source build/prepared install without activating
an extra listener/service. Physical sensors, fresh hardware OS and full reboot
remain separate acceptance. Verify actual bootstrap URL after commit/push before
offering an executable curl command.
