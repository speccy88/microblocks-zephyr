# Generic Python extensions: Pi 5 acceptance, 2026-11-02

The actual JavaScript compiler, native SmallVM and Python/SQLite ran on the
physical Raspberry Pi 5 through a private SSH-forwarded acceptance session.
The normal Start control created/read persistent rows. A mouse/keyboard edit
changed a normal list input from 21500 to 22600; 22600 then returned from SQL.
An independent MicroBlocks heartbeat advanced during requests. Editing the SQL
to reference a missing table produced the real actionable SQLite message and
stopped that script. User scripts contain normal domain blocks and lists, with
no JSON, jobs or process startup. See [browser.json](browser.json),
[actual blocks](pi-sqlite-blocks.png) and [actual error](sql-error-message.png).

The browser ran on Windows using Chromium 156.0.8078.74, through an exact-port
loopback SSH forward to the Pi. This is physical Pi evidence, **not** a physical
iPhone/Safari test. The Pi's active port-80 installation and user program data
were left unchanged. Candidate work lives below a newly allocated private
`/home/fred/mb-python-udufkoyi` directory, separate from the managed installation.

Upstream VM source remains `2071df569623ba9cdcd6f8106b61796e047df38b` (v417).
Upstream JS engine remains `5564b1e42d6790360450ebf11c9eb33a1c6877f2`; engine
bytes were hash-checked and unchanged. The native Pi build uses GCC 14.2.0,
ARMv8-A, Python 3.13.5, Linux 6.12.75+rpt-rpi-2712, glibc 2.41.

- Sanitized Pi binary SHA-256:
  `a43475ad95a74c6941606110b78e577d482077cc1297eb4a5c3a5273e15ad682`.
  Real bytecode/domain blocks, workers, local HTTP and graphical acceptance ran
  against this private candidate. No sanitizer diagnostic was observed.
- Ordinary Pi binary SHA-256:
  `d60102ce79a73f79ee63d094e79c0803e64fdfb8cb4949a688639e9e89d09a2b`.
  Compiled on the Pi from 55 verified prepared source entries. Self-test passed.
  All 22 selected tests passed: workers/SQLite (9), actual compiled VM (4),
  local HTTP (2), explicit MQTT API fixtures (3), managed lifecycle (4).
  See [ordinary acceptance](pi-ordinary-acceptance.json) and retained logs.
- Sanitized x86-64 WSL build and the same real-VM suite passed, including a
  forced moving collection during nested-list conversion. All 18 existing
  native MicroDuck regression tests passed with the extended transport.
- Shared final Pi mobile package passed six Chromium phone emulations, portrait
  and landscape, 375x667 through 932x430: menus, insertion, interruption,
  panning, anchored pinch and 50–250% zoom coordinate checks.
  See [mobile-touch.json](mobile-touch.json). No page error was observed.

HTTP tests use the Pi's already-installed official Requests 2.32.3 against a
temporary **local** fixture only, checking GET, POST, headers, redirects not
followed, binary encoding, response limits, path scope and timeouts. No external
HTTP endpoint was contacted or package installed. MQTT tests use an explicitly
fake API, not an installed Paho client or real broker. Blinka/Paho were absent
on the Pi, and no physical sensor, actuator or MicroDuck pin map was tested.

The optional managed hook automatically owns Python and preserves existing
MicroDuck routing. Its real Pi lifecycle test starts SQLite, reads 42, closes
the application and verifies child/socket cleanup; startup cancellation also
leaves no owned child running. This does not certify activation of that hook
in the existing system service. Coordinated deployment with the committed Pi
browser updater remains pending; preserve its current programs and Caddy/network
policy. The staged native update requires `python-extensions` compatibility.

An initial graphical harness changed an input's display without sending its
normal edit event; a direct read of the test database caught the stale value.
The final test uses actual keyboard editing and requires the edited value to
return from SQL. Earlier exploratory HTTP-palette drag/error checks were not
accepted as evidence; the final negative UI check uses an actual edited SQL
statement. Generic insertion/drag gesture checks are recorded separately above.
