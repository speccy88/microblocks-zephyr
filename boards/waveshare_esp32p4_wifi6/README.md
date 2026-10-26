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
inference passed. AP was canceled; station-only firmware and flash-hosted assets
are built and hash-flashed. User-entered station credentials were saved and
readback-verified. C6 request 284 times out after station start, blocking
association/DHCP and HTTP acceptance. The encrypted handoff is retained.
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
