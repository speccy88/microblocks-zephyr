# Foreground Pi session resume

Keep the fresh-directory default. Add explicit `--resume` for an existing
private user-owned data directory, preserving program.ucode and earlier logs.
Use the actual reviewed ELF rather than the installer's shell launcher.
Change no service, reboot, SSH or network setting; bind only loopback.

One supervisor owns a directory at a time, alongside the VM's own native data
lock. A contender must not attach to or stop an existing VM. Fresh exclusive
discovery/log filenames leave stale state untouched. Readiness requires the
new child PID, then this bridge child's successful bind marker and an HTTP
response. An unrelated HTTP server cannot make the session ready.

Publish private atomic session status and final child return codes. Stop only
the supervisor's own Popen children. Reject unsafe directories/lock/status files
without changing permissions or following symlinks. Existing data requires
--resume; missing resume data is an error.

Acceptance: actual native VM upload/CRC, socket reconnect and process resume
retain and execute a harmless program. Check competing supervisors, direct VM
ownership, stale live-VM discovery and occupied HTTP ports without affecting
their owners. Run locally, then on the real Pi using owned private storage.
Test the pinned JS compiler/connection path separately. Physical MicroDuck,
graphical acceptance, services and OS reboot remain outside this slice.
