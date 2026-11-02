# Optional Linux inference: LiteRT and ONNX Runtime

The shared Python extension provides two explicit **CPU** adapters: LiteRT2.3.0
(`ai-edge-litert`, Interpreter API) and ONNX Runtime1.31.1
(`CPUExecutionProvider`). Neither imports PyTorch or loads a GPU/NPU delegate
on the target. Imports are lazy; ordinary SQLite/Blinka use does not require
these packages. Default Pi5 and MicroDuck profiles keep inference disabled.

## High-level blocks

Use the normal Data blocks and `Examples/Python/Neural inference.ubp`:

1. `load neural model [tiny-dense-v1] backend [litert]` (or `onnx`).
2. `neural prediction [list 1000 2000 3000 4000] input scale [1000] output scale [1000]`.
3. Read the resulting ordinary list, inspect `neural backend` or model info,
   then `unload neural model`.

The input represents float32 `[1,2,3,4]`. The authored PyTorch fixture returns
approximately `[2.95,-2.225,6.8125]`; output units are scaled signed31 integers
`[2950,-2225,6812]` (allow one unit of rounding difference). A heartbeat runs
independently while the example loads/runs. Programs contain no bridge setup,
request IDs, Python factories, model filenames or polling loops.

First supported tensor contract: one fixed-shape float32 input and output,
flattened lists, positive dimensions/rank1..4 and at most256 elements by default
(configured ceiling1024). Explicit integer scales1..1000000 preserve useful
numbers on SmallVM417; nonfinite values and scaled output overflow are rejected.
This does not expose arbitrary ONNX graphs, dynamic/multiple/quantized tensors,
pretrained vision/speech or LLM pipelines as already supported features.

## Optional commissioning

In an explicitly chosen isolated Python environment, install one engine or both:

```sh
python -m pip install --index-url https://pypi.org/simple -r linux/extensions/inference/requirements-litert.txt
python -m pip install --index-url https://pypi.org/simple -r linux/extensions/inference/requirements-onnx.txt
# Both:
python -m pip install --index-url https://pypi.org/simple -r linux/extensions/inference/requirements.txt
```

Select that environment as the application's Python interpreter, preserve its
other required dependencies and enable the existing `inference` profile entry
only after checking its packages and model catalog. No default Pi5/Blinka lock,
existing service, project/database, MCU image, router or robot control is
modified by adding this source integration. Runtime installation and service
activation are separate from an isolated test result.

`demo_models:true` selects only the two small authored MIT fixtures bundled in
`models/`. For custom models, omit that flag and configure `model_dir` as a
canonical absolute trusted directory plus a `models` dictionary matching
`models/catalog.json`'s `models` field. Every variant needs its own filename,
format and SHA256; input/output shape and dtype must match actual engine metadata.
Only a configured model ID is accepted from blocks. No model path/URL, pickle,
external ONNX tensor file, custom shared library or executable model is accepted.
The worker uses model bytes and fixed CPU providers, never a host/cloud fallback.

`backends` reports installed package versions and reasons, not a claim that all
models are compatible. Failed load/replacement retains the previous model.
Missing packages, unknown backend/model, integrity/type/shape/operator errors,
invalid inputs and output overflow produce explicit diagnostics. Native work
stays in its owned worker process. The supervisor deadline stops a hung worker;
its loaded model is then lost and must be explicitly loaded again. No automatic
retry is performed. These bounds are not a complete sandbox for arbitrary
unreviewed native model parsers; catalogs remain trusted application configuration.

## PyTorch export workflow

Use a **separate development environment** for conversion. The tested exporter
uses CPU PyTorch2.14.0, `litert-torch==0.10.0`, `onnx==1.23.2` and
`onnxscript==0.7.2`. The catalog records the exact tested versions and source hash.

```sh
# Inside the export venv; CPU PyTorch is from its official wheel index:
python -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.14.0+cpu'
python -m pip install --index-url https://pypi.org/simple litert-torch==0.10.0 onnx==1.23.2 onnxscript==0.7.2
python tools/export_linux_inference_models.py --output /a/fresh/reviewed/model-directory
```

The tool authors a fixed two-dense-layer/ReLU network, exports it with
`torch.onnx.export(dynamo=True, external_data=False)` and
`litert_torch.convert`, and records separate artifacts, hashes, contracts and
PyTorch expected outputs. It loads no pickle or pretrained weights. Real custom
models must pass their own conversions/operator/shape/tolerance acceptance;
ONNX and TFLite are not a universal interchangeable format. PyTorch/converter
dependencies are not installed on the inference target.

## Targets and validation

Linux x86-64 and Pi5 ARM64 are separate test targets. Current wheels require
compatible Python and glibc (combined runtime pins: Python3.11+, glibc2.28+).
The future MicroDuck **Yocto** image must independently supply/check Python ABI,
libc, CPU libraries and package recipes; musl or an older glibc may require a
native/source build. No Yocto deployment, RKNN/NPU driver/delegate, robot policy
or motor operation is implemented or commissioned here. Never force a Radxa
Blinka profile: UART2 is motor-reserved. Use the robot's appropriate interfaces.
MCUs keep their own adapters; the existing P4 TFLM implementation is not replaced
by a Linux Python dependency or claimed as an ONNX Runtime port.

The canonical block/operation/tensor semantics live in this shared extension
and [spec](../../../docs/LINUX_INFERENCE_SPEC.md). Future target adapters may use
different backend-specific artifacts while preserving the domain-level blocks.
Capabilities must identify family, CPU, backend, format/operators and validation
separately; installed/available/enabled/tested are distinct states.

Tests separate controller fakes, actual CPU engines, supervised-worker fault
injection and genuine JS-compiled blocks on a real VM with a heartbeat. The
timeout test pauses only its own test child; it is not a slow-model benchmark.
`tools/check_linux_inference.py` records bounded tiny-model latency/RSS in a
fresh process per engine. RSS includes Python/libraries and timing excludes
VM/IPC; no general speed, model accuracy or NPU performance is inferred.

Official sources: [LiteRT](https://developers.google.com/edge/litert/overview),
[LiteRT Torch](https://github.com/google-ai-edge/litert-torch),
[ONNX Runtime Python](https://onnxruntime.ai/docs/api/python/api_summary.html),
[PyTorch ONNX export](https://docs.pytorch.org/docs/stable/onnx.html).
LiteRT/LiteRT Torch are Apache-2.0, ONNX Runtime/ONNX MIT and PyTorch BSD-style;
their packages retain their own third-party notices. The authored fixture source
and weights here are MIT, without a pretrained-model license dependency.
