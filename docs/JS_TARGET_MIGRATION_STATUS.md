# JavaScript target and custom-block migration

Keep GP as a usable fallback, the upstream JS pin separate from VM pins, and SFC
paused. This matrix tracks the migration scope requested after the Linux site
deployment. A visible library is not hardware acceptance.

| Target / feature | Preserved source and current JS status | Remaining work |
|---|---|---|
| Raspberry Pi 5 | Separate JS profile, core compiler/readback/matrix adapters, strict explicit loopback transport; prior real Pi JS arithmetic/readback/reconnect pass | New profile lifecycle acceptance; persistent service/boot and hosted WSS |
| MicroDuck RK3566 | Separate disconnected profile; coherent six typed read-only gateway libraries import140 functions; normal Pi fixtures retained | Remaining daemon interfaces, media pixels, physical commissioning; simple action library after editor migration |
| Fruit Jam | Four native `fruitJam` specs preserved in board library; GP fallback retained | Board-specific JS packaging, namespace, verified identity and transport tests |
| Waveshare RLCD | Fourteen `rlcd` specs and library functions preserved | Board-specific JS packaging, namespace and network/USB contract tests |
| Propeller 2 | Twenty `p2` specs, Smart Pin helpers and GP native USB implementation preserved | Correct FTDI/reset signal handling, identity gate, compiler/library tests |
| XRP RP2350 | Production XRP library remains in the pinned GP assets; public connection remains disabled | Extract exact library/provenance, import/compile/profile and matching locked-runtime semantics |
| ESP32-P4 | Camera31, audio16, neural16, speech7, wake-word13 and I2C18 specs preserved; GP fallback has media/files/NN protocols | Typed JS namespace, complete library import/roundtrip; bounded extension dispatch and actual block rendering; owner checkpoint/hardware acceptance |
| UNO Q matrix reference | Existing13x8 slot preserves104-digit string, defaults and actual saved-file reopening | Broader arbitrary-size variants need their exact source; no independent UNO Q firmware/checkout changes |

The P4 owner's checkout, COM5/COM12 and paused SFC must remain untouched.
Use the sources already preserved in this isolated repository and obtain any
new owner checkpoint through coordination rather than changing its worktree.

After the editor migration, continue MicroDuck daemon libraries from supported
protocols with faithful fixtures. A small child-friendly library and advanced
libraries must coexist in the **same project**, sharing underlying interface,
units, confirmations and safety handling. They are abstraction layers, not
mutually exclusive modes. Simple move/turn/stop/look/sound/named-skill helpers
must not invent physical behavior or silently bypass advanced safety gates.
