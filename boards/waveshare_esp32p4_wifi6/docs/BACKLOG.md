# Ordered follow-through (2026-10-26)

New ideas are queued; they do not interrupt the current task or create another
hardware owner. Native Zephyr, COM5-only access, USB plus station-hosted targets,
AP disabled and preservation of saved credentials apply throughout.

1. Finish bounded station compatibility diagnostics. Verify association, DHCP,
   board-served editor assets, real WebSocket programming and USB ownership.
   If blocked, record the exact evidence and proceed to independent work.
   The official support question is ready, but connector submission returned
   HTTP 403; no issue was created and no new access grants were requested.
2. Complete a versioned hardware coverage audit for the actual P4-WIFI6
   revision: schematic/product revision, populated parts versus connectors
   versus SoC facilities, pins and conflicts, native drivers, block exposure,
   and linked end-to-end evidence. States: tested, implemented-unverified,
   missing, incompatible. A capability list alone is insufficient.
3. Portable I2C discovery and readings, inspired by SparkFun's MIT-licensed
   Universal Auto-Detect source at 39b20cc3a9a1b1163f14fdfb8812c754926734c8.
   Explicit bus, bounded/cancellable operations and stable result lifecycle;
   address ACK, candidate and confirmed identity are distinct. Unknown devices
   expose addresses only. Registry names supported measurements, types and
   units; unsupported reads fail explicitly. Start with a small verified set,
   fixtures and safe available hardware. No blind configuration, reset, mux
   switching or foreign sensor probes at camera/codec addresses. Preserve
   third-party notices and inspect each reused driver's license.
4. Independent lightweight local wake-word detection using a compatible
   frontend/model/backend, explicit start/stop and event hat, bounded queues,
   confidence/cooldown, no default listener. Whistle remains separate.
5. Measured PPA/DSP/NN acceleration, then staged JPEG/H264 interfaces with
   accurate encode/decode directions and unsupported capability boundaries.
6. ESP-NOW portable blocks: capability/init, peer configuration, bounded typed
   send, receive event, sender/status, queue overflow/errors and teardown.
   P4 has no radio; current C6 support is unverified. Zephyr's direct-radio
   ESP32 sample does not establish a Hosted implementation. Espressif's open
   issue #19 tracks missing Hosted support. No channel change, broadcast,
   persistent keys, station disconnection or C6 flash without appropriate
   authority. RF proof requires a separately authorized available peer.

Hardware audit coverage includes CSI/IMX219/OV5647 and DSI attachments, ES8311
mic/speaker path, C6 Wi-Fi/Bluetooth, SD/storage, USB roles, exposed
GPIO/I2C/SPI/UART/I2S, buttons/LEDs/power, ISP/PPA/JPEG/H264 and compute
facilities only as verified on this exact schematic. Do not infer populated
Ethernet, displays, speakers or other loads from a generic P4 feature list.

Every library increment needs a usability pass: concise action/reporter labels,
named inputs/units, defaults/dropdowns, tooltips/help, small working examples,
native category colors/spacing, and explicit busy/empty/error/unsupported
states. Avoid backend jargon in the primary flow. Preserve the GP visual
language; check normal Windows viewport/scaling, long names, previews,
collapse/play, drag/cache, palette overlap and supported keyboard interaction.
Test USB and hosted UI separately. Return actual editor screenshots at coherent
milestones; a successful build does not prove visual polish or usability.

Primary references:
- https://github.com/sparkfun/SparkFun_Qwiic_Universal_Auto-Detect
- https://www.ti.com/lit/ds/symlink/tmp117.pdf
- https://docs.zephyrproject.org/latest/samples/boards/espressif/espnow/README.html
- https://github.com/espressif/esp-hosted-mcu/issues/19
