# Portable DSP / P4 acceleration stages

Fred requested image, voice interfaces and P4 PPA/ISP/JPEG/H.264 support on
2026-10-25. Native Zephyr remains required. These are separate capabilities;
the presence of silicon does not mean a MicroBlocks block is implemented.

## Contract

`dspCapabilities` returns explicit per-operation backend states: `software`,
`hardware`, `compiled_untested`, `unsupported`, or `unconfigured`. Preserve
these meanings across boards. Missing hardware may use a documented software
fallback only where the algorithm and output contract match. Nearest-neighbor
resize must remain nearest-neighbor; PPA bilinear scaling is a distinct
operation, with its 1/16 scale-factor restriction validated before DMA.

Images use bounded immutable handles, explicit formats/strides and lifecycle.
No GC pointer is retained in a DMA transaction. Jobs pin native input/output
ownership until completion or confirmed abort; cache-line-aligned buffers are
flushed before and invalidated after hardware access. Jobs have bounded
queues/deadlines and serialize peripheral ownership. Output-size arithmetic
is checked before allocation. Failure never returns an apparently valid image.

## Available and staged backends

| Operation | Silicon / SDK evidence | Native port status / gate |
|---|---|---|
| RGB565 capture, demosaic | CSI + ISP RAW8/10 to RGB565 | Native receiver physically passed with IMX219; OV5647 retained but not physically retested |
| Resize nearest, grayscale, RGB888 HWC uint8 | Portable C engine | Physical native VM tests and offline sanitizers pass |
| PPA scale/rotate/mirror | Native Zephyr `esp_ppa.c`, sample `ppa_srm` in pinned tree | Physical RGB888 identity/90/180/270/mirrors, RGB565 identity and smooth 2x geometry/channel tests passed on revision1.3. Blend/fill blocks remain missing |
| ISP exposure/white balance/color, filters/statistics | Espressif ISP controls exist | Start with verified capture/demosaic; expose only controls actually ported/tuned; AWB/AE are not automatic just because statistics exist |
| JPEG encode and decode | P4 hardware baseline JPEG codec, both directions | No P4 Zephyr video codec driver in pinned tree; separate bounded codec port and round-trip test required |
| H.264 encode | P4 hardware baseline encoder | Separate native port, revision errata, format conversion and RAM/bitstream validation required; no continuous video enabled |
| H.264 decode | Espressif component uses a software decoder | No claim of hardware decoding; unsupported in this port |
| PCM audio input/output | Native Zephyr ESP32 I2S driver has P4 paths | ES8311 ID8311, 16 kHz mono capture, DMA timing/lifecycle and controlled acoustic response physically passed. Browser inline playback passed; board speaker remains disabled/unconfigured |
| PDM | P4 I2S silicon functionality | Native driver mode support must be checked independently; not an audio recognition engine |
| FFT/filter/RMS/inference | CPU/software DSP and model-specific libraries | Bounded PCM RMS/peak, Whistle STT and native TFLM static dense model lifecycle/catalog/custom import physically passed. FFT/filter blocks and P4 kernel acceleration remain missing. No generic ONNX Runtime or YOLO claim |

Audio uses ES8311 at I2C0x18, SDA7/SCL8, MCLK13/BCLK12/LRCK10 and RX11,
16 kHz mono PCM. Its separate bounded sample pool and stop/cancellation were
tested; the PA remains off. No continuous microphone listener starts by
default. TFLM and model-resource contracts are in NEURAL_NETWORKS.md; PPA,
codecs and keyword-spotting still require their own native acceptance tests.

## PPA increment: contract and acceptance

Uses the pinned native Zephyr PPA API. Explicit smooth-resize, rotate-left
and horizontal/vertical flip reporters retain nearest resize separately.
RGB565/RGB888 inputs only initially; unsupported gray inputs, angles, dimension
bounds and nonrepresentable 1/16 scale ratios fail before DMA. One worker job,
no VM/GC objects in that worker, independent aligned native input copy so
releasing the original handle cannot race DMA; output adoption on VM thread.
Bound input/output workspaces separately, guard/cache-sync both buffers and
quarantine them if hardware times out without an observable abort guarantee.
Stop All cancels publication; never free a buffer still owned by hardware.
The four-handle store remains capped at 8 MiB. A PPA job additionally owns at
most 5,529,728 bytes for aligned input/output copies and guards (two 1280x720
RGB888 workspaces); allocation failure is explicit. Shared PSRAM limits still
apply when other workers reserve memory. Rotated results must fit 1280x720;
resize a full landscape 720p image before rotating it 90/270 degrees.

Acceptance sequence: compile both targets; physical generated quadrant/edge fixture
identity/90-degree rotation/mirror and smooth scaling; exact geometry/channel
order/guards; invalid/stale/unsupported input; source release during job;
cancel/repeat/release and heap reuse; VM latency while larger transform runs.
Record actual backend and duration, distinguish setup/copy cost from hardware
time. Show genuine per-block previews in GP, including independent outputs,
collapse/drag and release. No new camera capture or microphone is required.

`image-transforms.ubp` is the small generated-pattern example, available from
Projects & board. All four GP outputs were physically executed through the
COM5 bridge and displayed independently; first-result expansion, manual
collapse surviving rerun, re-expansion, settled drag rendering and expired
state on disconnect were verified. This is USB/loopback evidence; station
programming remains blocked by the companion control failure.

Tiny 48x32 fixtures measured approximately 83-321 microseconds inside the
PPA blocking API, with allocation/copy measured separately. This includes
driver/scheduling work and is not a CPU speedup benchmark. Jobs finished
before the first serial busy poll, so no long-job VM responsiveness measurement
is claimed. Cancellation tests include completed-but-unpublished results;
they do not prove an injected in-flight hardware fault. Real timeout/reset
fault injection was not performed. The conservative quarantine path retains
DMA buffers/client and refuses another operation until board reset.

## Primary sources

- [Zephyr PPA implementation](https://github.com/zephyrproject-rtos/zephyr/blob/a915b2f12675b48b16d56653ea145dcd8f20cbbf/soc/espressif/common/esp_ppa.c),
  [native sample](https://github.com/zephyrproject-rtos/zephyr/tree/a915b2f12675b48b16d56653ea145dcd8f20cbbf/samples/boards/espressif/ppa_srm).
- [Espressif PPA operations and scaling](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/ppa.html).
- [ISP pipeline/controls](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/isp.html).
- [JPEG engine directions](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/jpeg.html).
- [H.264 hardware encoder vs software decoder](https://components.espressif.com/components/espressif/esp_h264/versions/1.4.0/readme?language=en).
- [P4 I2S](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/i2s.html),
  [pinned Zephyr I2S implementation](https://github.com/zephyrproject-rtos/zephyr/blob/a915b2f12675b48b16d56653ea145dcd8f20cbbf/drivers/i2s/i2s_esp32.c).
- [Exact board resources and schematic](https://docs.waveshare.com/ESP32-P4-WIFI6/Resources-And-Documents).
