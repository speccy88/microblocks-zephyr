# Reconciled P4 source and non-writing project readback

Base:7e228ef. Use only the owner's sealed fe01c3fb v4 source archive and
three-way merge against9db5c3f, preserving all unrelated migration paths.
Attribute installed firmware and the uninstalled combined candidate separately.
Do not modify the protected owner checkout, COM5/COM12, retained board session,
GP branch, live site, paused SFC, system SDK or network/security configuration.

The owner adds bounded MBFILES SD operations over the existing file lease and
RPC217, plus saved boot/retry/latency support. Bring those existing interfaces
into the JS package without inventing storage methods or relaxing ownership,
name, size, cancellation or uncertain-outcome checks. Retain exact-source and
SDK provenance; new Zephyr compilation and physical acceptance are separate.

Current broader readback reproduces59 P4 functions but loses111 native specs.
Generate a bounded target-local module/source catalog. Verify source size/hash
before loading a known embedded module; retain native specs/defaults while
decompiled stored functions override their own bodies. Unknown libraries keep
the original fallback. Restore native primitive namespaces per target.

Board-project readback must send only ping/version/variable/code queries while
active, suppress automatic synchronization and extension commands, and cancel
without clearing/resetting the board. Concurrent reads, disconnect, project
replacement and malformed/oversized library responses must fail clearly.
Do not claim that merely connecting an ordinary editor is non-disruptive.

Test the actual pinned connection/compiler/decompiler/editor with a faithful
simulated board stream, including full P4 libraries, representative scripts,
read-only cancellation, no-write assertions, reconnect and source reopening.
Use a separately labelled graphical fixture. Real P4 graphical acceptance
requires a coordinated link; preserve its existing session until then.
