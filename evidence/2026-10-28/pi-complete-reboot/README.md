# Approved combined-service reboot and reconnect

Fred specifically confirmed this previously denied reboot. After a fresh host,
service and backup check, the exact command was retried once and returned zero:
`ssh -o BatchMode=yes -o StrictHostKeyChecking=yes rpi5 sudo -n /usr/sbin/reboot`.
No alternate reboot command or second reboot was used.

The Pi changed boot ID from `589fbd5f-cfbc-41ca-8ed9-ceb925b094fb` to
`2f648fa6-81dd-4fa0-99d3-e796a17faf38`. The combined user service activated at
8.645127 seconds after boot, before the first SSH return check at uptime21.69s.
Supervisor1045, VM1051 and bridge1053 started automatically. HTTP returned200,
the bridge protocol returned42 and CRC4087428137, and the program hash was still
`e1670b43577fb8aa7335fdd4fbef213d482c79874db785842275e6aca3325600`.
All previously running system services returned. Existing lingering remained yes;
no security/network configuration changed.

## Separate graphical reconnect defect

Opening an empty editor and using the original Connect button erased the stored
program before the subsequent Read button. The resulting file was4bytes, with
SHA256 `2d556dff0157cd804851fac5c6ed0ad2466a5081f461d92ff4fc4d5ebf38856b`.
This happened after successful boot persistence, not during reboot. The pinned
`MB_Editor.justConnected` deliberately synchronizes a differing current project,
including an empty one. The negative screenshot and query receipt are retained.

The local adapter now waits for an autosave restore decision and arms upstream
readback before a Linux-loopback handshake when the current project is empty.
Populated projects and serial targets retain their existing behavior. The pinned
engine, VM and transport security are unchanged. The focused regression uses the
actual pinned editor method and seven cases, including the old erase branch.

Only the owned service was stopped to restore the exact private backup and apply
two adapter files to the private test editor. It was then restarted once. This
manual repair restart is distinct from the already-recorded automatic boot start.
Two fresh graphical connections automatically recovered the arithmetic block;
each evaluation returned42. The final32-byte program and CRC matched the original
pre-reboot values exactly. No new arithmetic project was uploaded as a substitute
for readback. The shared acceptance panel says fictional robot, but these runs
use the actual Pi VM and no robot daemon or simulated arithmetic.

## Cleanup and limits

The owned uninstall removed its test unit and launcher, retaining the saved code,
backup, private Python environment and immutable versions. The cleanup probe's
first reload copy used default file permissions and was correctly refused by the
VM. Uninstall was not repeated. A new0600 private copy executed the retained code
and returned42. No SmallVM remained running after that check. The owned browser
tab and identity-verified temporary SSH tunnel were closed; unrelated sessions
and services were retained. The original tunnel cleanup guard stopped before
termination because of DateTime reparsing; exact PID/start/argv verification
resolved it without touching another process.

The alpha1 archive remains unchanged and predates the reconnect fix. Rebuild the
package with this adapter, verify its final contents, and coordinate publication
and download/hash acceptance before offering a public installer command. Fresh-SD
setup, Windows reboot/SSH-agent persistence and physical MicroDuck remain untested.
The inherited reboot approval blocker is resolved. No publication occurred.
