# Board editor and installation entry points

Each of the eight landing-page cards keeps its editor and installation action
side by side, including on a narrow phone. Both open their destination in a
separate tab, preserving an edited project in another tab. The touch-editor
entry remains available. The global P2 install link moves into the P2 card.

`web/js-portal/boards.json` is the reviewed installation catalog. The launcher
and seven short installation guides are generated from it. The existing P2
installer retains its own firmware packager and real hardware acceptance.
Guide pages perform no USB, network discovery, installation or shell execution.

| Target | Installation entry | Reviewed boundary |
|---|---|---|
| Fruit Jam | RP2350 SWD/build guide | Physical SWD installation; no published project firmware image or browser flasher |
| Waveshare ESP32-S3 RLCD 4.2 | Pinned Zephyr build and USB guide | Standalone SmallVM build and physical installation; no public ready-to-flash image |
| Waveshare ESP32-P4 WIFI6 | Native Zephyr/USB serial guide | Tested pre-v3 board; revision guard and 0x2000 native simple-boot layout; no browser flasher |
| Propeller 2 | Existing browser RAM/flash installer | Real Windows Edge installation on Edge32; original Edge and Eval compiled only |
| Production XRP RP2350 | RP2350 SWD/build guide | Production ROB-26619; preserve state, motor power off; no published project firmware image |
| Raspberry Pi 5 | Linux source-installer guide | Current pinned-source bootstrap; older published alpha2 package linked separately |
| MicroDuck | Commissioning guide | Robot hardware and compatible release pending; disconnected preview remains explicit |
| UNO Q | Separate App Lab/reference guide | Verified v0.1.2 community release; MCU runtime installed separately; its bundled editor is GP, portal JS profile remains an offline reference |

Release metadata was reviewed on 2026-11-05 through the repositories' GitHub
release APIs. Project releases currently contain the Pi alpha2 package and an
editor preview archive, not firmware images for the four Zephyr MCU targets or
MicroDuck. Their guides link the real project release listing and explicitly
state that a matching firmware package is unavailable. No new release or
automatic flash support is invented by this layout change.

Acceptance checks cover all eight editor/action pairs, same-row proximity at
desktop and 320/390-pixel widths, touch targets, keyboard focus, separate tabs,
each local guide, truthful release/method labels, P2's unchanged installer,
saved-project preservation and absence of automatic connections. Run the
repository validator and actual browser tests, then verify CI and deployed
routes and assets. This UI change does not establish any new hardware support.
