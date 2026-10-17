#!/usr/bin/env python3
"""Run bounded wasm32/WASI interpreter tests and retain their output."""
# SPDX-License-Identifier: MIT
import argparse
from pathlib import Path
import wasmtime

parser = argparse.ArgumentParser()
parser.add_argument("module", type=Path)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
config = wasmtime.Config()
config.consume_fuel = True
engine = wasmtime.Engine(config)
store = wasmtime.Store(engine)
store.set_fuel(200_000_000)
wasi = wasmtime.WasiConfig()
wasi.stdout_file = str(args.output)
stderr = args.output.with_suffix(".stderr.txt")
wasi.stderr_file = str(stderr)
store.set_wasi(wasi)
linker = wasmtime.Linker(engine)
linker.define_wasi()
module = wasmtime.Module.from_file(engine, str(args.module))
instance = linker.instantiate(store, module)
try:
    instance.exports(store)["_start"](store)
finally:
    print(args.output.read_text() if args.output.exists() else "")
    print(stderr.read_text() if stderr.exists() else "")
