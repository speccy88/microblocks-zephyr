# JSONata — next local feasibility stage

JSON CRUD and JSON Pointer are implemented separately in [JSON.md](JSON.md).
They do not implement JSONata expressions. No JSONata block or native support
is advertised yet. No browser/cloud execution is substituted for on-device code.

Read-only source inspection identified two candidates:

* [jsonata-cpp](https://github.com/rayokota/jsonata-cpp) has an Apache-2.0
  C++17 implementation using nlohmann_json and utfcpp. Its current CMake
  integration fetches nlohmann_json v3.12.0 if absent. Build dependencies must
  be pinned and prepared offline before a Zephyr compile. The README's language
  coverage claim is upstream's claim, not a result on this board.
* [jsonata-c](https://github.com/qlyoung/jsonata-c) embeds the JavaScript
  implementation using Duktape. Its Makefile builds ES5 JavaScript with npm and
  links Duktape; it is not a dependency-free C evaluator.

The [official JavaScript reference](https://github.com/jsonata-js/jsonata)
and [language documentation](https://docs.jsonata.org/) define the behavior to
compare. Reference vectors should cover selection, mapping/filtering, arithmetic,
aggregation, object construction, missing/null/array semantics, Unicode and errors.

Before integrating either runtime, measure host footprint and then native RV32
compile size, PSRAM/scratch use and latency. Establish limits for input/output,
expression bytes, recursion, intermediate allocations, regex cost and evaluation
steps, with cancellation. Generic C++ heap use and evaluation recursion need
inspection; a successful host evaluation alone will not establish safe bounds.
No expression may call network, filesystem, GPIO or other host functions.

Current status: initial source review only. Neither candidate has been built,
installed or run in this project. Next step is a pinned offline host comparison
and allocator/cancellation audit, then a separate native profile if feasible.
