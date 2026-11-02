# Optional Linux CPU inference acceptance — 2026-11-02

Implemented one optional Python inference extension with lazy LiteRT2.3.0 and
ONNX Runtime1.31.1 CPU adapters. A fixed authored two-dense-layer/ReLU PyTorch
network was actually exported with CPU PyTorch2.14.0, LiteRT Torch0.10.0 and
torch.onnx/ONNX1.23.2 to separate self-contained .tflite/.onnx artifacts.
The catalog records source and artifact SHA256 hashes, dtype/shape, expected
PyTorch values and tolerance. No pretrained/model-service dependency, pickle,
arbitrary model path, external ONNX tensor file, GPU/NPU or motor operation.

On Linux x86-64 / Python3.14.4 / glibc2.43 (WSL), 13 controller/real-engine/
worker tests plus two genuine JS-compiled domain-block/native-VM tests pass
with zero skips. The two CPU engines return float32 outputs within1e-5 of
PyTorch and scaled [2950,-2225,6812]. Tests cover load/switch/unload, prior-model
preservation, unknown/missing/corrupt/incompatible models, dynamic shape,
external tensors, invalid inputs, output bounds and optional dependency errors.
The timeout test deliberately pauses its own worker and confirms that another
SQLite worker responds before timeout; this is fault injection, not measured
slow-model performance. The process is owned by the isolated test service.

The actual native x86-64 VM417 was compiled from the pinned source. Genuine
editor functions/blocks compile36 chunks per backend; the normal user program
contains no RPC/bridge selectors. An independent heartbeat reached190/227 while
the respective real model call was pending, then the output reporters returned
the expected integers and the VM still answered ping. Tests use private PTY,
private Unix service/state, and no TCP listener or user's program/database.
The shared loader also checks that a saved Python1.0 core library is retained
by identity when the separate Neural Inference implementation library is added.
The unchanged SQLite compiler example still produces its original32 chunks.

host-x86_64.json records50 measured calls after five warmups, fresh process per
backend. Tiny-model tensor-I/O CPU medians were6us LiteRT and17us ONNX;
whole-operation medians19.9us and35.55us. Peak process RSS was about55MiB and
73MiB, including Python/native libraries. Timings exclude VM/IPC and depend on
the host/virtualization/cache/scheduling: no broader model, target, accuracy,
acceleration or speedup claim is made.

Pi5 physical inference, current managed-service deployment and MicroDuck Yocto
inference are not validated at this checkpoint. Dedicated CI installs only the
optional CPU requirements and requires all15 tests on native x86-64 and ARM64
with no skips. The existing Pi/Blinka service, default dependency lock, program,
SQLite, MQTT/broker settings, network and robot controls are unchanged by these
host tests. Default Pi5/MicroDuck inference profile entries remain disabled.

The dedicated [ARM64 CPU job](https://github.com/speccy88/microblocks-zephyr/actions/runs/41491581084/job/125435677237)
on source commit7501270654e836670189ed7c51152380962883d3 also passes all15
tests without skips on a native GitHub ubuntu-24.04-arm host (aarch64,
Python3.13.17, glibc2.39). host-arm64-ci.json records its actual engine/model
results and bounded CPU measurements from the completed job log. The native
x86-64 job of the same workflow also passes. This is host CI evidence, not
Pi5 physical commissioning, MicroDuck Yocto support or deployment.
