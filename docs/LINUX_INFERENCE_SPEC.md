# Shared inference contract, Linux first

Requested engines: open-source LiteRT and ONNX Runtime, with an authored
PyTorch model/export workflow. This does not use Edge Impulse. Model formats,
operators, conversion versions and numerical tolerance remain backend-specific.

Implement one optional trusted Python extension, with lazy CPU-only adapters
for `litert` (.tflite, Interpreter API) and `onnx` (.onnx, CPUExecutionProvider).
Shared operations: backends, models, load, infer, info and unload. A configured
model ID selects an immutable hash-checked variant from a fixed local catalog;
wire input cannot name a filename, URL, Python factory, pickle or accelerator.
No automatic dependency/model download, delegate or custom-op loading.

First scope: one fixed-shape float32 input and output tensor, at most256
elements by default, no dynamic shape/resize, strings, quantized or sparse
tensors. Model sizes, dimensions and input/output JSON are bounded. The common
block uses normal flattened lists, explicit input/output scales and signed31
scaled integer output, preserving useful numbers on SmallVM417. Raw backend
float32 metadata/results remain separate from these user-facing units.

Optional runtime dependencies must not enter the default Pi5/Blinka dependency
lock, MCU images, core interpreter or browser. PyTorch and conversion tooling
are development/export dependencies, not required on an inference target.
Pi5 ARM64, native Linux x86-64 and future MicroDuck Yocto are separate acceptance
targets. glibc/Python ABI/wheels and providers must be checked independently;
no MicroDuck/Radxa pin mapping, NPU/GPU claim or motor interface is introduced.

Use the existing private worker supervisor and asynchronous VM Python jobs.
Blocking native execution stays in its own process; other VM scripts and other
extensions continue. A supervisor timeout kills the owned worker, loses its
loaded model and is never silently retried. Expose explicit missing dependency,
unsupported backend/format/type/shape/operator, integrity, no-model and timeout
diagnostics. Failed model replacement preserves the prior validated session.

Acceptance: run the same modest authored PyTorch network exported to separate
ONNX and LiteRT assets; compare real CPU results to recorded expected values
on available Linux hosts/Pi. Test load, switch, infer, unload, missing/corrupt
model, invalid inputs/output overflow, unavailable dependencies and supervisor
timeout/non-blocking behavior. Compile normal domain blocks with the real JS
compiler and execute them on a real native VM with an independent heartbeat.
Record engine versions, architecture, artifact hashes and bounded latency/RSS
observations without calling tiny-model timings a performance benchmark.

Keep default profiles disabled until explicitly commissioned. Current service,
program, SQLite, Caddy and all robot control remain untouched by isolated tests.
No new network listener, board firmware or hardware configuration is required.
