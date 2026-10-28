# Empty-editor reconnect preservation

The approved combined-service reboot preserved the exact saved program and both
services returned automatically. A later fresh graphical connection exposed a
separate pinned-editor behavior: `MB_Editor.justConnected` clears the board when
its current project differs, including when the editor is empty. Consequently,
reading the board after connecting is too late. The private arithmetic backup
remains intact; record the negative result separately from boot persistence.

For local Linux connections, wait for any pending autosave restore decision, then
arm upstream `readFromBoard` before opening the connection if the editor project
has no user code. Reuse upstream readback and existing non-writing readback
protection. A populated project retains the existing explicit connect/sync
behavior; its blocks, variables and imported libraries must never be silently
replaced. Serial/P4 connections, upstream files and runtime remain unchanged.
Do not clear or upload anything merely to prepare a read.

Acceptance: reproduce the old empty-project erase branch with the actual pinned
editor class; show that the guarded branch reads instead; retain populated and
serial behavior; honor restored autosave state and reject editor replacement
during that wait. On the real Pi, restore only the verified owned arithmetic
backup while the owned service is stopped, restart that unit, and demonstrate a
fresh graphical connection, readback and execution. This subsequent controlled
service restart does not replace the earlier automatic reboot-startup evidence.
No second reboot, security setting change or publication is required.
