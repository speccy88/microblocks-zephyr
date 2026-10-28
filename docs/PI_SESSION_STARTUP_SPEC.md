# Pi VM and editor bridge startup contract

Provide an explicit opt-in user service for the existing foreground supervisor.
One systemd unit owns supervisor, native VM and loopback bridge. A child failure
ends the other child; systemd restarts the session against the same private
program directory. The service must not start a second independent VM or point
at stale PTY discovery. Preserve the native binary installer and VM-only option.

The service utility requires an already installed pinned ARM64 binary, explicit
editor directory and Python interpreter with websockets15.0.1. Copy only the
reviewed supervisor/bridge sources into a hash-addressed immutable runtime
directory. Validate all inputs before replacing any unit. Refuse a foreign unit,
an active unit that would change, symlinks in managed destinations, unsafe paths,
non-private data and occupied ports. Keep NoNewPrivileges, PrivateTmp and
ProtectSystem=strict; grant write access solely to program data. Bind only
127.0.0.1 on an explicit high port. No Caddy, port80, firewall, certificate,
SSH-key, lingering or unrelated service changes. Existing uninstaller ownership
markers must still work.

Acceptance: actual systemd syntax check; foreign/invalid input preservation;
foreground status semantics unchanged; real Pi first start, VM and bridge child
failure recovery, saved program/CRC, graphical connect/readback/first evaluation,
and authorized OS reboot with no manual VM/bridge restart. Record disruption and
verify recovery files. Remove only test-owned services/processes after acceptance.

Investigate the earlier raw-fixture to graphical first-evaluation error with
wire traces and a reproducible regression. Do not assume reconnect fixes its
cause or declare acceptance for an errored first click. Preserve pinned upstream
editor files and prefer a bounded local compatibility correction if required.
