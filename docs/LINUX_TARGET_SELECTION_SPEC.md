# Independent Linux targets

The portal's existing board dropdown must expose Raspberry Pi 5 independently
of robot services, and the separately named MicroDuck Rockchip RK3566 target.
Keep their existing stable IDs (`raspberry-pi5`, `microduck`) and other boards.
MicroDuck is an experimental placeholder, not an installable/validated robot.

Pi 5 advertises only its physically tested native SmallVM core and dated editor
evidence. It requires no robotd, mediad, tofd, padd, Bluetooth, GPIO driver or
MicroDuck socket. Peripheral support, released download installation, actual
user service and OS reboot must not be inferred from core/process tests.

The MicroDuck placeholder permits offline editing/preparation. Its public
profile must not open hardware transports or offer installation commands even
if a future generic ARM64 release manifest becomes available. Disable its
installation/service/endpoint fields and clear stale choices on target switch.
Keep explicit simulation/development packages separate from this public target.

Pi installation commands remain gated by a reviewed immutable release, with
existing hashes, host verification and browser trust checks intact. Selection
does not connect, probe, install or change security/network settings. The public
main site is unchanged until integration is coordinated; a source/preview change
must not be described as a deployed Pages update.
