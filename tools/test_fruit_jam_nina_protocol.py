#!/usr/bin/env python3
"""Compile/run the real bounded NINA framing C with malformed input fixtures."""
# SPDX-License-Identifier: MIT
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wasi-sdk',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    import wasmtime
    root=Path(__file__).resolve().parents[1]
    board=root/'boards/adafruit_fruit_jam/smallvm/src'
    with tempfile.TemporaryDirectory(prefix='fruitjam-nina-') as folder:
        work=Path(folder)
        command=[str(args.wasi_sdk.resolve()/'bin/clang'),'-O1','-Wall','-Wextra','-Werror',
            '-I'+str(board),str(board/'nina_protocol.c'),str(board/'wifi_control.c'),str(root/'tests/fruit_jam_nina_protocol.c'),
            '-Wl,-z,stack-size=65536','-Wl,--max-memory=1048576','-o',str(work/'test.wasm')]
        subprocess.run(command,check=True,timeout=45)
        config=wasmtime.Config();config.consume_fuel=True
        engine=wasmtime.Engine(config);store=wasmtime.Store(engine);store.set_fuel(1000000)
        wasi=wasmtime.WasiConfig();wasi.stdout_file=str(work/'stdout');wasi.inherit_stderr()
        store.set_wasi(wasi);linker=wasmtime.Linker(engine);linker.define_wasi()
        instance=linker.instantiate(store,wasmtime.Module.from_file(engine,str(work/'test.wasm')))
        instance.exports(store)['_start'](store)
        report=json.loads((work/'stdout').read_text())
        report.update(command=command,source_sha256=hashlib.sha256((board/'nina_protocol.c').read_bytes()).hexdigest())
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
