# MicroDuck starter libraries and advanced blocks together

In the staged JavaScript MicroDuck editor, choose **Load starter lab (includes
SIMULATION)**. The optional `Libraries/MicroDuck Starter Lab.ubl` import contains
ten modules and186 functions: the six existing normal read-only modules, the
preserved advanced Motion/Robot Simulation modules, Simple Sensors and Simple
Practice. The ordinary six-module `MicroDuck Linux` import keeps six modules (146 functions).
Both abstraction levels can be used in one project and saved/reopened together.
There is no mode switch or second connection.

Simple Sensors offers battery, reported board temperature and health verdict, head temperature, depth-zone and declared
gamepad-button readings. Each helper captures, reads and releases one immutable
snapshot through the existing service adapter. Invalid indices are refused
before capturing. Use **reading known?** before extracting a value; **reading
status** and **reading unit** explain unavailable results. Units and origins
match the advanced libraries: battery0.01%, head temperaturemC, rangemm and
buttonBoolean. This first layer hides lifecycle bookkeeping, retaining explicit
typed readings rather than silently replacing unknown data with zero. Button
numbers follow descriptor discovery; they do not promise a particular A/B name.

Simple Practice contains six explicitly labelled SIMULATION blocks: timed
forward, timed left yaw, cancel the mock timed lease, preview stop, chirp and
named skill. They call the same advanced simulation wrappers. Confirmation
defaults false, backend opt-in and existing command bounds remain mandatory,
and there is no retry. Timed commands do not promise a travelled distance or
turned angle. Preview stop is a recorded `robot.stop` request, not a real stop
or torque-off. Actual robot transport and movement are not enabled.

The actual pinned JS editor imports, compiles and reopens representative simple
and advanced projects. Native tests upload those actual compiled function bytes
to the existing verified local SmallVM, using private protocol-faithful robotd,
tofd and padd fixtures and mock motion/packet recorders. The graphical check
places both action layers and a simple sensor reporter in the same project.
See [the dated evidence](../evidence/2026-10-28/microduck-starter/README.md).

New helper validation is local: it is not new Raspberry Pi execution, physical
MicroDuck or browser-to-robot acceptance. Shipping identity/configuration,
continuous freshness, calibrated geometry, actual stopping and live movement
remain commissioning gates. Mediad audio still lacks a supported upstream
interface in the reviewed source. Existing BLE confidentiality restrictions,
GP/live versions, native runtime, shared main, P4 hardware and paused SFC stay
unchanged.
