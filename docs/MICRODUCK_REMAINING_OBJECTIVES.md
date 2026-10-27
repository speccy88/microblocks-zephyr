# MicroDuck remaining brief objectives

This separates missing software from acceptance gates. The update-watch merge
and read-only preflight are retained on the isolated integration branch. The
next additive checkpoint implements a receive-only camera signaling/browser
peer core with internal fakes. It opens no live camera, signaling endpoint or
robot connection. The physical robot has not arrived.

| Brief objective | Remaining work | Kind and next acceptance |
|---|---|---|
| Camera/video transport | [Receive-only camera core](../linux/microduck/CAMERA.md) implements the pinned GStreamer consumer signaling, video-only browser answer policy and sole read-only media.video query. Tests use in-memory signaling and fake RTC/media, with no decoded frames. | Remaining software: trusted live signaling adapter/identity, explicit viewer and playback/rotation UI, and any native camera primitive. Shipping camera, codec/ICE/DTLS/browser interoperability, privacy and physical geometry remain acceptance gates. No live URL or connection is enabled in the portal. |
| Continuous locomotion and direct motor surfaces | No implementation of these control transports is supplied. BLE/local gateway and camera observer do not grant them. | Missing software outside the reviewed discrete-method surface. Review the official control interfaces and authorization before a separate implementation; require independent safety and hardware acceptance. No real motion command is sent. |
| Secure real PIN/Wi-Fi commissioning | No verified confidential browser transport has been commissioned. Real Web Bluetooth remains immutable confidential:false. | Missing secure transport/attestation plus shipping-image validation. Keep all actual PIN/PSK transmission blocked; a checkbox, PIN or invented endpoint is not a solution. |
| Complete duckctl command parity | The browser supplies 27 raw methods, two structured credential paths and one dedicated stream. Broader gamepad/reboot/policy-management surfaces are not exposed merely because a daemon names them. | Deliberate partial command coverage. Add only source-reviewed parameter, permission, confirmation and unknown-outcome contracts; use mocks before hardware. Dynamic skill discovery is already implemented; arbitrary dynamic RPC forwarding is not authorized. |
| Prepare the shipping image for read-only native use | The checklist currently requires manual host/config/socket inspection. | Implemented preparation: a filesystem-only commissioning preflight, with no connections, requests, listeners, permission edits or services. See [preflight](../linux/microduck/PREFLIGHT.md); it does not complete shipping-image acceptance. |
| Actual robot API, socket identities and caller policy | Shipping revision, expected numeric server UIDs and real peer identities remain unknown. | Hardware/inventory gate. File ownership and a configured UID cannot substitute for SO_PEERCRED or a successful permitted daemon request. No guessing identities or relaxing permissions. |
| Sensors, battery, IMU, health, sound and skills | Typed records and native jobs run on the real Pi against simulated robot daemons. Physical readings/actions remain untested. | Physical gate. Compare source-backed units, absence/default semantics and observed diagnostics on arrival. A health record is not movement authorization. |
| Graphical typed example and protected console | Native bytecode and mock DOM/RPC tests pass. Graphical execution/acceptance remains unverified. | Platform/UI gate: Edge control was stopped because the current Windows browser URL could not be determined confidently. No retry or alternative UI-automation route is attempted here. |
| HTTPS Pages transport | Trusted WSS and actual browser local-network behavior are not commissioned. | Deployment/transport gate. The supported loopback editor/SSH path is tested; no mixed-content or certificate-warning bypass. |
| Public release, copy command, Pages and hosted CI | Local deterministic candidates and workflows exist; live assets, published install/copy and hosted runners are unverified. | Coordination/publication gate. Integrate the P4 owner's intended commit separately, regenerate exact final provenance, publish only when coordinated, then verify real URLs/download bytes. |
| User-service startup, full OS reboot and Windows SSH after reboot | Templates/process persistence are tested; actual startup and reboot are not. | Acceptance gate. Foreground/process-restart evidence does not establish reboot behavior. No startup/security change or reboot is performed by this work. |

The preflight will report observations and blockers, never global robot-ready,
caller authorization, verified daemon identity or permission to move. It must
remain useful on fixtures/Pi while labelling those as unrelated to physical
MicroDuck acceptance. Existing service processes and security settings remain
unchanged. There is no current approval request.
