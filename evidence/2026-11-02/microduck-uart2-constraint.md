# MicroDuck board mapping constraint — 2026-11-02

Fred's hardware-test finding, relayed by the parent task: UART2 is used by the
motors. A forced Radxa Blinka board/pin mapping must not be used on MicroDuck.
Use the appropriate robot/device service interfaces and validate their actual
ownership, model, buses and pins independently. Sharing RK3566 with another
board does not establish compatible connectors or pin assignments.

This records the operator-supplied constraint. No raw hardware capture for that
test exists in this checkout, and this note does not claim that SmallVM, Blinka,
an external sensor, an OLED, a camera or motor control passed on the robot.
Existing MicroDuck profile climate enablement remains false and
pin_map_validated remains false. The separate Pi5 Blinka installation/detection
is not a MicroDuck validation and must not be deployed as its board profile.
