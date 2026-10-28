# Waveshare ESP32-P4-WIFI6 - native Zephyr camera and audio

Required architecture: native Zephyr, SmallVM v417, portable image primitives,
and a P4 video driver. Future ArduinoCore-Zephyr compatibility is a goal;
arbitrary Arduino library support is not assumed. Real IMX219 capture,
resize/grayscale/RGB888 preprocessing and export passed on native Zephyr.
Bounded ES8311 PCM capture and experimental local Whistle speech-to-text are
implemented. A private controlled microphone clip matched the host/P4 text;
the actual graphical speech block also executes, with variable recognition
accuracy and scalar latency of tens of seconds. Native TFLM neural blocks now
run tested INT8 and float32 dense models, including a restricted offline ONNX
Gemm/Relu conversion. PPA smooth resize/rotate/flip now run in native hardware;
native Okay Nabu wake-word clip inference, bounded microphone streaming and GP
event hats also pass. Acoustic wake detection remains unverified. Direct ONNX
Runtime and NN kernel acceleration remain unavailable.
Native model transfer/rejection and actual GP catalog/custom file import and
inference passed. AP was canceled. The local station follow-up now passes actual
association/DHCP, flash-hosted asset integrity, WebSocket programming and 918 RAM
storage requests over Wi-Fi, with the factory C6 unchanged. A subsequent HTTP
poll-budget repair passed real board-hosted editor loading and RAM file editing;
the interrupted browser download remains unverified. Native SD metadata and
bounded MBFILES create/reopen/exact-readback tests now pass alongside a
hash-verified editor asset transfer. Earlier real board-hosted file-manager tests
created and reopened UTF-8 SD text, independently checked through COM5. The installed
opt-in saved-boot profile also reconnects automatically after tested warm resets;
the optional bounded loss-retry profile also passes one controlled local loss.
The small-packet latency follow-up found C6 Legacy power save enabled while
kernel/VM processing remained fast. The explicit low-latency profile now reads,
disables and confirms volatile power save once per boot, with no setter retry.
Raw TCP opened in62ms, worker pings took15..16ms and VM pings16..32ms; actual
GUI open/reconnect took89/95ms. A fresh file session took36ms under its unchanged
3s deadline and the SD view listed MBFILES successfully without file changes.
This keeps the receiver awake and may use more power; default profiles stay
unchanged. No C6 firmware, router, security or credential change was made.
The earlier30s editor opening/heartbeat tolerance remains a fallback. The
explicit powered-board profile now polls SDIO at5ms rather than20ms; the same
hash-verified2.2MB GP transfer improved from23.623s to10.236s.
Concurrent VM pings and native/graphical SD-read checks pass. More idle polling
may cost power; energy, full power removal and long-duration behavior remain
unmeasured. See [HTTP throughput and installed firmware](../../docs/P4_HTTP_THROUGHPUT.md),
[small-packet latency](../../docs/P4_TCP_LATENCY.md) and the [earlier deadline follow-up](../../docs/P4_CONNECTION_OPENING.md).
See [recovery acceptance](../../docs/P4_WIFI_LOSS_RETRY.md). See the
[bounded boot policy and evidence](../../docs/P4_SAVED_WIFI_BOOT.md) and the
[current physical results and local diagnostic](docs/NETWORK_LIVE_VALIDATION.md).
See [native SD results and limitations](../../docs/SD_STORAGE_NATIVE.md) for the
FAT32 probe, memory audit, installed bounded file manager and its limits.
The encrypted credential handoff is retained.
See [station target](docs/NETWORK_STATION.md) and [NN contract](docs/NEURAL_NETWORKS.md).
Current dark camera frames need a lit-scene retest;
the strict content check remains failed in the latest evidence.
See [START_HERE](START_HERE.md) for reproduction and current limitations.
See the [versioned hardware audit](docs/HARDWARE_SUPPORT.md) for populated
circuitry, connector/SoC-only features, shared pins and remaining driver/block gaps.

I2C Devices blocks scan an explicit bus, distinguish address-only/candidate/
confirmed identities, list supported readings and read typed numeric values
with units or formatted text. Actual bus 0 tests and GP execution confirm
IMX219/ES8311 IDs and camera register readings; address 0x64 remains unknown.
TMP117 temperature conversion is fixture-tested only, without attached hardware.
See [discovery contract and limits](docs/I2C_DISCOVERY.md).

The working ESP-IDF camera proof is preserved on the separate **local-only**
branch `codex/p4-idf-reference` at `86c116b`. It is not the requested final port.
See [architecture review](docs/ARCHITECTURE_REVIEW.md) and [spec](docs/SPEC.md).

See [Wake Word](docs/WAKE_WORD.md) for the optional model profile, measured
memory/latency, explicit listening controls and acoustic-test limits.
