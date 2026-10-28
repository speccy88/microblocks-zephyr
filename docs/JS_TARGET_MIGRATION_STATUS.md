# JavaScript target and custom-block migration

Keep GP as a usable fallback, the upstream JS pin separate from VM pins, and SFC
paused. This matrix tracks the migration scope requested after the Linux site
deployment. A visible library is not hardware acceptance.

| Target / feature | Preserved source and current JS status | Remaining work |
|---|---|---|
| Raspberry Pi 5 | Separate JS profile, core compiler/readback/matrix adapters, strict explicit loopback transport; prior real Pi JS arithmetic/readback/reconnect pass | New profile lifecycle acceptance; persistent service/boot and hosted WSS |
| MicroDuck RK3566 | Separate disconnected profile; coherent six typed read-only gateway libraries import140 functions; normal Pi fixtures retained | Remaining daemon interfaces, media pixels, physical commissioning; simple action library after editor migration |
| Fruit Jam | Explicit JS package, coherent library, private `fruitJam` namespace, version/identity-gated USB adapter | JS graphical peripherals/hardware and existing board-network path acceptance |
| Waveshare RLCD | Explicit JS package, complete library, private `rlcd` namespace, identity-gated USB adapter | JS graphical peripherals/hardware and board-network transport |
| Propeller 2 | Explicit FTDI USB profile with DTR false and v405 gate; complete `p2` library compile/roundtrip | Physical serial/reset behavior; independently inspect broader core primitive support |
| XRP RP2350 | Exact production GP library and four dependencies copied with hashes; actual import/compile/roundtrip and USB gate; native actuator locks retained | Physical locked-runtime JS acceptance; public GP connection remains unchanged |
| ESP32-P4 | Ten preserved modules and private maps; bounded extension dispatch; typed file controller/dialog, generation-bound neural import panel, guarded USB and explicit WSS frontend; native storage and full-suite checks in the dated receipt | Inline image/audio views and compiler tracing; owner checkpoint and real USB/WSS hardware acceptance |
| UNO Q matrix reference | Explicit offline profile and exact reference library;13x8 slot preserves104-digit strings/defaults and prior actual saved-file reopening | Independent firmware identity and connectivity; broader arbitrary-size variants need exact source |

The P4 owner's checkout, COM5/COM12 and paused SFC must remain untouched.
Use the sources already preserved in this isolated repository and obtain any
new owner checkpoint through coordination rather than changing its worktree.

The all-target contract is [JS_ALL_TARGETS_SPEC.md](JS_ALL_TARGETS_SPEC.md).
Headless USB fixtures and actual pinned compiler tests do not establish physical
board behavior. MicroDuck and UNO Q providers remain disabled. Existing ordinary
Steps & Transitions blocks are imported unchanged for compatibility; the paused
SFC graph/editor implementation has not been resumed.

After the editor migration, continue MicroDuck daemon libraries from supported
protocols with faithful fixtures. A small child-friendly library and advanced
libraries must coexist in the **same project**, sharing underlying interface,
units, confirmations and safety handling. They are abstraction layers, not
mutually exclusive modes. Simple move/turn/stop/look/sound/named-skill helpers
must not invent physical behavior or silently bypass advanced safety gates.
